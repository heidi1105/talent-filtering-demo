"""
Stage 6 — Backfill Kprofiles photos for talents Wikidata couldn't match
========================================================================
Some talents have no Wikipedia/Wikidata entry, so 04_wikidata_enrich.py left
photo_url null and they render with no image in the search UI. Kprofiles does
carry a photo for these people. This script fills the gap.

Precedence (enforced here and in 04_wikidata_enrich.py)
-------------------------------------------------------
    wikidata  >  kprofiles

  - This script only ever writes to rows where photo_url IS NULL, and stamps
    photo_source = 'kprofiles'.
  - 04_wikidata_enrich.py overwrites photo_url unconditionally when it finds a
    P18 claim and re-stamps photo_source = 'wikidata'.

So a Kprofiles photo is a placeholder that Wikidata reclaims for free the next
time enrichment runs. Nothing here can shadow a Wikidata photo.

How it works
------------
  1. Query the DB for talents with photo_url IS NULL.
  2. Match each one back to its Kprofiles profile_url via talents_clean.json
     (matched on normalized name_en, with birth_year as tiebreaker).
  3. Scrape only those pages for the photo, reusing extract_photo_url() from
     02_scrape_profiles.py so both paths stay identical.
  4. Write photo_url + photo_source = 'kprofiles' back.

Results are cached in kprofiles_photos.json, so a re-run does not re-scrape.

Usage
-----
    python 06_backfill_kprofiles_photos.py             # dry run — scrape + report, no writes
    python 06_backfill_kprofiles_photos.py --apply     # write to the database
    python 06_backfill_kprofiles_photos.py --apply --limit 20   # try a small batch first

Requires DATABASE_URL (read from .env).

Prerequisite: the photo_source migration at the bottom of schema.sql must have
been applied.
"""

import argparse
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

CLEAN_FILE  = Path("talents_clean.json")
CACHE_FILE  = Path("kprofiles_photos.json")
REPORT_FILE = Path("kprofiles_photos_report.json")
REQUEST_DELAY = 1.5
CHECKPOINT_EVERY = 25


# ---------------------------------------------------------------------------
# Reuse the scraper's photo logic (module name starts with a digit, so the
# normal import statement is not available)
# ---------------------------------------------------------------------------

def _load_scraper_module():
    path = Path(__file__).with_name("02_scrape_profiles.py")
    spec = importlib.util.spec_from_file_location("scrape_profiles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

def norm_name(name: str | None) -> str:
    """
    'Ahn Hyo-seop' / 'Ahn Hyo Seop' / 'ahnhyoseop' all collapse to the same key,
    so hyphenation and spacing differences between the DB and the scrape do not
    break the join.
    """
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_index(clean_records: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for r in clean_records:
        key = norm_name(r.get("name_english"))
        if key and r.get("profile_url"):
            index.setdefault(key, []).append(r)
    return index


def match_record(talent: dict, index: dict[str, list[dict]]) -> tuple[dict | None, str]:
    """Returns (matched_clean_record, reason). reason is '' on success."""
    key = norm_name(talent.get("name_en"))
    candidates = index.get(key)
    if not candidates:
        return None, "no_kprofiles_record"
    if len(candidates) == 1:
        return candidates[0], ""
    # Same English name appears more than once — disambiguate on birth_year
    by_year = [c for c in candidates if c.get("birth_year") == talent.get("birth_year")]
    if len(by_year) == 1:
        return by_year[0], ""
    return None, "ambiguous_name"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache() -> dict[str, str | None]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write to the database (default is a dry run)")
    parser.add_argument("--limit", type=int, default=None,
                        help="process at most N talents")
    args = parser.parse_args()

    if not CLEAN_FILE.exists():
        print(f"ERROR: {CLEAN_FILE} not found. Run 03_clean_load.py first.")
        return

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        return

    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    scraper = _load_scraper_module()

    with open(CLEAN_FILE, encoding="utf-8") as f:
        clean_records = json.load(f)
    index = build_index(clean_records)
    print(f"Indexed {len(index)} Kprofiles names from {CLEAN_FILE}")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Guard: fail loudly rather than silently skipping provenance
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'talents' AND column_name = 'photo_source'
    """)
    if not cur.fetchone():
        print("ERROR: talents.photo_source does not exist.")
        print("Apply the migration at the bottom of schema.sql first.")
        conn.close()
        return

    cur.execute("""
        SELECT id, name_en, birth_year, wikidata_id
        FROM talents
        WHERE photo_url IS NULL
        ORDER BY name_en
    """)
    cols = [d[0] for d in cur.description]
    missing = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()

    print(f"{len(missing)} talents have no photo_url")
    if args.limit:
        missing = missing[:args.limit]
        print(f"Limited to {len(missing)}")

    cache = load_cache()
    report = {"updated": [], "no_photo_on_page": [], "unmatched": [], "fetch_failed": []}
    processed = 0

    for i, talent in enumerate(missing, 1):
        name = talent["name_en"]
        record, reason = match_record(talent, index)

        if record is None:
            report["unmatched"].append({
                "id": str(talent["id"]), "name_en": name, "reason": reason,
            })
            continue

        url = record["profile_url"]

        if url in cache:
            photo = cache[url]
        else:
            print(f"[{i}/{len(missing)}] {name} — {url}")
            soup = scraper.fetch_page(url)
            if soup is None:
                report["fetch_failed"].append({"id": str(talent["id"]), "name_en": name, "url": url})
                time.sleep(REQUEST_DELAY)
                continue
            photo = scraper.extract_photo_url(soup)
            cache[url] = photo
            processed += 1
            if processed % CHECKPOINT_EVERY == 0:
                save_cache(cache)
                print(f"  Cache checkpoint saved ({len(cache)} pages)")
            time.sleep(REQUEST_DELAY)

        if not photo:
            report["no_photo_on_page"].append({
                "id": str(talent["id"]), "name_en": name, "url": url,
            })
            continue

        report["updated"].append({
            "id": str(talent["id"]), "name_en": name,
            "photo_url": photo, "wikidata_id": talent.get("wikidata_id"),
        })

    save_cache(cache)

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------
    if args.apply and report["updated"]:
        cur = conn.cursor()
        written = 0
        for item in report["updated"]:
            # The photo_url IS NULL guard is repeated here so a concurrent
            # 04_wikidata_enrich.py run cannot be clobbered mid-flight.
            cur.execute("""
                UPDATE talents
                SET photo_url = %s, photo_source = 'kprofiles', last_updated = now()
                WHERE id = %s AND photo_url IS NULL
            """, (item["photo_url"], item["id"]))
            written += cur.rowcount
        conn.commit()
        cur.close()
        print(f"\nWrote {written} photo_url values (photo_source = 'kprofiles')")
    elif report["updated"]:
        print(f"\nDRY RUN — {len(report['updated'])} rows would be updated. "
              f"Re-run with --apply to write.")

    conn.close()

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\nSummary")
    print(f"  Photo found        : {len(report['updated'])}")
    print(f"  No photo on page   : {len(report['no_photo_on_page'])}")
    print(f"  No Kprofiles match : {len(report['unmatched'])}")
    print(f"  Fetch failed       : {len(report['fetch_failed'])}")
    print(f"  Report written to  : {REPORT_FILE}")


if __name__ == "__main__":
    main()
