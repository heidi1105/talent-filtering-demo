"""
Brand-affiliation enrichment
=============================
For every individual talent with a Wikidata id that hasn't been checked yet
(brands_checked_at IS NULL), researches current/past commercial brand
affiliations via web search and writes verified ones to talent_brands.

Usage
-----
    python -m enrichment.brands.run --dry-run            # read + build queries + report only
    python -m enrichment.brands.run --limit 10            # smoke test a handful of talents
    python -m enrichment.brands.run --limit 10 --yes       # skip the cost-guard prompt

Requires DATABASE_URL, ANTHROPIC_API_KEY (.env).

IMPORTANT — read before a full run: this pipeline is open-ended web
research, not a deterministic lookup (contrast enrichment/followers/). The
provider can hallucinate a plausible brand deal with a plausible-looking
URL. Two independent guards stand between a model claim and a database
write, both enforced in validate_candidates() below, not just in the
prompt:
  1. source_url and evidence_year are both required — see schema.sql's
     talent_brands_evidence_year_check.
  2. source_url must exactly match a URL the web_search tool actually
     returned during that talent's research call (see providers/
     anthropic_web_search.py's observed_urls) — a citation the model never
     retrieved is dropped, not written.
A row failing either guard is logged to logs/failures_<ts>.json, never
silently written and never silently discarded without a trace.

Skip logic: after each batch completes, talents.brands_checked_at is set
for every talent in the batch — whether affiliations were found or not.
The candidate query filters on brands_checked_at IS NULL, so re-runs
never re-query (and re-bill) already-checked talents.

Crash safety: each batch is committed to the DB and the raw-response /
failure logs are rewritten immediately after that batch completes —
mirrors enrichment/followers/run.py.
"""

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from .normalize import BrandCache, choose_survivor
from .prompt import MIN_EVIDENCE_YEAR
from .provider_base import AffiliationCandidate, BrandResearchResult, TalentQuery
from .urls import canonicalize_url

BATCH_SIZE = 10                # small: each talent is its own paid web-search call
COST_GUARD_THRESHOLD = 20
LOG_DIR = Path(__file__).parent / "logs"


# ---------------------------------------------------------------------------
# Pure logic (no DB / network) — unit tested directly.
# ---------------------------------------------------------------------------

def build_talent_queries(rows: list[tuple]) -> list[TalentQuery]:
    """rows: (talent_id, name_en, name_native, other_names, group_name,
    occupation, nationality) tuples from talents."""
    queries = []
    for talent_id, name_en, name_native, other_names, group_name, occupation, nationality in rows:
        queries.append(TalentQuery(
            talent_id=str(talent_id), name_en=name_en, name_native=name_native,
            other_names=list(other_names or []), group_name=group_name,
            occupation=list(occupation or []), nationality=nationality,
        ))
    return queries


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def validate_candidates(result: BrandResearchResult) -> tuple[list[AffiliationCandidate], list[dict]]:
    """Applies the hard ingest rules to one talent's provider result.

    Returns (valid, rejected). `valid` entries still carry a raw brand_name
    string — brand_id resolution happens separately in resolve_and_dedupe()
    since it needs the DB-backed BrandCache. `rejected` entries always carry
    a `reasons` list (or a single provider-level reason) so the failure log
    is diagnostic, not just a discard count.
    """
    if result.status != "ok":
        return [], [{
            "talent_id": result.talent_id, "brand_name": None, "source_url": None,
            "reasons": ["provider_error"], "detail": result.error_message,
        }]

    valid, rejected = [], []
    for c in result.affiliations:
        reasons = []
        if not c.brand_name or not c.brand_name.strip():
            reasons.append("missing_brand_name")
        if c.status not in ("current", "past"):
            reasons.append("invalid_status")
        if c.confidence not in ("high", "medium", "low"):
            reasons.append("invalid_confidence")
        if not c.source_url:
            reasons.append("missing_source_url")
        if c.evidence_year is None:
            reasons.append("missing_evidence_year")
        elif c.evidence_year < MIN_EVIDENCE_YEAR:
            reasons.append("evidence_year_too_old")
        if c.source_url and canonicalize_url(c.source_url) not in result.observed_urls:
            reasons.append("url_not_grounded")

        if reasons:
            rejected.append({
                "talent_id": result.talent_id, "brand_name": c.brand_name,
                "source_url": c.source_url, "reasons": reasons, "detail": None,
            })
        else:
            valid.append(c)
    return valid, rejected


