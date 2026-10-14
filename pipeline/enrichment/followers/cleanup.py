"""
Instagram handle cleanup
========================
Consumes a failures log written by `enrichment.followers.run` and clears
handles that are confirmed dead — the account doesn't exist (not_found) or
is private (private), so a follower count can never be fetched for it.
"error" and "missing_from_response" entries are left alone: those can be
transient (rate limit, timeout, provider hiccup) and don't mean the handle
itself is bad, so they're not touched here.

This nulls out `handle` and `profile_url` on the social_accounts row (it
does not delete the row), so any existing follower_count history for that
talent is preserved and the row is simply excluded from future runs until
someone finds a corrected handle.

Usage
-----
    python -m enrichment.followers.cleanup --log enrichment/followers/logs/failures_<ts>.json
    python -m enrichment.followers.cleanup --log <path> --apply

Requires DATABASE_URL (.env). Dry run by default — pass --apply to write.
"""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

REMOVABLE_STATUSES = {"not_found", "private"}
LOG_DIR = Path(__file__).parent / "logs"

CLEAR_STMT = """
    UPDATE social_accounts
    SET handle = NULL, profile_url = NULL, last_updated = now()
    WHERE talent_id = %s AND platform = 'instagram' AND handle = %s
"""


@dataclass
class DeadHandle:
    talent_id: str
    name_en: str
    handle: str
    status: str


def load_failures_log(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("failures", [])


def select_dead_handles(failures: list[dict]) -> tuple[list[DeadHandle], list[dict]]:
    """Split failures into ones eligible for cleanup vs. left alone.

    Returns (dead_handles, skipped) where skipped entries keep their
    original dict shape plus nothing removed — they're reported so the run
    stays auditable end to end.
    """
    dead, skipped = [], []
    for entry in failures:
        if entry.get("status") in REMOVABLE_STATUSES:
            dead.append(DeadHandle(
                talent_id=entry["talent_id"], name_en=entry.get("name_en", ""),
                handle=entry["handle"], status=entry["status"],
            ))
        else:
            skipped.append(entry)
    return dead, skipped


def clear_handles(cur, dead_handles: list[DeadHandle]) -> list[DeadHandle]:
    """Runs the UPDATE for each dead handle. Returns the ones actually cleared
    (rowcount == 1) — a 0 rowcount means the row already changed since the
    log was written, so it's reported separately rather than assumed done.
    """
    cleared = []
    for dh in dead_handles:
        cur.execute(CLEAR_STMT, (dh.talent_id, dh.handle))
        if cur.rowcount:
            cleared.append(dh)
    return cleared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True, type=Path,
                        help="path to a failures_*.json log from enrichment.followers.run")
    parser.add_argument("--apply", action="store_true",
                        help="write to the database (default is a dry run)")
    args = parser.parse_args()

    if not args.log.exists():
        print(f"ERROR: log file not found: {args.log}")
        return

    failures = load_failures_log(args.log)
    dead_handles, skipped = select_dead_handles(failures)

    print(f"{len(failures)} failure entries in {args.log}")
    print(f"  {len(dead_handles)} eligible for cleanup (not_found / private)")
    print(f"  {len(skipped)} left alone (error / missing_from_response — may be transient)")

    for dh in dead_handles:
        print(f"    {dh.name_en:30s} @{dh.handle:25s} [{dh.status}]")

    if not dead_handles:
        print("\nNothing to clean up.")
        return

    if not args.apply:
        print(f"\nDRY RUN — {len(dead_handles)} handles would be cleared. Re-run with --apply to write.")
        return

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

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cleared = clear_handles(cur, dead_handles)
    conn.commit()
    cur.close()
    conn.close()

    stale = [dh for dh in dead_handles if dh not in cleared]

    print(f"\nCleared {len(cleared)} handles.")
    if stale:
        print(f"  {len(stale)} skipped — row changed since the log was written (handle no longer matched).")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOG_DIR / f"cleanup_{time.strftime('%Y%m%dT%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump({
            "source_log": str(args.log),
            "cleared": [dh.__dict__ for dh in cleared],
            "stale": [dh.__dict__ for dh in stale],
            "skipped": skipped,
        }, fh, ensure_ascii=False, indent=2)
    print(f"  Report written to: {report_path}")


if __name__ == "__main__":
    main()
