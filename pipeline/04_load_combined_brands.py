"""
04_load_combined_brands.py — load brand affiliations from combined enrichment batches.

Reads the batch result files in enrichment/combined/results/batch_*.json,
extracts brand affiliations, maps wikidata_id → talent_id (UUID) from
Supabase, converts to the format expected by the brands pipeline, and
loads them using the same validation/normalization/dedup logic as
load_manual_research.py.

Prerequisites:
  - Base talent data must already be loaded (run 03a_load_cleaned.py first)
    so that wikidata_id → talent_id lookups succeed.
  - DATABASE_URL must be set in .env

Run:
  python 04_load_combined_brands.py --dry-run     # validate + report, no DB writes
  python 04_load_combined_brands.py               # load brands into Supabase
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BATCH_DIR = SCRIPT_DIR / "enrichment" / "combined" / "results"


def load_batches() -> list[dict]:
    """Read all batch_*.json files and return flat list of talent records.

    Most batch files are a plain JSON list of talent records. A few are
    wrapped in a status dict instead:
      - {"_batch_metadata": ..., "results": [...]}           (normal, wrapped)
      - {"status": "INCOMPLETE", "partial_results": [...]}   (partial batch)
      - {"status": "failed", ...}                             (no results at all)
    """
    all_records = []
    for fp in sorted(BATCH_DIR.glob("batch_*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("results") or data.get("partial_results")
            if records is None:
                print(f"  WARNING: {fp.name} has no results (status={data.get('status')!r}) — skipping")
                continue
            print(f"  NOTE: {fp.name} is a {data.get('status', 'wrapped')} batch — "
                  f"using {len(records)} of {data.get('talents_total', data.get('talent_count', '?'))} records")
        else:
            print(f"  WARNING: {fp.name} has unexpected top-level type {type(data).__name__} — skipping")
            continue
        all_records.extend(records)
    return all_records


def build_qid_to_tid(conn) -> dict[str, str]:
    """Build wikidata_id → talent UUID mapping from the DB."""
    cur = conn.cursor()
    cur.execute("SELECT wikidata_id, id FROM talents WHERE wikidata_id IS NOT NULL")
    mapping = {row[0]: str(row[1]) for row in cur.fetchall()}
    cur.close()
    return mapping


def convert_to_manual_format(records: list[dict], qid_to_tid: dict) -> list[dict]:
    """Convert combined batch records to load_manual_research.py's input format.

    Input per record:
        { wikidata_id, name_en, brands: [{brand_name, source_url, evidence_year,
          confidence, evidence_note}], brands_searched, ... }

    Output per record:
        { talent_id (UUID), name_en, affiliations: [{brand_name, status,
          source_url, evidence_year, confidence, evidence_note}] }
    """
    converted = []
    skipped_no_tid = 0
    skipped_no_brands = 0

    for r in records:
        qid = r.get("wikidata_id")
        if not qid:
            continue

        tid = qid_to_tid.get(qid)
        if not tid:
            skipped_no_tid += 1
            continue

        brands = r.get("brands") or []
        # Include talents with no brands so brands_checked_at gets stamped
        affiliations = []
        for b in brands:
            affiliations.append({
                "brand_name":    b.get("brand_name", ""),
                "status":        b.get("status", "current"),
                "source_url":    b.get("source_url", ""),
                "evidence_year": b.get("evidence_year"),
                "confidence":    b.get("confidence", ""),
                "evidence_note": b.get("evidence_note"),
            })

        converted.append({
            "talent_id":    tid,
            "name_en":      r.get("name_en", ""),
            "affiliations": affiliations,
        })

        if not affiliations:
            skipped_no_brands += 1

    return converted, skipped_no_tid, skipped_no_brands


def main():
    parser = argparse.ArgumentParser(
        description="Load brand affiliations from combined enrichment batches into Supabase."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and report only — no DB writes")
    args = parser.parse_args()

    sys.stdout.reconfigure(line_buffering=True)

    # --- Load .env ---
    try:
        from dotenv import load_dotenv
        load_dotenv(SCRIPT_DIR / ".env")
    except ImportError:
        pass

    import psycopg2

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set (.env)")
        return

    # --- Read batch files ---
    records = load_batches()
    total_with_brands = sum(1 for r in records if r.get("brands"))
    total_brands = sum(len(r.get("brands", [])) for r in records)
    print(f"Read {len(records)} records from batch files")
    print(f"  {total_with_brands} talents have brand affiliations ({total_brands} total)")

    # --- Map wikidata_id → talent_id ---
    conn = psycopg2.connect(db_url)
    qid_to_tid = build_qid_to_tid(conn)
    print(f"  {len(qid_to_tid)} talents in DB with wikidata_id")

    converted, skipped_no_tid, skipped_no_brands = convert_to_manual_format(records, qid_to_tid)
    print(f"  Converted {len(converted)} records ({skipped_no_tid} skipped — not in DB)")

    if not converted:
        print("Nothing to load.")
        conn.close()
        return

    # --- Write intermediate JSON (useful for debugging) ---
    out_path = SCRIPT_DIR / "enrichment" / "combined" / "brands_for_load.json"
    out_path.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Wrote {out_path.relative_to(SCRIPT_DIR)}")

    if args.dry_run:
        # Just report counts
        with_aff = sum(1 for c in converted if c["affiliations"])
        total_aff = sum(len(c["affiliations"]) for c in converted)
        print(f"\nDRY RUN summary:")
        print(f"  Talents to process : {len(converted)}")
        print(f"  With affiliations  : {with_aff}")
        print(f"  Total affiliations : {total_aff}")
        print(f"  Skipped (no DB row): {skipped_no_tid}")
        print(f"  brands_for_load.json written for inspection.")
        conn.close()
        return

    # --- Load via the brands pipeline ---
    from enrichment.brands.normalize import BrandCache
    from enrichment.brands.provider_base import AffiliationCandidate, BrandResearchResult
    from enrichment.brands.urls import canonicalize_url
    from enrichment.brands.run import (
        MARK_CHECKED_STMT,
        resolve_and_dedupe,
        validate_candidates,
        write_rows,
    )

    all_talent_ids = [c["talent_id"] for c in converted]

    # Build BrandResearchResult objects
    results = []
    for entry in converted:
        candidates = [
            AffiliationCandidate(
                brand_name=a["brand_name"],
                status=a.get("status", ""),
                source_url=a.get("source_url", ""),
                evidence_year=a.get("evidence_year"),
                confidence=a.get("confidence", ""),
                evidence_note=a.get("evidence_note"),
            )
            for a in entry["affiliations"]
        ]

        # For combined enrichment, source_urls are from web search — mark as observed
        observed = frozenset(
            canonicalize_url(a.get("source_url", ""))
            for a in entry["affiliations"]
            if a.get("source_url")
        )

        results.append(BrandResearchResult(
            talent_id=entry["talent_id"],
            affiliations=candidates,
            status="ok",
            observed_urls=observed,
        ))

    # Validate and write
    cache_cur = conn.cursor()
    cache = BrandCache(cache_cur)

    total_written = 0
    total_skipped = 0
    total_rejected = 0

    write_cur = conn.cursor()
    for i, result in enumerate(results):
        name = converted[i]["name_en"]
        valid, rejected = validate_candidates(result)
        total_rejected += len(rejected)

        if rejected:
            for r in rejected:
                print(f"  REJECTED {name}: {r['brand_name']} — {r['reasons']}")

        if valid:
            kept, dropped = resolve_and_dedupe(result.talent_id, valid, cache)
            written, skipped = write_rows(write_cur, kept)
            total_written += written
            total_skipped += skipped

        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  [{i+1}/{len(results)}] committed — written {total_written}", flush=True)

    # Mark all talents as brands-checked
    write_cur.execute(MARK_CHECKED_STMT, {"talent_ids": all_talent_ids})
    conn.commit()
    write_cur.close()
    cache_cur.close()
    conn.close()

    print(f"\nSummary")
    print(f"  Talents processed    : {len(results)}")
    print(f"  Affiliations written : {total_written}")
    print(f"  Skipped (dup/manual) : {total_skipped}")
    print(f"  Rejected (validation): {total_rejected}")
    print(f"  New brands created   : {len(cache.newly_created)}")
    print(f"  brands_checked_at    : stamped for all {len(all_talent_ids)} talents")


if __name__ == "__main__":
    main()
