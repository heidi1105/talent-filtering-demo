"""
01_fetch_wikidata_seed.py — harvest the Korean-talent seed universe from Wikidata.

For each occupation anchor (subclasses included via P279*), find humans who are
citizens of South Korea OR members of a South-Korean musical group, then fetch
each entity and record its raw fields (02 normalizes the occupations).

CRASH-SAFE / RESUMABLE:
  - The person-QID list is cached to seed/person_qids.json (a restart does not
    re-run the 15 discovery queries).
  - Entities are fetched 50 at a time and seed/wikidata_raw.json is rewritten
    after EVERY batch, with a [done/total] progress line.
  - Re-running skips anyone already in wikidata_raw.json, so an interrupted run
    (network drop, rate-limit, Ctrl-C) picks up where it left off.

Output: seed/wikidata_raw.json
Run:
  python 01_fetch_wikidata_seed.py             # full harvest (resumes if interrupted)
  python 01_fetch_wikidata_seed.py --limit 50  # smoke test (cap people fetched)
  python 01_fetch_wikidata_seed.py --refresh-qids   # re-run discovery queries
Requires network. No DB access.
"""
import argparse
import json
import time

import seedlib as S

SEED      = S.SEED_DIR
QIDS_FILE = SEED / "person_qids.json"
RAW_FILE  = SEED / "wikidata_raw.json"
GROUP_MAP_FILE = SEED / "group_membership.json"   # person QID → group name (P527 reverse)
BATCH     = 50

def collect_person_qids() -> list[str]:
    qids: set[str] = set()
    for anchor, canon in S.OCCUPATION_ANCHORS:
        q = f"""
        SELECT DISTINCT ?p WHERE {{
          ?p wdt:P31 wd:Q5 ; wdt:P106/wdt:P279* wd:{anchor} .
          {{ ?p wdt:P27 wd:{S.Q_SOUTH_KOREA} }}
          UNION
          {{ ?p wdt:P463 ?g . ?g wdt:P495 wd:{S.Q_SOUTH_KOREA} }}
        }}"""
        rows = S.sparql(q)
        got = {S.qid_from_uri(b["p"]["value"]) for b in rows}
        print(f"  {anchor:>11} ({canon:<15}): {len(got):5d} people", flush=True)
        qids |= got
        time.sleep(1)
    return sorted(qids)


def collect_group_member_qids() -> tuple[list[str], dict[str, str]]:
    """Find members of South Korean musical groups, regardless of individual
    P106 (occupation) claims.

    Two-pass approach for maximum coverage:
      Pass A — Korean groups: groups tagged P495/P17 = South Korea, OR subclass
               types like "South Korean boy band". Gets ALL members (incl. foreign).
      Pass B — Korean members of ANY group: catches Korean idols in multinational
               groups like (G)I-DLE even when the group itself isn't tagged as Korean.

    Uses P31/P279* for group type subclasses.
    Uses both P463 (person → group) and P527 (group → person) for membership.

    Returns:
      (sorted person QIDs, {person_qid: group_name}) — the group_name map is built
      from the SPARQL results (both P463 and P527 directions) so it works even when
      the person's own entity lacks a P463 claim.  Used as a fallback in build_row().
    """
    qids: set[str] = set()
    person_to_groups: dict[str, set[str]] = {}   # person QID → group QIDs

    def _record(rows):
        for b in rows:
            pid = S.qid_from_uri(b["p"]["value"])
            gid = S.qid_from_uri(b["g"]["value"])
            qids.add(pid)
            person_to_groups.setdefault(pid, set()).add(gid)

    # Pass A: all members of Korean groups (any nationality)
    for gtype in S.GROUP_TYPE_ANCHORS:
        q = f"""
        SELECT DISTINCT ?p ?g WHERE {{
          ?g wdt:P31/wdt:P279* wd:{gtype} .
          {{ ?g wdt:P495 wd:{S.Q_SOUTH_KOREA} }}
          UNION
          {{ ?g wdt:P17 wd:{S.Q_SOUTH_KOREA} }}
          {{ ?p wdt:P463 ?g }} UNION {{ ?g wdt:P527 ?p }}
          ?p wdt:P31 wd:Q5 .
        }}"""
        rows = S.sparql(q)
        before = len(qids)
        _record(rows)
        print(f"  [A] group type {gtype:>10}: {len(qids) - before:5d} new members (Korean groups)", flush=True)
        time.sleep(1)

    before_b = len(qids)

    # Pass B: Korean citizens who are members of ANY musical group
    for gtype in S.GROUP_TYPE_ANCHORS:
        q = f"""
        SELECT DISTINCT ?p ?g WHERE {{
          ?g wdt:P31/wdt:P279* wd:{gtype} .
          {{ ?p wdt:P463 ?g }} UNION {{ ?g wdt:P527 ?p }}
          ?p wdt:P31 wd:Q5 ;
             wdt:P27 wd:{S.Q_SOUTH_KOREA} .
        }}"""
        rows = S.sparql(q)
        before = len(qids)
        _record(rows)
        print(f"  [B] group type {gtype:>10}: {len(qids) - before:5d} new members (Korean citizens in any group)", flush=True)
        time.sleep(1)

    print(f"  Pass A: {before_b} | Pass B added: {len(qids) - before_b} | total: {len(qids)}")

    # Resolve group labels in one batch, then build person → group_name map.
    all_group_qids: set[str] = set()
    for gids in person_to_groups.values():
        all_group_qids |= gids
    print(f"  Resolving labels for {len(all_group_qids)} distinct groups...")
    group_labels = S.resolve_labels(sorted(all_group_qids))

    group_map: dict[str, str] = {}
    for pid, gids in person_to_groups.items():
        for gid in sorted(gids):          # deterministic order
            label = group_labels.get(gid, "")
            if label:
                group_map[pid] = label
                break                      # first labelled group wins

    print(f"  Group membership map: {len(group_map)} people with a group name")
    return sorted(qids), group_map

