"""
05_apply_enrichment.py — apply enriched data from batch results back to seed files.

Reads all enrichment/combined/results/batch_*.json files, extracts the
`enriched` dict from each talent result, and merges corrections into
seed/wikidata_raw_cleaned.json and regenerates seed/talents_seed.json.

Fields in `enriched` overwrite existing values ONLY when the existing value
is null/empty. To force-overwrite (e.g. fix a wrong nationality), use --force.

Run:
  python 05_apply_enrichment.py --dry-run        # preview changes, no writes
  python 05_apply_enrichment.py                   # apply corrections
  python 05_apply_enrichment.py --force           # overwrite non-null fields too
  python 05_apply_enrichment.py --batch-dir DIR   # custom batch directory

No network, no DB. Operates only on local JSON files.
"""
import argparse
import glob
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import seedlib as S

SEED = S.SEED_DIR
BATCH_DIR = Path(__file__).resolve().parent / "enrichment" / "combined" / "results"

# Fields that enrichment can update
ENRICHABLE_FIELDS = [
    "name_en", "name_native", "birth_year", "gender", "nationality",
    "debut_year", "languages_spoken", "other_names", "active_countries",
    "photo_url", "instagram", "twitter", "youtube", "group_name",
]

# Fields where enrichment value is a list (merge, don't replace)
LIST_FIELDS = {"languages_spoken", "other_names", "active_countries"}


