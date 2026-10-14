"""
Brand-enrichment calibration run
=================================
The gate specified in BRAND_ENRICHMENT_PLAN.md before any production run:
research a fixed, small set of talents, print a report a human can
hand-score, and stop. No talent_brands rows are ever written by this
script — see enrichment.brands.run for the real pipeline, which should not
run at full scale until this output has been hand-scored.

Calibration set (see build_calibration_set):
  - top 10 talents by Instagram follower count (A-list proxy — expected to
    have real, findable endorsements)
  - 10 random talents from the bottom half of follower count (restricted to
    talents with an Instagram handle, so there's at least a search anchor).
    This half is deliberately included because validating only on A-list
    talent reports false accuracy — the mid/obscure half is where
    fabrication shows up, per BRAND_ENRICHMENT_PLAN.md.

Usage
-----
    python -m enrichment.brands.calibrate                  # build + print the set, no spend
    python -m enrichment.brands.calibrate --run             # research it for real, print + save report
    python -m enrichment.brands.calibrate --run --seed 7    # different random bottom-half sample
    python -m enrichment.brands.calibrate --run --yes       # skip the spend confirmation

The `--seed` default (42) is fixed on purpose: running the preview, then
`--run` afterward, must show and then research the exact same 20 talents —
not re-roll the random half between the two invocations.

Requires DATABASE_URL always; ANTHROPIC_API_KEY only for --run.
"""

import argparse
import math
import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from .normalize import BrandCache
from .provider_base import TalentQuery
from .run import (
    LOG_DIR, build_talent_queries, fetch_talent_rows_by_id, validate_candidates,
    write_log_atomic,
)

DEFAULT_SEED = 42
TOP_N = 10
BOTTOM_SAMPLE_N = 10


# ---------------------------------------------------------------------------
# Pure logic — no DB / network.
# ---------------------------------------------------------------------------

@dataclass
class CalibrationTalent:
    talent_id: str
    name_en: str
    name_native: str | None
    handle: str
    followers: int | None
    cohort: str  # "top10" | "bottom_random10"


def build_calibration_set(pool: list[tuple], seed: int = DEFAULT_SEED) -> list[CalibrationTalent]:
    """pool: (talent_id, name_en, name_native, handle, followers) tuples,
    already ordered by followers descending (fetch_calibration_pool does
    this). Top 10 = highest followers; 10 random from the back half of the
    SAME pool (which is already restricted to talents with a handle)."""
    top10 = pool[:TOP_N]
    bottom_half = pool[len(pool) // 2:]
    rng = random.Random(seed)
    bottom_sample = rng.sample(bottom_half, min(BOTTOM_SAMPLE_N, len(bottom_half)))

    result = [_to_calibration_talent(row, "top10") for row in top10]
    result += [_to_calibration_talent(row, "bottom_random10") for row in bottom_sample]
    return result


def _to_calibration_talent(row: tuple, cohort: str) -> CalibrationTalent:
    talent_id, name_en, name_native, handle, followers = row
    return CalibrationTalent(
        talent_id=str(talent_id), name_en=name_en, name_native=name_native,
        handle=handle, followers=followers, cohort=cohort,
    )


def percentile(sorted_values: list, pct: float):
    """Nearest-rank percentile, no numpy dependency. sorted_values must
    already be sorted ascending."""
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, math.ceil(pct * len(sorted_values)) - 1)
    return sorted_values[max(idx, 0)]


def compute_distribution(counts: list[int]) -> dict:
    """counts: valid-affiliation count per talent. median / p90 / max /
    pct_zero, as specced."""
    if not counts:
        return {"n": 0, "median": None, "p90": None, "max": None, "pct_zero": None}
    ordered = sorted(counts)
    return {
        "n": len(counts),
        "median": statistics.median(counts),
        "p90": percentile(ordered, 0.9),
        "max": ordered[-1],
        "pct_zero": round(100 * sum(1 for c in counts if c == 0) / len(counts), 1),
    }


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

CALIBRATION_POOL_QUERY = """
    SELECT id, name_en, name_native, instagram_username, instagram_followers
    FROM talents_search
    WHERE instagram_username IS NOT NULL
    ORDER BY instagram_followers DESC NULLS LAST, name_en
"""


