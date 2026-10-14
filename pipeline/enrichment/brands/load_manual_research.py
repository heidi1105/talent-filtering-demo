"""
Load manually-researched brand affiliations from JSON into Supabase.

Companion to enrichment/brands/run.py — same validation, normalization,
and deduplication logic, but reads from a local JSON file instead of
calling the Anthropic API. Designed for research done in Claude Pro
conversations (or any manual source).

Usage
-----
    python -m enrichment.brands.load_manual_research research_batch.json
    python -m enrichment.brands.load_manual_research research_batch.json --dry-run

Input JSON format — a list of talent results:

    [
      {
        "talent_id": "uuid-here",
        "name_en": "Kim Tae Ri",
        "affiliations": [
          {
            "brand_name": "Chanel",
            "status": "current",
            "source_url": "https://...",
            "evidence_year": 2024,
            "confidence": "high",
            "evidence_note": "Named global ambassador in Chanel press release"
          }
        ]
      },
      {
        "talent_id": "uuid-here",
        "name_en": "Someone With No Deals",
        "affiliations": []
      }
    ]

Every talent in the file gets brands_checked_at stamped, whether they
have affiliations or not — same as run.py.

Requires DATABASE_URL (.env). No ANTHROPIC_API_KEY needed.
"""

import argparse
import json
import sys
from pathlib import Path

from .normalize import BrandCache
from .provider_base import AffiliationCandidate
from .urls import canonicalize_url
from .run import (
    MARK_CHECKED_STMT,
    UPSERT_STMT,
    dedupe_resolved_rows,
    resolve_and_dedupe,
    validate_candidates,
    write_log_atomic,
    write_rows,
)
from .provider_base import BrandResearchResult
from .prompt import MIN_EVIDENCE_YEAR


def load_json(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"ERROR: expected a JSON array, got {type(data).__name__}")
        sys.exit(1)
    return data


def json_to_results(entries: list[dict]) -> list[BrandResearchResult]:
    """Convert the manual JSON format to BrandResearchResult objects
    so we can reuse validate_candidates() and the rest of the pipeline."""
    results = []
    for entry in entries:
        talent_id = entry.get("talent_id")
        if not talent_id:
            print(f"WARNING: skipping entry with no talent_id: {entry.get('name_en', '???')}")
            continue

        candidates = [
            AffiliationCandidate(
                brand_name=a.get("brand_name", ""),
                status=a.get("status", ""),
                source_url=a.get("source_url", ""),
                evidence_year=a.get("evidence_year"),
                confidence=a.get("confidence", ""),
                evidence_note=a.get("evidence_note"),
            )
            for a in entry.get("affiliations", [])
        ]

        # For manual research, all source_urls are considered "observed"
        # (no URL grounding check — the researcher verified them)
        observed = frozenset(
            canonicalize_url(a.get("source_url", ""))
            for a in entry.get("affiliations", [])
            if a.get("source_url")
        )

        results.append(BrandResearchResult(
            talent_id=talent_id,
            affiliations=candidates,
            status="ok",
            observed_urls=observed,
        ))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load manually-researched brand affiliations from JSON into Supabase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("json_file", type=Path, help="Path to the research JSON file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and report only — no DB writes")
    args = parser.parse_args()

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

    entries = load_json(args.json_file)
    print(f"Loaded {len(entries)} talent entries from {args.json_file}")

    results = json_to_results(entries)

    # Validate
    all_valid = []
    all_rejected = []
    for result in results:
        name = next((e["name_en"] for e in entries if e.get("talent_id") == result.talent_id), result.talent_id)
        valid, rejected = validate_candidates(result)
        all_rejected.extend(rejected)

        if rejected:
            for r in rejected:
                print(f"  REJECTED {name}: {r['brand_name']} — {r['reasons']}")

        print(f"  {name}: {len(valid)} valid, {len(rejected)} rejected")
        all_valid.append((result.talent_id, valid))

    if args.dry_run:
        print(f"\nDRY RUN — {sum(len(v) for _, v in all_valid)} affiliations would be written, "
              f"{len(all_rejected)} rejected. No DB changes.")
        return

    # Write to DB
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    conn = psycopg2.connect(db_url)
    cache_cur = conn.cursor()
    cache = BrandCache(cache_cur)

    total_written = 0
    total_skipped = 0
    all_talent_ids = [r.talent_id for r in results]

    write_cur = conn.cursor()
    for talent_id, valid in all_valid:
        if not valid:
            continue
        kept, dropped = resolve_and_dedupe(talent_id, valid, cache)
        written, skipped = write_rows(write_cur, kept)
        total_written += written
        total_skipped += skipped

    # Mark all talents as checked
    write_cur.execute(MARK_CHECKED_STMT, {"talent_ids": all_talent_ids})
    conn.commit()
    write_cur.close()
    cache_cur.close()
    conn.close()

    print(f"\nSummary")
    print(f"  Talents processed  : {len(results)}")
    print(f"  Affiliations written: {total_written}")
    print(f"  Skipped (manual)    : {total_skipped}")
    print(f"  Rejected            : {len(all_rejected)}")
    print(f"  New brands created  : {len(cache.newly_created)}")
    print(f"  brands_checked_at   : stamped for all {len(all_talent_ids)} talents")


if __name__ == "__main__":
    main()