def load_all_batches(batch_dir: Path) -> dict[str, dict]:
    """Load all batch results, return {wikidata_id: enriched_dict}."""
    enrichments: dict[str, dict] = {}
    files_read = 0
    entries_read = 0

    for fp in sorted(batch_dir.glob("batch_*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))

        # Handle different file formats
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # batch_002 style: {results: [...]}
            if "results" in data and isinstance(data["results"], list):
                records = data["results"]
            # partial style: {partial_results: [...]}
            elif "partial_results" in data and isinstance(data["partial_results"], list):
                records = data["partial_results"]
            # failed batch: no records
            elif data.get("status") == "failed":
                continue

        files_read += 1
        for entry in records:
            if not isinstance(entry, dict):
                continue
            entries_read += 1
            qid = entry.get("wikidata_id")
            enriched = entry.get("enriched", {})
            if qid and isinstance(enriched, dict) and enriched:
                # If same QID appears in multiple batches, later batch wins
                if qid in enrichments:
                    enrichments[qid].update(enriched)
                else:
                    enrichments[qid] = dict(enriched)

    print(f"Read {files_read} batch files, {entries_read} entries, "
          f"{len(enrichments)} with enriched data")
    return enrichments


def is_empty(val):
    """Check if a value is effectively empty."""
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, list) and len(val) == 0:
        return True
    return False


def apply_enrichments(records: list[dict], enrichments: dict[str, dict],
                      force: bool = False) -> tuple[int, dict[str, int]]:
    """Apply enriched data to records in place. Returns (count, field_stats)."""
    idx = {r["wikidata_id"]: r for r in records}
    applied = 0
    field_stats: dict[str, int] = Counter()
    changes_log: list[dict] = []

    for qid, enriched in enrichments.items():
        rec = idx.get(qid)
        if not rec:
            continue

        changed = False
        for field, new_val in enriched.items():
            if field not in ENRICHABLE_FIELDS:
                continue
            if is_empty(new_val):
                continue

            old_val = rec.get(field)

            if field in LIST_FIELDS:
                # Merge lists: add new items not already present
                existing = old_val if isinstance(old_val, list) else []
                if isinstance(new_val, list):
                    merged = list(existing)
                    for item in new_val:
                        if item not in merged:
                            merged.append(item)
                    if merged != existing:
                        rec[field] = merged
                        field_stats[field] += 1
                        changed = True
            elif force or is_empty(old_val):
                rec[field] = new_val
                field_stats[field] += 1
                changed = True

        if changed:
            applied += 1

    return applied, dict(field_stats)


def main():
    ap = argparse.ArgumentParser(description="Apply enrichment corrections to seed files")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview changes without writing")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing non-null values too")
    ap.add_argument("--batch-dir", type=str, default=None,
                    help="Custom batch results directory")
    args = ap.parse_args()

    batch_dir = Path(args.batch_dir) if args.batch_dir else BATCH_DIR

    # Load enrichments from all batches
    enrichments = load_all_batches(batch_dir)
    if not enrichments:
        print("No enriched data found in batch files.")
        return

    # Field distribution
    print("\nEnrichment field distribution:")
    field_counts = Counter()
    for e in enrichments.values():
        for k in e:
            if k in ENRICHABLE_FIELDS:
                field_counts[k] += 1
    for k, v in field_counts.most_common():
        print(f"  {k}: {v}")

    # Load cleaned file
    cleaned_path = SEED / "wikidata_raw_cleaned.json"
    cleaned = json.loads(cleaned_path.read_text(encoding="utf-8"))
    print(f"\nLoaded {len(cleaned)} records from wikidata_raw_cleaned.json")

    # Apply to cleaned
    applied, field_stats = apply_enrichments(cleaned, enrichments, force=args.force)
    print(f"\nApplied corrections to {applied} records in wikidata_raw_cleaned.json:")
    for k, v in sorted(field_stats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return

    # Backup cleaned
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = SEED / f"wikidata_raw_cleaned.backup_pre_enrich_{ts}.json"
    shutil.copy2(cleaned_path, backup)
    print(f"\nBackup: {backup.name}")

    # Write updated cleaned
    cleaned_path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Written: wikidata_raw_cleaned.json ({len(cleaned)} records)")

    # Regenerate talents_seed.json via 02a logic
    qid2canon = S.load_occupation_closures()
    seen: dict[str, dict] = {}
    dropped = 0
    for r in cleaned:
        occ = S.normalize_occupations(
            r.get("occupation_qids", []),
            qid2canon,
            r.get("occupation_labels", {}),
        )
        if not occ:
            # Group members often lack Wikidata occupation tags — default to Singer
            if r.get("group_name"):
                occ = ["Singer"]
            else:
                dropped += 1
                continue
        if not r.get("name_en") and not r.get("name_native"):
            continue
        nn = r.get("name_native") or ""
        nn = re.sub(r'\s*\(.*?\)\s*$', '', nn).strip() or None
        seen[r["wikidata_id"]] = {
            "wikidata_id":      r["wikidata_id"],
            "name_en":          r.get("name_en"),
            "name_native":      nn,
            "birth_year":       r.get("birth_year"),
            "gender":           r.get("gender"),
            "nationality":      r.get("nationality"),
            "occupation":       occ,
            "group_name":       r.get("group_name"),
            "debut_year":       r.get("debut_year"),
            "languages_spoken": r.get("languages_spoken") or [],
            "other_names":      r.get("other_names") or [],
            "photo_url":        r.get("photo_url"),
            "instagram":        r.get("instagram"),
            "twitter":          r.get("twitter"),
            "youtube":          r.get("youtube"),
            "active_countries": r.get("active_countries") or [],
            "remarks":          r.get("remarks"),
        }

    out = list(seen.values())
    (SEED / "talents_seed.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Written: talents_seed.json ({len(out)} records, {dropped} dropped)")

    # Save apply report
    report = {
        "applied_to": applied,
        "field_stats": field_stats,
        "force": args.force,
        "total_cleaned": len(cleaned),
        "total_seed": len(out),
        "dropped_no_occ": dropped,
        "batch_files_read": len(list(batch_dir.glob("batch_*.json"))),
        "enrichments_available": len(enrichments),
        "applied_at": datetime.now().isoformat(),
    }
    report_path = SEED / f"enrichment_apply_report_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {report_path.name}")


if __name__ == "__main__":
    main()