def fetch_calibration_pool(cur) -> list[tuple]:
    cur.execute(CALIBRATION_POOL_QUERY)
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _print_set(calibration_set: list[CalibrationTalent]) -> None:
    for cohort in ("top10", "bottom_random10"):
        rows = [c for c in calibration_set if c.cohort == cohort]
        print(f"\n  {cohort} ({len(rows)}):")
        for c in rows:
            native = f" / {c.name_native}" if c.name_native else ""
            followers = f"{c.followers:,}" if c.followers is not None else "—"
            print(f"    {c.name_en:28s}{native:20s} @{c.handle:22s} {followers:>12s} followers")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="store_true",
                        help="actually call the provider and score; default is set-preview only, no spend")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"random seed for the bottom-half sample (default {DEFAULT_SEED})")
    parser.add_argument("--yes", action="store_true", help="skip the spend confirmation prompt")
    parser.add_argument("--model", default=None, help="override the Anthropic model id")
    args = parser.parse_args()

    import sys
    sys.stdout.reconfigure(line_buffering=True)

    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        return

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    pool = fetch_calibration_pool(cur)
    calibration_set = build_calibration_set(pool, seed=args.seed)

    print(f"{len(pool)} talents with an Instagram handle in the pool.")
    print(f"Calibration set (seed={args.seed}):")
    _print_set(calibration_set)

    if not args.run:
        print("\nPreview only — no provider calls made. Re-run with --run once this set is approved.")
        conn.close()
        return

    if not args.yes:
        answer = input(
            f"\nAbout to research {len(calibration_set)} talents via the Anthropic API "
            f"(billed web search + generation per talent). Continue? [y/N] "
        )
        if answer.strip().lower() != "y":
            print("Aborted.")
            conn.close()
            return

    rows = fetch_talent_rows_by_id(cur, [c.talent_id for c in calibration_set])
    cache_cur = conn.cursor()
    cache = BrandCache(cache_cur)  # read-only use here: preview_resolve() never writes
    cur.close()

    talents = build_talent_queries(rows)
    order = {c.talent_id: i for i, c in enumerate(calibration_set)}
    talents.sort(key=lambda t: order[t.talent_id])
    cohort_by_id = {c.talent_id: c.cohort for c in calibration_set}
    followers_by_id = {c.talent_id: c.followers for c in calibration_set}

    from .prompt import DEFAULT_MODEL
    from .providers.anthropic_web_search import AnthropicBrandProvider

    provider = AnthropicBrandProvider(model=args.model or DEFAULT_MODEL)

    print(f"\nResearching {len(talents)} talents...")
    start = time.monotonic()
    results = provider.research(talents)

    per_talent_report = []
    counts_overall, counts_by_cohort = [], {"top10": [], "bottom_random10": []}

    for result in results:
        talent = next(t for t in talents if t.talent_id == result.talent_id)
        valid, rejected = validate_candidates(result)
        cohort = cohort_by_id[result.talent_id]

        affiliations = []
        for c in valid:
            resolution = cache.preview_resolve(c.brand_name)
            affiliations.append({
                "brand_name": c.brand_name, "brand_resolution": resolution.action,
                "status": c.status, "confidence": c.confidence,
                "evidence_year": c.evidence_year, "source_url": c.source_url,
                "evidence_note": c.evidence_note,
            })

        per_talent_report.append({
            "talent_id": result.talent_id, "name_en": talent.name_en, "name_native": talent.name_native,
            "cohort": cohort, "instagram_followers": followers_by_id[result.talent_id],
            "provider_status": result.status, "provider_error": result.error_message,
            "affiliations_found": len(valid), "affiliations": affiliations,
            "rejected": rejected,
        })
        counts_overall.append(len(valid))
        counts_by_cohort[cohort].append(len(valid))

        native = f" / {talent.name_native}" if talent.name_native else ""
        print(f"  {talent.name_en}{native}: {len(valid)} valid, {len(rejected)} rejected"
              + (f" (provider error: {result.error_message})" if result.status != "ok" else ""))

    elapsed = time.monotonic() - start

    dist_overall = compute_distribution(counts_overall)
    dist_top10 = compute_distribution(counts_by_cohort["top10"])
    dist_bottom = compute_distribution(counts_by_cohort["bottom_random10"])

    print("\nDistribution of affiliations found per talent")
    print(f"  Overall (n={dist_overall['n']}) : median {dist_overall['median']}, "
          f"p90 {dist_overall['p90']}, max {dist_overall['max']}, "
          f"{dist_overall['pct_zero']}% with zero")
    print(f"  top10   (n={dist_top10['n']})  : median {dist_top10['median']}, "
          f"p90 {dist_top10['p90']}, max {dist_top10['max']}, "
          f"{dist_top10['pct_zero']}% with zero")
    print(f"  bottom_random10 (n={dist_bottom['n']}): median {dist_bottom['median']}, "
          f"p90 {dist_bottom['p90']}, max {dist_bottom['max']}, "
          f"{dist_bottom['pct_zero']}% with zero")
    print(f"\nElapsed: {elapsed:.1f}s")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    report_path = LOG_DIR / f"calibration_{ts}.json"
    raw_path = LOG_DIR / f"calibration_raw_{ts}.json"

    write_log_atomic(report_path, {
        "seed": args.seed,
        "distribution": {"overall": dist_overall, "top10": dist_top10, "bottom_random10": dist_bottom},
        "talents": per_talent_report,
    })
    write_log_atomic(raw_path, {r.talent_id: r.raw for r in results})

    cache_cur.close()
    conn.close()

    print(f"\nReport : {report_path}")
    print(f"Raw responses : {raw_path}")
    print("\nHand-score this report before running enrichment.brands.run for real.")


if __name__ == "__main__":
    main()
