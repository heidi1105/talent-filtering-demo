"""
02a_normalize_cleaned.py — normalize wikidata_raw_cleaned.json for DB load.

Reads ONLY from seed/wikidata_raw_cleaned.json (the curated enrichment-merged
file). Applies occupation normalization, drops entries with no talent occupation,
dedupes by wikidata_id. Carries over active_countries and remarks.

Output: seed/talents_seed.json   (same file 03a_load_cleaned.py expects)
Run:    python 02a_normalize_cleaned.py
No network, no DB.
"""
import json
from collections import Counter

import seedlib as S

SEED = S.SEED_DIR


def main():
    cleaned_path = SEED / "wikidata_raw_cleaned.json"
    base = json.loads(cleaned_path.read_text(encoding="utf-8"))
    print(f"Reading {len(base)} entries from wikidata_raw_cleaned.json")

    qid2canon = S.load_occupation_closures()

    seen: dict[str, dict] = {}
    dropped_no_occ = 0
    for r in base:
        occ = S.normalize_occupations(
            r.get("occupation_qids", []),
            qid2canon,
            r.get("occupation_labels", {}),
        )
        if not occ:
            dropped_no_occ += 1
            continue
        if not r.get("name_en") and not r.get("name_native"):
            continue
        seen[r["wikidata_id"]] = {
            "wikidata_id":      r["wikidata_id"],
            "name_en":          r.get("name_en"),
            "name_native":      r.get("name_native"),
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
    print(f"Input {len(base)} | dropped (no talent occupation) {dropped_no_occ} "
          f"| seed rows {len(out)}")
    hist = Counter(o for r in out for o in r["occupation"])
    print("Occupation distribution:")
    for k, v in hist.most_common():
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main()