def dedupe_resolved_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """rows: one talent's candidates, each already resolved to a brand_id.
    Collapses multiple candidates landing on the same brand_id (e.g. the
    model reported "Chanel" and "CHANEL" as if separate) via choose_survivor,
    keeping the stronger one. Returns (kept, dropped)."""
    kept_by_brand: dict[str, dict] = {}
    dropped = []
    for row in rows:
        bid = row["brand_id"]
        if bid not in kept_by_brand:
            kept_by_brand[bid] = row
            continue
        existing = kept_by_brand[bid]
        if choose_survivor(row, existing) == "from":
            dropped.append(existing)
            kept_by_brand[bid] = row
        else:
            dropped.append(row)
    return list(kept_by_brand.values()), dropped


# ---------------------------------------------------------------------------
# DB glue
# ---------------------------------------------------------------------------

CANDIDATE_QUERY = """
    SELECT t.id, t.name_en, t.name_native, t.other_names, t.group_name, t.occupation, t.nationality
    FROM talents t
    WHERE t.wikidata_id IS NOT NULL
      AND t.birth_year IS NOT NULL   -- individuals only; groups run as a separate pass (Track D)
      AND t.brands_checked_at IS NULL
    ORDER BY t.name_en
    LIMIT %(limit)s
"""

MARK_CHECKED_STMT = """
    UPDATE talents SET brands_checked_at = now()
    WHERE id = ANY(%(talent_ids)s::uuid[])
"""

UPSERT_STMT = """
    INSERT INTO talent_brands
        (talent_id, brand_id, status, source_url, confidence, evidence_year, extraction_method, raw)
    VALUES (%(talent_id)s, %(brand_id)s, %(status)s, %(source_url)s, %(confidence)s,
            %(evidence_year)s, 'ai', %(raw)s)
    ON CONFLICT (talent_id, brand_id) DO UPDATE SET
        status = EXCLUDED.status,
        source_url = EXCLUDED.source_url,
        confidence = EXCLUDED.confidence,
        evidence_year = EXCLUDED.evidence_year,
        extraction_method = 'ai',
        extracted_at = now(),
        raw = EXCLUDED.raw
    -- Never let a re-run clobber a manually-curated row (e.g. an owner
    -- correction, or a manual 'not signed'). A 0 rowcount here means the
    -- existing row was left alone, not that the write failed.
    WHERE talent_brands.extraction_method = 'ai'
"""


TALENTS_BY_ID_QUERY = """
    SELECT t.id, t.name_en, t.name_native, t.other_names, t.group_name, t.occupation, t.nationality
    FROM talents t
    WHERE t.id = ANY(%(talent_ids)s::uuid[])
"""


def fetch_candidate_rows(cur, limit: int | None) -> list[tuple]:
    cur.execute(CANDIDATE_QUERY, {"limit": limit})
    return cur.fetchall()


def fetch_talent_rows_by_id(cur, talent_ids: list[str]) -> list[tuple]:
    """Used by calibrate.py, which picks specific talents rather than going
    through the NOT-EXISTS candidate gate above."""
    cur.execute(TALENTS_BY_ID_QUERY, {"talent_ids": talent_ids})
    return cur.fetchall()


def resolve_and_dedupe(talent_id: str, valid: list[AffiliationCandidate], cache: BrandCache) -> tuple[list[dict], list[dict]]:
    """Resolves each candidate's brand_name to a brand_id (creating new
    brand rows as needed) and dedupes within this talent. Returns
    (rows_to_write, dropped_duplicates)."""
    resolved = []
    for c in valid:
        brand_id = cache.resolve(c.brand_name)
        resolved.append({
            "talent_id": talent_id, "brand_id": brand_id, "status": c.status,
            "source_url": c.source_url, "confidence": c.confidence,
            "evidence_year": c.evidence_year,
            "raw": {"brand_name_as_reported": c.brand_name, "evidence_note": c.evidence_note},
        })
    return dedupe_resolved_rows(resolved)


def write_rows(cur, rows: list[dict]) -> tuple[int, int]:
    """Returns (written, skipped_manual) — see UPSERT_STMT's WHERE guard."""
    from psycopg2.extras import Json

    written = skipped_manual = 0
    for row in rows:
        cur.execute(UPSERT_STMT, {**row, "raw": Json(row["raw"])})
        if cur.rowcount:
            written += 1
        else:
            skipped_manual += 1
    return written, skipped_manual


def write_log_atomic(path: Path, data) -> None:
    """Write via a temp file + rename so a crash mid-write can't corrupt the
    previous, already-flushed version of the log."""
    import json
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    tmp.replace(path)


