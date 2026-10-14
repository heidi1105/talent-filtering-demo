"""
audit_dbkpop.py — post-load coverage audit against dbkpop (REPORT ONLY).

Scrapes dbkpop's All K-Pop Idols table and reports idols NOT present in the DB
(matched on Korean name, else stage name). It never inserts anything — it hands
you a review list of possible gaps (foreign-national members, idols Wikidata
mis-tagged, real misses). Run it AFTER 03 has loaded.

Output: audit/dbkpop_gaps.json
Run:  python audit_dbkpop.py [--limit N]
Requires network + DATABASE_URL. Best-effort: if dbkpop changes its table
markup, check the parsed row count it prints.
"""
import argparse
import json
import re

import requests
from bs4 import BeautifulSoup

import seedlib as S

AUDIT = S.SCRIPT_DIR / "audit"
URL = "https://dbkpop.com/db/all-k-pop-idols/"

def norm(s):
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower())

def scrape():
    r = requests.get(URL, headers=S.HEADERS, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    heads = [th.get_text(strip=True).lower() for th in table.find_all("th")]

    def col(*names):
        for i, h in enumerate(heads):
            if any(n in h for n in names):
                return i
        return None

    ci_stage = col("stage")
    ci_korean = col("korean")
    ci_group = col("group")
    ci_dob = col("birth", "date of")
    rows = []
    for tr in table.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if not tds:
            continue

        def g(i):
            return tds[i] if i is not None and i < len(tds) else None

        rows.append({"stage": g(ci_stage), "korean": g(ci_korean),
                     "group": g(ci_group), "dob": g(ci_dob)})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    AUDIT.mkdir(exist_ok=True)

    print("Scraping dbkpop all-idols table...")
    idols = scrape()
    print(f"  parsed {len(idols)} idol rows")
    if args.limit:
        idols = idols[:args.limit]

    conn = S.connect()
    cur = conn.cursor()
    cur.execute("SELECT name_en, name_native FROM talents")
    db = cur.fetchall()
    cur.close()
    conn.close()

    have_ko = {norm(k) for _, k in db if k}
    have_en = {norm(n) for n, _ in db if n}

    gaps = []
    for it in idols:
        ko, en = norm(it.get("korean")), norm(it.get("stage"))
        if (ko and ko in have_ko) or (en and en in have_en):
            continue
        gaps.append(it)

    (AUDIT / "dbkpop_gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"dbkpop idols not found in DB: {len(gaps)} -> audit/dbkpop_gaps.json")

if __name__ == "__main__":
    main()
