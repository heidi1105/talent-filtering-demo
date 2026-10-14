"""
03_reconcile_load.py — must-include coverage gate, then upsert into Supabase.

Step 1 (gate): grade seed/talents_seed.json against seed/must_include.json and
write seed/coverage_report.json. If any anchor is missing, stop before loading
(unless --force).

Step 2 (load): upsert talents keyed on wikidata_id. A pre-existing row with no
wikidata_id that matches on name_native + birth_year gets the QID back-filled
onto it (so the old Kprofiles rows are reconciled, never duplicated). Socials
(instagram/twitter/youtube) upsert into social_accounts.

Run:
  python 03_reconcile_load.py --dry-run          # reconcile + preview, no DB writes
  python 03_reconcile_load.py                     # load, but stop if anchors missing
  python 03_reconcile_load.py --force             # load even if anchors missing
  python 03_reconcile_load.py --stale-days 180    # skip rows updated within N days
Requires DATABASE_URL (.env).
"""
import argparse
import json
import re
from datetime import datetime

import seedlib as S

SEED = S.SEED_DIR

def norm(s: str | None) -> str:
    """Normalise a name for fuzzy matching.
    NFKD strips accents (é→e), NFC recomposes Hangul Jamo back to syllables,
    then we map ø→o for names like LØREN."""
    import unicodedata
    t = unicodedata.normalize("NFKD", (s or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = unicodedata.normalize("NFC", t)               # Jamo → syllables (가-힣)
    t = t.replace("ø", "o").replace("đ", "d").replace("ł", "l")
    return re.sub(r"[^a-z0-9가-힣]", "", t)

def reconcile(seed_rows, anchors):
    idx_en = {norm(r["name_en"]): r for r in seed_rows if r.get("name_en")}
    idx_ko = {norm(r["name_native"]): r for r in seed_rows if r.get("name_native")}
    # Secondary: other_names (stage names, aliases like "S.Coups", "미연")
    idx_alias = {}
    for r in seed_rows:
        for alias in (r.get("other_names") or []):
            key = norm(alias)
            if key:
                idx_alias.setdefault(key, r)
    # Group index: for group-type anchors (STAYC, Treasure)
    idx_group = {}
    for r in seed_rows:
        gn = r.get("group_name")
        if gn:
            idx_group.setdefault(norm(gn), r)
    matched, missing = [], []
    for a in anchors:
        m = None
        if a.get("type") == "group":
            m = idx_group.get(norm(a["name_en"]))
            if not m and a.get("name_native"):
                m = idx_group.get(norm(a["name_native"]))
        else:
            m = idx_en.get(norm(a["name_en"]))
            if not m and a.get("name_native"):
                m = idx_ko.get(norm(a["name_native"]))
            if not m:
                m = idx_alias.get(norm(a["name_en"]))
            if not m and a.get("name_native"):
                m = idx_alias.get(norm(a["name_native"]))
            # Prefix fallback: "Krystal" matches "Krystal Jung" etc.
            if not m:
                key = norm(a["name_en"])
                if len(key) >= 4:
                    for idx in (idx_en, idx_ko, idx_alias):
                        for k, v in idx.items():
                            if len(k) >= 4 and k.startswith(key):
                                m = v
                                break
                        if m:
                            break
            if not m and a.get("name_native"):
                key = norm(a["name_native"])
                if len(key) >= 2:
                    for idx in (idx_en, idx_ko, idx_alias):
                        for k, v in idx.items():
                            if len(k) >= 2 and k.startswith(key):
                                m = v
                                break
                        if m:
                            break
        # Group-aware disambiguation: if anchor specifies a group and the
        # current match belongs to a different group, scan for a seed row
        # that matches both the name and the group.
        if m and a.get("group"):
            anchor_grp = norm(a["group"])
            if anchor_grp and norm(m.get("group_name") or "") != anchor_grp:
                a_en = norm(a["name_en"])
                a_ko = norm(a.get("name_native") or "")
                for r in seed_rows:
                    if norm(r.get("group_name") or "") != anchor_grp:
                        continue
                    r_en = norm(r.get("name_en") or "")
                    r_ko = norm(r.get("name_native") or "")
                    r_aliases = [norm(al) for al in (r.get("other_names") or [])]
                    if (a_en and (a_en == r_en or r_en.startswith(a_en)
                                  or a_en in r_aliases)) or \
                       (a_ko and (a_ko == r_ko or a_ko in r_aliases)):
                        m = r
                        break

        (matched if m else missing).append({**a, "matched_qid": (m or {}).get("wikidata_id")})
    return matched, missing

SOCIALS = [
    ("instagram", "instagram", "https://instagram.com/{}"),
    ("twitter",   "twitter",   "https://twitter.com/{}"),
    ("youtube",   "youtube",   "https://youtube.com/channel/{}"),
]

def load(conn, rows, stale_days, commit_every=100):
    cur = conn.cursor()
    ins = upd = skip = soc = 0
    total = len(rows)
    for n, r in enumerate(rows, 1):
        qid = r["wikidata_id"]
        cur.execute("SELECT id, last_updated FROM talents WHERE wikidata_id = %s", (qid,))
        hit = cur.fetchone()
        tid = None
        if hit:
            tid = hit[0]
            if stale_days and hit[1] and (datetime.now(hit[1].tzinfo) - hit[1]).days < stale_days:
                skip += 1
            else:
                cur.execute("""
                    UPDATE talents SET
                        name_en = %s,
                        name_native = COALESCE(%s, name_native),
                        birth_year  = COALESCE(%s, birth_year),
                        gender      = COALESCE(%s, gender),
                        nationality = COALESCE(%s, nationality),
                        occupation  = %s,
                        group_name  = COALESCE(%s, group_name),
                        debut_year  = COALESCE(%s, debut_year),
                        languages_spoken = COALESCE(NULLIF(%s::text[], '{}'), languages_spoken),
                        other_names = COALESCE(NULLIF(%s::text[], '{}'), other_names),
                        photo_url   = COALESCE(photo_url, %s),
                        photo_source = CASE WHEN photo_url IS NULL AND %s IS NOT NULL
                                            THEN 'wikidata' ELSE photo_source END,
                        source      = COALESCE(source, 'wikidata'),
                        last_updated = now()
                    WHERE id = %s
                """, (r["name_en"], r["name_native"], r["birth_year"], r["gender"],
                      r["nationality"], r["occupation"], r["group_name"],
                      r["debut_year"], r["languages_spoken"], r["other_names"],
                      r["photo_url"], r["photo_url"], tid))
                upd += 1
        else:
            # Back-fill onto a pre-existing (Kprofiles) row matched by native name + birth year.
            if r.get("name_native"):
                cur.execute("""SELECT id FROM talents
                               WHERE wikidata_id IS NULL AND name_native = %s
                                 AND birth_year IS NOT DISTINCT FROM %s""",
                            (r["name_native"], r["birth_year"]))
                row = cur.fetchone()
                if row:
                    tid = row[0]
            if tid:
                cur.execute("""
                    UPDATE talents SET
                        wikidata_id = %s, name_en = %s,
                        gender = COALESCE(%s, gender),
                        nationality = COALESCE(%s, nationality),
                        occupation = %s,
                        group_name = COALESCE(%s, group_name),
                        debut_year = COALESCE(%s, debut_year),
                        languages_spoken = COALESCE(NULLIF(%s::text[], '{}'), languages_spoken),
                        other_names = COALESCE(NULLIF(%s::text[], '{}'), other_names),
                        photo_url = COALESCE(photo_url, %s),
                        source = COALESCE(source, 'wikidata'),
                        last_updated = now()
                    WHERE id = %s
                """, (qid, r["name_en"], r["gender"], r["nationality"], r["occupation"],
                      r["group_name"], r["debut_year"], r["languages_spoken"],
                      r["other_names"], r["photo_url"], tid))
                upd += 1
            else:
                cur.execute("""
                    INSERT INTO talents (name_en, name_native, birth_year, gender, nationality,
                                         occupation, group_name, debut_year, languages_spoken,
                                         other_names, wikidata_id, photo_url,
                                         photo_source, source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'wikidata') RETURNING id
                """, (r["name_en"], r["name_native"], r["birth_year"], r["gender"],
                      r["nationality"], r["occupation"], r["group_name"],
                      r["debut_year"], r["languages_spoken"], r["other_names"],
                      qid, r["photo_url"],
                      "wikidata" if r["photo_url"] else None))
                tid = cur.fetchone()[0]
                ins += 1

        for key, platform, tmpl in SOCIALS:
            h = r.get(key)
            if not h:
                continue
            cur.execute("""
                INSERT INTO social_accounts (talent_id, platform, handle, profile_url)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (talent_id, platform) DO UPDATE
                  SET handle = EXCLUDED.handle, profile_url = EXCLUDED.profile_url, last_updated = now()
            """, (tid, platform, h, tmpl.format(h)))
            soc += 1

        if n % commit_every == 0:
            conn.commit()
            print(f"  [{n}/{total}] committed — inserted {ins}, updated {upd}, "
                  f"skipped {skip}, socials {soc}", flush=True)
    conn.commit()
    cur.close()
    return ins, upd, skip, soc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--stale-days", type=int, default=0)
    ap.add_argument("--commit-every", type=int, default=100,
                    help="commit + log progress every N rows")
    args = ap.parse_args()

    rows = json.loads((SEED / "talents_seed.json").read_text(encoding="utf-8"))
    anchors = json.loads((SEED / "must_include.json").read_text(encoding="utf-8"))
    matched, missing = reconcile(rows, anchors)

    report = {"total_seed": len(rows), "anchors": len(anchors),
              "matched": len(matched), "missing": missing,
              "generated": datetime.now().isoformat()}
    (SEED / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Seed rows: {len(rows)} | anchors matched: {len(matched)}/{len(anchors)}")
    if missing:
        print(f"MISSING {len(missing)} anchors:")
        for m in missing:
            print("   -", m["name_en"], (m.get("group") or ""))

    if args.dry_run:
        print("dry-run: no DB writes. seed/coverage_report.json written.")
        return
    if missing and not args.force:
        print("\nStopping before load — anchors missing. Add them, or re-run with --force.")
        return

    conn = S.connect()
    ins, upd, skip, soc = load(conn, rows, args.stale_days, args.commit_every)
    conn.close()
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    (SEED / f"load_report_{ts}.json").write_text(json.dumps(
        {"inserted": ins, "updated": upd, "skipped": skip, "socials": soc,
         "anchors_missing": len(missing)}, indent=2), encoding="utf-8")
    print(f"Loaded: inserted {ins}, updated {upd}, skipped {skip}, social rows {soc}")

if __name__ == "__main__":
    main()