def build_row(qid: str, e: dict, labels: dict,
              group_fallback: dict[str, str] | None = None) -> dict:
    labs = e.get("labels", {})
    ko = labs.get("ko", {}).get("value", "")
    occ = S.claim_qids(e, "P106")
    grp = S.claim_qids(e, "P463")
    nat = S.claim_qids(e, "P27")
    gender = None
    for g in S.claim_qids(e, "P21"):
        if g in S.GENDER_MAP:
            gender = S.GENDER_MAP[g]; break
    debut = S.claim_year(e, "P2031")            # work period start = debut
    if debut and not (1950 <= debut <= 2030):
        debut = None
    langs = [labels.get(q, "") for q in S.claim_qids(e, "P1412") if labels.get(q)]
    aliases = e.get("aliases", {})
    other = []
    for lg in ("en", "ko"):
        for a in aliases.get(lg, []):
            v = a.get("value")
            if v and v not in other:
                other.append(v)
    # Group name: try P463 label first, fall back to the SPARQL-derived reverse
    # map (covers P527 "has part" on the group's page).
    group_name = labels.get(grp[0]) if grp else None
    if not group_name and group_fallback:
        group_name = group_fallback.get(qid)
    return {
        "wikidata_id": qid,
        "name_en": labs.get("en", {}).get("value"),
        "name_native": ko if S.has_hangul(ko) else None,
        "birth_year": S.claim_year(e, "P569"),
        "gender": gender,
        "nationality": labels.get(nat[0]) if nat else None,
        "group_name": group_name,
        "debut_year": debut,
        "languages_spoken": langs,
        "other_names": other,
        "occupation_qids": occ,
        "occupation_labels": {q: labels.get(q, "") for q in occ},
        "instagram": S.claim_string(e, "P2003"),
        "twitter": S.claim_string(e, "P2002"),
        "youtube": S.claim_string(e, "P2397"),
        "photo_url": S.image_url(e),
    }

