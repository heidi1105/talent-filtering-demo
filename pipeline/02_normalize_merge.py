"""
02_normalize_merge.py — normalize occupations and dedupe the harvest.

Reads seed/wikidata_raw.json, maps each person's raw Wikidata occupations to
the canonical profession vocab (Actor, Singer, ... TV Host, Entertainer,
Influencer, Content Creator), dropping crew / adult-industry / mis-parse tags.
Anyone left with no talent occupation is removed. Dedupes by wikidata_id.

Output: seed/talents_seed.json
Run:  python 02_normalize_merge.py
No network, no DB.
"""
import json
from collections import Counter

import seedlib as S

SEED = S.SEED_DIR

def main():
    raw = json.loads((SEED / "wikidata_raw.json").read_text(encoding="utf-8"))
    qid2canon = S.load_occupation_closures()   # reads cache built in step 01

    seen: dict[str, dict] = {}
    dropped_no_occ = 0
    for r in raw:
        occ = S.normalize_occupations(r.get("occupation_qids", []), qid2canon,
                                      r.get("occupation_labels", {}))
        if not occ:
            dropped_no_occ += 1
            continue
        if not r.get("name_en") and not r.get("name_native"):
            continue
        seen[r["wikidata_id"]] = {
            "wikidata_id": r["wikidata_id"],
            "name_en": r.get("name_en"),
            "name_native": r.get("name_native"),
            "birth_year": r.get("birth_year"),
            "gender": r.get("gender"),
            "nationality": r.get("nationality"),
            "occupation": occ,
            "group_name": r.get("group_name"),
            "debut_year": r.get("debut_year"),
            "languages_spoken": r.get("languages_spoken") or [],
            "other_names": r.get("other_names") or [],
            "photo_url": r.get("photo_url"),
            "instagram": r.get("instagram"),
            "twitter": r.get("twitter"),
            "youtube": r.get("youtube"),
        }

    out = list(seen.values())
    (SEED / "talents_seed.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Input {len(raw)} | dropped (no talent occupation) {dropped_no_occ} | seed rows {len(out)}")
    hist = Counter(o for r in out for o in r["occupation"])
    print("Occupation distribution:")
    for k, v in hist.most_common():
        print(f"  {v:5d}  {k}")

if __name__ == "__main__":
    main()
