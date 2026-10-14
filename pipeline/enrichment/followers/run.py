"""
Instagram follower-count refresh
=================================
For every talent with an Instagram handle in social_accounts, fetches the
current follower count from Bright Data and writes it back.

Usage
-----
    python -m enrichment.followers.run --dry-run              # read + normalize + report only
    python -m enrichment.followers.run --limit 10              # smoke test a handful of talents
    python -m enrichment.followers.run --stale-days 80         # quarterly refresh, skip fresh rows
    python -m enrichment.followers.run --stale-days 80 --yes   # skip the cost-guard prompt

Requires DATABASE_URL, BRIGHTDATA_API_KEY, BRIGHTDATA_IG_PROFILE_DATASET_ID (.env).

Does NOT overwrite an existing follower_count with None on a failed lookup —
the old value is left in place and the handle is logged to
enrichment/followers/logs/ for manual review.

Crash safety: each batch is committed to the DB and the failure log is
rewritten immediately after that batch completes — not just once at the
end. An interruption (Ctrl-C, network drop, crash) loses at most the
in-flight batch; every batch fetched (and paid for) before that is already
saved.
"""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .handles import normalize_handle
from .provider_base import FollowerResult

BATCH_SIZE = 75
COST_GUARD_THRESHOLD = 100
LOG_DIR = Path(__file__).parent / "logs"


@dataclass
class Candidate:
    talent_id: str
    name_en: str
    handle: str  # normalized, lowercase


# ---------------------------------------------------------------------------
# Pure logic (no DB / network) — unit tested directly.
# ---------------------------------------------------------------------------

def normalize_candidates(rows: list[tuple]) -> tuple[list[Candidate], list[dict]]:
    """rows: (talent_id, name_en, raw_handle) tuples from social_accounts.

    Returns (candidates, invalid) where invalid entries didn't look like a
    real IG username and are skipped rather than sent to the provider.
    """
    candidates, invalid = [], []
    for talent_id, name_en, raw_handle in rows:
        normalized = normalize_handle(raw_handle)
        if normalized is None:
            invalid.append({"talent_id": str(talent_id), "name_en": name_en, "raw_handle": raw_handle})
        else:
            candidates.append(Candidate(talent_id=str(talent_id), name_en=name_en, handle=normalized))
    return candidates, invalid


def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def build_updates(
    candidates: list[Candidate], results: list[FollowerResult]
) -> tuple[list[tuple[str, int]], list[dict]]:
    """Merge candidates with provider results.

    Returns (updates, failures). updates = [(talent_id, follower_count)] for
    rows to write. A result that is missing, or has status != "ok", or has
    follower_count None, becomes a failure entry instead — it must never
    overwrite an existing count.
    """
    by_handle = {r.handle.lower(): r for r in results}
    updates, failures = [], []
    for c in candidates:
        r = by_handle.get(c.handle.lower())
        if r is None:
            failures.append({
                "talent_id": c.talent_id, "name_en": c.name_en, "handle": c.handle,
                "status": "missing_from_response", "error_message": None,
            })
        elif r.status == "ok" and r.follower_count is not None:
            updates.append((c.talent_id, r.follower_count))
        else:
            failures.append({
                "talent_id": c.talent_id, "name_en": c.name_en, "handle": c.handle,
                "status": r.status, "error_message": r.error_message,
            })
    return updates, failures


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

CANDIDATE_QUERY = """
    SELECT t.id, t.name_en, sa.handle
    FROM social_accounts sa
    JOIN talents t ON t.id = sa.talent_id
    WHERE sa.platform = 'instagram' AND sa.handle IS NOT NULL
      AND (
        %(stale_days)s::int IS NULL
        OR sa.followers_captured_at IS NULL
        OR sa.followers_captured_at < now() - make_interval(days => %(stale_days)s::int)
      )
    ORDER BY sa.followers_captured_at NULLS FIRST
    LIMIT %(limit)s
"""

UPDATE_STMT = """
    UPDATE social_accounts
    SET follower_count = %s, followers_captured_at = now(), last_updated = now()
    WHERE talent_id = %s AND platform = 'instagram'
"""


def fetch_candidate_rows(cur, stale_days: int | None, limit: int | None) -> list[tuple]:
    cur.execute(CANDIDATE_QUERY, {"stale_days": stale_days, "limit": limit})
    return cur.fetchall()


def write_updates(cur, updates: list[tuple[str, int]]) -> int:
    written = 0
    for talent_id, follower_count in updates:
        cur.execute(UPDATE_STMT, (follower_count, talent_id))
        written += cur.rowcount
    return written