@dataclass
class RunReport:
    written: int = 0
    skipped_manual: int = 0
    rejected: list = None
    provider_errors: int = 0

    def __post_init__(self):
        if self.rejected is None:
            self.rejected = []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="read + build queries + report only; no provider calls, no DB writes")
    parser.add_argument("--limit", type=int, default=None, help="process at most N talents")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"talents per DB-commit checkpoint (default {BATCH_SIZE})")
    parser.add_argument("--yes", action="store_true", help="skip the cost-guard confirmation prompt")
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
    rows = fetch_candidate_rows(cur, args.limit)
    cur.close()

    print(f"{len(rows)} candidate talents (wikidata set, individual, no AI brand rows yet"
          f"{f', limit {args.limit}' if args.limit else ''})")

    talents = build_talent_queries(rows)

    if args.dry_run:
        print("\nDRY RUN — no provider calls, no DB writes.")
        for t in talents[:20]:
            native = f" / {t.name_native}" if t.name_native else ""
            print(f"  {t.name_en}{native}")
        if len(talents) > 20:
            print(f"  ... and {len(talents) - 20} more")
        conn.close()
        return

    if not talents:
        print("Nothing to research.")
        conn.close()
        return

    if len(talents) > COST_GUARD_THRESHOLD and not args.yes:
        answer = input(
            f"\nAbout to research {len(talents)} talents via the Anthropic API "
            f"(billed web search + generation per talent). Continue? [y/N] "
        )
        if answer.strip().lower() != "y":
            print("Aborted.")
            conn.close()
            return

    from .providers.anthropic_web_search import AnthropicBrandProvider
    from .prompt import DEFAULT_MODEL

    provider = AnthropicBrandProvider(model=args.model or DEFAULT_MODEL)
    cache_cur = conn.cursor()
    cache = BrandCache(cache_cur)
    start = time.monotonic()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    failures_log_path = LOG_DIR / f"failures_{ts}.json"
    raw_log_path = LOG_DIR / f"raw_{ts}.json"
    new_brands_log_path = LOG_DIR / f"new_brands_{ts}.json"

    report = RunReport()
    raw_responses: dict[str, dict] = {}
    batches = list(chunked(talents, args.batch_size))

    try:
        for i, batch in enumerate(batches, 1):
            print(f"  Batch {i}/{len(batches)}: researching {len(batch)} talents")
            for t in batch:
                print(f"    - {t.name_en}" + (f" / {t.name_native}" if t.name_native else ""))

            results = provider.research(batch)
            batch_rows = []
            for result in results:
                raw_responses[result.talent_id] = result.raw
                valid, rejected = validate_candidates(result)
                report.rejected.extend(rejected)
                if result.status != "ok":
                    report.provider_errors += 1

                kept, dropped = resolve_and_dedupe(result.talent_id, valid, cache)
                for d in dropped:
                    report.rejected.append({
                        "talent_id": result.talent_id, "brand_name": d["raw"]["brand_name_as_reported"],
                        "source_url": d["source_url"], "reasons": ["duplicate_in_batch"], "detail": None,
                    })
                batch_rows.extend(kept)

                name = next(t.name_en for t in batch if t.talent_id == result.talent_id)
                print(f"    {name:30s} {len(kept)} affiliation(s), {len(rejected) + len(dropped)} rejected")

            write_cur = conn.cursor()
            written, skipped_manual = write_rows(write_cur, batch_rows)
            # Mark all talents in this batch as checked — even those with 0 affiliations
            batch_ids = [t.talent_id for t in batch]
            write_cur.execute(MARK_CHECKED_STMT, {"talent_ids": batch_ids})
            conn.commit()
            write_cur.close()

            report.written += written
            report.skipped_manual += skipped_manual

            print(f"    -> {written} written, {skipped_manual} skipped (manual row present) "
                  f"(running total: {report.written} written, {len(report.rejected)} rejected)")

            write_log_atomic(failures_log_path, {
                "batches_completed": i, "batches_total": len(batches),
                "written_so_far": report.written, "skipped_manual": report.skipped_manual,
                "provider_errors": report.provider_errors, "rejected": report.rejected,
            })
            write_log_atomic(raw_log_path, raw_responses)
            write_log_atomic(new_brands_log_path, cache.newly_created)
    except KeyboardInterrupt:
        cache_cur.close()
        conn.close()
        print(f"\nInterrupted. {report.written} rows already committed; "
              f"progress logs saved under {LOG_DIR}.")
        return

    cache_cur.close()
    conn.close()
    elapsed = time.monotonic() - start

    print("\nSummary")
    print(f"  Talents researched : {len(talents)}")
    print(f"  Affiliations written: {report.written}")
    print(f"  Skipped (manual row): {report.skipped_manual}")
    print(f"  Rejected candidates : {len(report.rejected)}")
    print(f"  Provider errors      : {report.provider_errors}")
    print(f"  New brands created   : {len(cache.newly_created)}")
    print(f"  Elapsed              : {elapsed:.1f}s")
    print(f"  Failure log          : {failures_log_path}")
    print(f"  Raw response log     : {raw_log_path}")
    print(f"  New brands log       : {new_brands_log_path}")


if __name__ == "__main__":
    main()