def save(rows: list) -> None:
    RAW_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="cap number of people fetched")
    ap.add_argument("--refresh-qids", action="store_true", help="re-run the discovery queries")
    ap.add_argument("--backfill-groups", action="store_true",
                    help="rebuild group membership map and backfill group_name in existing raw rows")
    ap.add_argument("--max-consec-fail", type=int, default=3,
                    help="stop + save after N consecutive failed batches (throttling)")
    args = ap.parse_args()

    SEED.mkdir(exist_ok=True)

    # Fast path: --backfill-groups only rebuilds group map + patches existing rows.
    if args.backfill_groups:
        print("Rebuilding group membership map from Wikidata SPARQL...")
        _, group_map = collect_group_member_qids()
        GROUP_MAP_FILE.write_text(
            json.dumps(group_map, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(group_map)} entries -> seed/group_membership.json")

        # Summarise distinct groups and member counts.
        from collections import Counter
        group_counts = Counter(group_map.values())
        groups_file = SEED / "groups_found.txt"
        lines = []
        for name, cnt in sorted(group_counts.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"{cnt:4d}  {name}")
        groups_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n{len(group_counts)} distinct groups -> seed/groups_found.txt")
        print("Top 30:")
        for line in lines[:30]:
            print(f"  {line}")
        if len(lines) > 30:
            print(f"  ... and {len(lines) - 30} more (see seed/groups_found.txt)")

        if RAW_FILE.exists():
            rows = json.loads(RAW_FILE.read_text(encoding="utf-8"))
            patched = 0
            for r in rows:
                if not r.get("group_name") and r["wikidata_id"] in group_map:
                    r["group_name"] = group_map[r["wikidata_id"]]
                    patched += 1
            save(rows)
            print(f"\nBackfilled group_name on {patched} rows in wikidata_raw.json")
        return

    print("Building occupation subclass closures (cached to seed/occupation_closure.json)...")
    S.load_occupation_closures()

    # 1. Person QIDs — cached so a restart doesn't re-query all 15 anchors.
    if QIDS_FILE.exists() and not args.refresh_qids:
        qids = json.loads(QIDS_FILE.read_text(encoding="utf-8"))
        print(f"Loaded {len(qids)} person QIDs from cache (--refresh-qids to rebuild)")
    else:
        # 1a. Occupation-based: humans with a matching P106 claim
        print("Collecting person QIDs per occupation anchor...")
        qids = collect_person_qids()
        print(f"  Occupation-based: {len(qids)} people")

        # 1b. Group-member-based: members of SK musical groups, no P106 required.
        #     Catches idols whose Wikidata entries lack occupation tags (e.g. aespa).
        print("Collecting members of South Korean musical groups...")
        group_qids, group_map = collect_group_member_qids()
        new_from_groups = set(group_qids) - set(qids)
        print(f"  {len(new_from_groups)} additional people from group membership")
        qids = sorted(set(qids) | set(group_qids))

        # Save the group-membership map so resumed / re-fetched runs can use it.
        GROUP_MAP_FILE.write_text(
            json.dumps(group_map, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Group map saved -> seed/group_membership.json")

        QIDS_FILE.write_text(json.dumps(qids, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Total distinct people: {len(qids)} -> seed/person_qids.json")

    # Load group-membership map (fallback for group_name when P463 is missing).
    if GROUP_MAP_FILE.exists():
        group_map = json.loads(GROUP_MAP_FILE.read_text(encoding="utf-8"))
        print(f"Loaded group membership map: {len(group_map)} entries")
    else:
        group_map = {}
        print("No group membership map found (run with --refresh-qids to build one)")

    if args.limit:
        qids = qids[:args.limit]
        print(f"Limited to {len(qids)}")

    # 2. Resume — keep anyone already fetched.
    rows: list = []
    if RAW_FILE.exists():
        rows = json.loads(RAW_FILE.read_text(encoding="utf-8"))
        done = {r["wikidata_id"] for r in rows}
        rows = [r for r in rows if r["wikidata_id"] in set(qids)]  # respect --limit
        print(f"Resuming: {len(done)} already fetched")
    else:
        done = set()
    todo = [q for q in qids if q not in done]
    print(f"To fetch: {len(todo)} (of {len(qids)})")

    # 3. Fetch in batches; checkpoint after each. A run of consecutive batch
    #    failures means sustained throttling that won't clear this run, so stop
    #    cleanly (progress is already saved) rather than grinding — re-run to resume.
    consec = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            ents = S.get_entities(chunk)
            label_qids: set[str] = set()
            for e in ents.values():
                if "missing" in e:
                    continue
                label_qids |= set(S.claim_qids(e, "P106"))
                label_qids |= set(S.claim_qids(e, "P463"))
                label_qids |= set(S.claim_qids(e, "P27"))
            label_qids |= set(S.claim_qids(e, "P1412"))
            labels = S.resolve_labels(sorted(label_qids))
            for qid, e in ents.items():
                if "missing" in e:
                    continue
                rows.append(build_row(qid, e, labels, group_fallback=group_map))
            save(rows)  # checkpoint every batch
            consec = 0
            done_n = min(i + BATCH, len(todo))
            print(f"  [{done_n}/{len(todo)}] fetched — {len(rows)} rows saved", flush=True)
        except Exception as err:
            consec += 1
            save(rows)
            print(f"  batch failed ({consec}/{args.max_consec_fail}): {err}", flush=True)
            if consec >= args.max_consec_fail:
                print(f"\nCircuit breaker: {consec} consecutive batch failures "
                      f"(likely Wikidata throttling). Saved {len(rows)} rows to "
                      f"wikidata_raw.json. Re-run this script later to resume.")
                return
            time.sleep(30)  # brief pause, then try the next batch

    print(f"Done. {len(rows)} rows -> seed/wikidata_raw.json")

if __name__ == "__main__":
    main()