def write_log_atomic(path: Path, data: dict) -> None:
    """Write via a temp file + rename so a crash mid-write can't corrupt the
    previous, already-flushed version of the log."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="read + normalize + report only; no provider calls, no DB writes")
    parser.add_argument("--limit", type=int, default=None, help="process at most N talents")
    parser.add_argument("--stale-days", type=int, default=None,
                        help="only refresh rows last checked more than N days ago (e.g. 80)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"handles per Bright Data request (default {BATCH_SIZE})")
    parser.add_argument("--yes", action="store_true",
                        help="skip the cost-guard confirmation prompt")
    args = parser.parse_args()

    import sys
    sys.stdout.reconfigure(line_buffering=True)  # progress must show up live, not just at exit

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
    rows = fetch_candidate_rows(cur, args.stale_days, args.limit)
    cur.close()

    print(f"{len(rows)} candidate rows (instagram handle set"
          f"{f', stale > {args.stale_days}d' if args.stale_days else ''}"
          f"{f', limit {args.limit}' if args.limit else ''})")

    candidates, invalid = normalize_candidates(rows)
    print(f"  {len(candidates)} valid handles, {len(invalid)} skipped (unrecognized handle format)")

    if args.dry_run:
        print("\nDRY RUN — no provider calls, no DB writes.")
        for c in candidates[:20]:
            print(f"  {c.name_en:30s} @{c.handle}")
        if len(candidates) > 20:
            print(f"  ... and {len(candidates) - 20} more")
        conn.close()
        return

    if not candidates:
        print("Nothing to fetch.")
        conn.close()
        return

    if len(candidates) > COST_GUARD_THRESHOLD and not args.yes:
        answer = input(
            f"\nAbout to submit {len(candidates)} handles to Bright Data "
            f"(pay-per-success). Continue? [y/N] "
        )
        if answer.strip().lower() != "y":
            print("Aborted.")
            conn.close()
            return

    from .providers.brightdata import BrightDataInstagramProvider

    provider = BrightDataInstagramProvider()
    start = time.monotonic()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"failures_{time.strftime('%Y%m%dT%H%M%S')}.json"

    total_written = 0
    all_failures: list[dict] = []
    status_counts: dict[str, int] = {}
    batches = list(chunked(candidates, args.batch_size))

    try:
        for i, batch in enumerate(batches, 1):
            batch_handles = [c.handle for c in batch]
            print(f"  Batch {i}/{len(batches)}: fetching {len(batch_handles)} handles")
            for c in batch:
                print(f"    - {c.name_en} (@{c.handle})")

            results = provider.fetch(batch_handles)
            updates, failures = build_updates(batch, results)

            cur = conn.cursor()
            written = write_updates(cur, updates)
            conn.commit()
            cur.close()

            total_written += written
            all_failures.extend(failures)
            for f in failures:
                status_counts[f["status"]] = status_counts.get(f["status"], 0) + 1

            # Per-talent result, in the same order they were requested in.
            update_map = dict(updates)
            failure_map = {f["talent_id"]: f for f in failures}
            for c in batch:
                if c.talent_id in update_map:
                    print(f"    {c.name_en:30s} @{c.handle:22s} ok  ({update_map[c.talent_id]:,} followers)")
                else:
                    f = failure_map[c.talent_id]
                    detail = f" ({f['error_message']})" if f.get("error_message") else ""
                    print(f"    {c.name_en:30s} @{c.handle:22s} {f['status']}{detail}")

            print(f"    -> {written} updated, {len(failures)} failed "
                  f"(running total: {total_written} updated, {len(all_failures)} failed)")

            # Rewritten after every batch, so an interruption still leaves a
            # log covering everything fetched so far — not just the final tally.
            write_log_atomic(log_path, {
                "batches_completed": i, "batches_total": len(batches),
                "updated_so_far": total_written,
                "failures": all_failures, "invalid_handles": invalid,
            })
    except KeyboardInterrupt:
        conn.close()
        print(f"\nInterrupted. {total_written} rows already committed; "
              f"progress log saved to {log_path}.")
        return

    conn.close()
    elapsed = time.monotonic() - start

    print("\nSummary")
    print(f"  Total candidates : {len(candidates)}")
    print(f"  Updated          : {total_written}")
    print(f"  Billed (ok)      : {total_written}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:16s}: {count}")
    print(f"  Invalid handles  : {len(invalid)} (not sent to provider)")
    print(f"  Elapsed          : {elapsed:.1f}s")
    print(f"  Failure log      : {log_path}")


if __name__ == "__main__":
    main()
