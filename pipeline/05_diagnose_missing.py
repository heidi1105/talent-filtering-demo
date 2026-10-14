"""
Stage 5 (diagnostic only) — Why are the "not found" talents missing?
====================================================================
READ-ONLY. Touches no database and changes no enrichment logic. It re-runs
the Wikidata search for every record in wikidata_enrich_missing.json and
reports *why* each one failed, so we can tell apart:

  - records that are genuinely absent from Wikidata (need a manual / KR-wiki path)
  - records that ARE on Wikidata but were rejected by the current strict gate
    (recoverable by loosening the matcher)

It deliberately searches WIDER and judges LOOSER than 04_wikidata_enrich.py,
purely to surface candidates — it never writes anything.

Outcome categories per record:
  no_candidates      search returned nothing in either language (likely truly absent)
  no_human           candidates exist but none are P31=human (homonym pages, songs, etc.)
  matchable_strict   a candidate would already pass the CURRENT strict rules
                     (i.e. this row is probably a STALE not_found — just re-run
                      04 with --retry-not-found)
  birthyear_conflict human candidate found, but WD birth year != DB birth year
                     (shows both; recoverable via +/-1 tolerance or fixing a
                      bad DB year)
  matchable_loosened human candidate that passes the PROPOSED balanced rules
                     (>=1yr tolerance / ignore implausible DB year / wider
                      occupation vocab) but not the strict ones
  human_no_signal    human candidate with no birth year and no recognizable
                     occupation — genuinely ambiguous, needs review

Usage:
  python 05_diagnose_missing.py
  python 05_diagnose_missing.py --in wikidata_enrich_missing.json --limit 10

Output:
  console summary + diagnose_missing_report.json (full per-record detail)

Requires: pip install requests
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import requests

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
HEADERS      = {"User-Agent": "TalentDiagnostic/1.0 (internal research tool)"}
REQUEST_DELAY = 0.6
SEARCH_LIMIT  = 15          # vs 5 in the live script — surfaces deeper homonyms
PLAUSIBLE_MIN = 1940        # a DB birth_year outside this range is treated as junk
PLAUSIBLE_MAX = 2012
SCRIPT_DIR    = Path(__file__).resolve().parent

# Wider than the live script's KNOWN_OCCUPATIONS — these are the terms we'd add
# in the balanced loosening. Used here only to label a candidate as "plausible".
OCC_TERMS = {
    "singer", "actress", "actor", "rapper", "dancer", "model", "presenter",
    "host", "mc", "songwriter", "producer", "director", "comedian", "youtuber",
    "influencer", "musician", "performer", "entertainer", "screenwriter",
    "businesswoman", "businessman",
    # additions:
    "idol", "k-pop", "kpop", "pop", "trot", "tarento", "television personality",
    "voice", "creator", "streamer", "trainee", "composer", "lyricist",
    "variety", "celebrity", "girl group", "boy band", "musical theatre",
}


def _api_get(params: dict, retries: int = 6) -> dict:
    wait = 8
    for attempt in range(retries):
        r = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=20)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(wait)
            wait = min(wait * 2, 120)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Wikidata API failed repeatedly (rate limit / server error)")


def search(label: str, lang: str, limit: int = SEARCH_LIMIT) -> list[dict]:
    data = _api_get({
        "action": "wbsearchentities", "search": label, "language": lang,
        "type": "item", "format": "json", "limit": limit,
    })
    return data.get("search", [])


def fetch_entity(qid: str) -> dict | None:
    data = _api_get({
        "action": "wbgetentities", "ids": qid, "format": "json",
        "props": "claims|labels", "languages": "en|ko",
    })
    e = data.get("entities", {}).get(qid)
    return e if e and "missing" not in e else None


_LABEL_CACHE: dict[str, str] = {}


def resolve_labels(qids: list[str]) -> dict[str, str]:
    uncached = [q for q in qids if q not in _LABEL_CACHE][:50]
    if uncached:
        data = _api_get({
            "action": "wbgetentities", "ids": "|".join(uncached),
            "format": "json", "props": "labels", "languages": "en",
        })
        for qid, ent in data.get("entities", {}).items():
            lbl = ent.get("labels", {}).get("en", {}).get("value", "")
            if lbl:
                _LABEL_CACHE[qid] = lbl
    return {q: _LABEL_CACHE[q] for q in qids if q in _LABEL_CACHE}


def claim_qids(entity: dict, prop: str) -> list[str]:
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        dv = c.get("mainsnak", {}).get("datavalue", {})
        if dv.get("type") == "wikibase-entityid":
            out.append(dv["value"]["id"])
    return out


def wd_birth_year(entity: dict) -> int | None:
    claims = entity.get("claims", {}).get("P569", [])
    if not claims:
        return None
    t = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
    m = re.match(r"[+-](\d{4})", t)
    return int(m.group(1)) if m else None


def is_human(entity: dict) -> bool:
    return "Q5" in claim_qids(entity, "P31")


def has_known_occupation(entity: dict) -> bool:
    occ = claim_qids(entity, "P106")
    if not occ:
        return False
    labels = resolve_labels(occ)
    time.sleep(REQUEST_DELAY)
    return any(term in lbl.lower() for lbl in labels.values() for term in OCC_TERMS)


def _has_hangul(s: str) -> bool:
    return bool(re.search(r"[가-힣]", s or ""))


def diagnose_one(rec: dict) -> dict:
    name_en = rec.get("name_en", "")
    name_native = rec.get("name_native") or ""
    db_year = rec.get("birth_year")
    db_year_plausible = bool(db_year) and PLAUSIBLE_MIN <= db_year <= PLAUSIBLE_MAX

    # Gather candidates: Korean name first (if hangul), then English.
    queries = []
    if _has_hangul(name_native):
        queries.append((name_native, "ko"))
    if name_en:
        queries.append((name_en, "en"))

    raw_hits: list[dict] = []
    seen = set()
    for label, lang in queries:
        for hit in search(label, lang):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                raw_hits.append({**hit, "_via": f"{lang}:{label}"})
        time.sleep(REQUEST_DELAY)

    if not raw_hits:
        return {**rec, "outcome": "no_candidates", "candidates": []}

    cands = []
    any_human = False
    best_strict = None
    best_loosened = None
    best_conflict = None
    best_no_signal = None

    for hit in raw_hits[:SEARCH_LIMIT]:
        ent = fetch_entity(hit["id"])
        time.sleep(REQUEST_DELAY)
        if not ent:
            continue
        human = is_human(ent)
        wy = wd_birth_year(ent)
        info = {
            "qid": hit["id"],
            "label": hit.get("label"),
            "description": hit.get("description", "")[:60],
            "via": hit["_via"],
            "human": human,
            "wd_birth_year": wy,
        }
        if not human:
            cands.append(info)
            continue
        any_human = True
        occ_ok = has_known_occupation(ent)
        info["occupation_match"] = occ_ok
        cands.append(info)

        # Strict rule (mirrors 04): both years known -> exact match; else occupation.
        if db_year and wy:
            strict_pass = (wy == db_year)
        else:
            strict_pass = occ_ok
        if strict_pass and best_strict is None:
            best_strict = info

        # Loosened (proposed balanced) rule.
        if db_year_plausible and wy:
            loose_pass = abs(wy - db_year) <= 1
        elif wy and not db_year_plausible:
            loose_pass = True            # trust WD year; our DB year is junk/missing
        else:
            loose_pass = occ_ok
        if loose_pass and best_loosened is None:
            best_loosened = info

        # Categorize fallbacks for reporting.
        if db_year and wy and wy != db_year and best_conflict is None:
            best_conflict = info
        if wy is None and not occ_ok and best_no_signal is None:
            best_no_signal = info

    if best_strict:
        outcome = "matchable_strict"        # probably a stale not_found
        chosen = best_strict
    elif best_loosened:
        outcome = "matchable_loosened"
        chosen = best_loosened
    elif best_conflict:
        outcome = "birthyear_conflict"
        chosen = best_conflict
    elif any_human and best_no_signal:
        outcome = "human_no_signal"
        chosen = best_no_signal
    elif not any_human:
        outcome = "no_human"
        chosen = None
    else:
        outcome = "human_no_signal"
        chosen = best_no_signal

    return {**rec, "outcome": outcome, "chosen": chosen, "candidates": cands}


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnose why missing talents weren't matched.")
    ap.add_argument("--in", dest="infile", default="wikidata_enrich_missing.json")
    ap.add_argument("--out", dest="outfile", default="diagnose_missing_report.json")
    ap.add_argument("--limit", type=int, help="Diagnose only the first N (for a quick test).")
    args = ap.parse_args()

    in_path = SCRIPT_DIR / args.infile
    records = json.loads(in_path.read_text(encoding="utf-8"))
    if args.limit:
        records = records[: args.limit]
    print(f"Diagnosing {len(records)} records from {in_path.name}\n")

    results = []
    for i, rec in enumerate(records, 1):
        print(f"[{i}/{len(records)}] {rec.get('name_en','')} ...", end=" ", flush=True)
        try:
            res = diagnose_one(rec)
            print(res["outcome"])
        except Exception as e:
            res = {**rec, "outcome": "diag_error", "error": str(e), "candidates": []}
            print(f"ERROR: {e}")
        results.append(res)

    out_path = SCRIPT_DIR / args.outfile
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = Counter(r["outcome"] for r in results)
    print("\n--- Diagnosis summary ---")
    order = ["matchable_strict", "matchable_loosened", "birthyear_conflict",
             "human_no_signal", "no_human", "no_candidates", "diag_error"]
    for k in order:
        if counts.get(k):
            print(f"  {k:20s}: {counts[k]}")
    for k, v in counts.items():
        if k not in order:
            print(f"  {k:20s}: {v}")

    print(f"\nRecoverable by re-running 04 (stale): {counts.get('matchable_strict', 0)}")
    print(f"Recoverable by loosening the matcher: "
          f"{counts.get('matchable_loosened', 0) + counts.get('birthyear_conflict', 0)}")
    print(f"Likely genuinely absent (KR-wiki / manual): "
          f"{counts.get('no_candidates', 0) + counts.get('no_human', 0)}")
    print(f"Ambiguous, need human review: {counts.get('human_no_signal', 0)}")
    print(f"\nFull detail written to {out_path.name}")


if __name__ == "__main__":
    main()
