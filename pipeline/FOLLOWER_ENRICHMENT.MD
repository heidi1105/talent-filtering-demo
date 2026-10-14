# Plan: Instagram Follower-Count Enrichment Module

> Hand this file to Claude Code as the build spec. It targets **Bright Data** as the
> data provider, but the provider is isolated behind a thin adapter so it can be swapped
> for Apify or another vendor without touching the pipeline.

---

## 1. Objective

Add a module to the existing Python enrichment pipeline that, for every talent record
with an Instagram handle, fetches the current follower count from a managed scraping
provider (Bright Data) and writes it back to Supabase.

The module runs in two modes:
- **On-demand** — as part of a normal enrichment run.
- **Batch refresh** — quarterly / bi-annually across the full talent set.

**Non-goals (do not build):**
- No DIY scraping / proxy rotation (managed provider handles anti-bot).
- No YouTube / Twitter follower fetching yet (design the adapter so it *can* extend later, but only Instagram is in scope now).
- No new UI. This is backend/pipeline only.
- No new Supabase tables — follower columns already exist (see §3).

---

## 2. Provider: Bright Data

Use Bright Data's **Instagram Profiles Scraper** (Web Scraper API, pay-per-success).

- Input: an Instagram username or profile URL.
- Output: structured JSON including `followers` (follower count), plus bio/verified/etc.
- Auth: API key via `BRIGHTDATA_API_KEY` env var. Dataset/collector ID via `BRIGHTDATA_IG_DATASET_ID` env var.
- Billing model: pay-per-successful-record, so failed handles (deleted/private/renamed) don't incur cost — but MUST be logged so they can be reviewed.

**Adapter requirement:** all Bright Data specifics live in one file
(`providers/brightdata.py`) behind an interface like:

```python
class FollowerProvider(Protocol):
    def fetch(self, handles: list[str]) -> list[FollowerResult]: ...

@dataclass
class FollowerResult:
    handle: str
    follower_count: int | None      # None if not found
    status: str                     # "ok" | "not_found" | "private" | "error"
    raw: dict | None                # provider payload for debugging
```

Swapping to Apify later = write `providers/apify.py` implementing the same Protocol.

---

## 3. Data model (already exists — confirm, don't create)

Talent table already has follower columns. Claude Code should:
1. **Inspect the live schema first** and confirm the exact column names for follower
   count and last-checked timestamp before writing any code.
2. Write results to the existing follower count column.
3. Set the last-checked / last-updated timestamp on each successful update.
4. Only read rows where the Instagram handle is non-null.

> ⚠️ Confirm the real column names against Supabase — do not assume
> `follower_count` / `follower_last_checked`.

---

## 4. Module design

Suggested structure:

```
enrichment/
  followers/
    __init__.py
    provider_base.py      # Protocol + FollowerResult dataclass
    providers/
      brightdata.py       # Bright Data implementation
    handles.py            # normalize + extract usernames from stored links/handles
    run.py                # orchestration: read → fetch → write → report
```

### 4.1 Handle normalization (`handles.py`)
- Accept raw values that may be a bare username, `@username`, or a full
  `instagram.com/username/` URL, and normalize to a bare username.
- Strip query strings, trailing slashes, whitespace, and a leading `@`.
- Skip / flag anything that doesn't look like a valid IG username.

### 4.2 Fetch (`providers/brightdata.py`)
- Batch handles into a single Bright Data request where the API supports it
  (it accepts multiple inputs per trigger) rather than one call per talent.
- Trigger the collector, poll for completion, download results.
- Map each returned record back to its input handle and to a `FollowerResult`.
- Classify outcomes: `ok`, `not_found`, `private`, `error`.
- Handle async job lifecycle (trigger → poll `status` until `ready` → fetch data),
  with a sane max-wait and backoff.

### 4.3 Orchestration (`run.py`)
- Read candidate rows from Supabase (Instagram handle not null).
- Optional `--stale-days N` filter: only refresh rows whose last-checked timestamp
  is older than N days (default for quarterly runs, e.g. 80). Lets a re-run skip
  fresh rows.
- Optional `--limit N` for test runs.
- Chunk handles into batches (e.g. 50–100 per provider request) to stay within
  provider limits and keep failures isolated.
- For each successful result, update the talent row (follower count + timestamp).
- Do NOT overwrite an existing follower count with `None` on a failed lookup —
  leave the old value and log the failure.
- Print/write a summary report at the end: total, updated, not_found, private, errors.

---

## 5. Configuration (env vars)

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=        # service role, backend only
BRIGHTDATA_API_KEY=
BRIGHTDATA_IG_DATASET_ID=    # Instagram Profiles collector/dataset id
```

Load via existing config mechanism / `.env`. Never hardcode keys.

---

## 6. Error handling & resilience

- **Rate limits / transient errors:** retry with exponential backoff, capped.
- **Partial batch failure:** a bad handle in a batch must not fail the whole batch;
  isolate and record per-handle status.
- **Idempotent:** safe to re-run; the `--stale-days` filter prevents redundant paid
  lookups on rows updated in the current cycle.
- **Cost guard:** log the count of handles about to be submitted and (optionally)
  require confirmation above a threshold, so a full-table run isn't triggered by accident.
- **Dry run:** `--dry-run` flag that reads + normalizes + reports what *would* be
  fetched, without calling the provider or writing to Supabase.

---

## 7. Logging & observability

- Per-run summary: counts by status, elapsed time, number of records billed.
- Persist a list of `not_found` / `private` / `error` handles (log file or a simple
  table/column) so stale or renamed handles can be cleaned up manually.
- Do not log API keys.

---

## 8. Testing

- Unit test `handles.py` normalization against: bare username, `@username`, full URL,
  URL with query string, invalid input.
- Mock the provider in `run.py` tests — assert correct rows are selected, correct
  updates issued, and that a `None`/error result does NOT overwrite an existing count.
- One small live smoke test (5–10 real handles behind a `--limit`) before the first
  full run.

---

## 9. Scheduling (quarterly / bi-annual)

- The module must be runnable as a single command, e.g.:
  `python -m enrichment.followers.run --stale-days 80`
- Wire that command into whatever scheduler you use (cron, or a Vercel scheduled
  function / GitHub Action). Scheduling config is out of scope for this build —
  just make the entrypoint clean and parameterized so it drops into a scheduler.

---

## 10. Legal / scope note (keep in mind, don't action)

This module is intended for private/internal use. Do not expand scope to other platforms or new tables in this build.

---

## 11. Build order for Claude Code

1. Confirm the live Supabase schema (follower column + timestamp column names).
2. `provider_base.py` — Protocol + dataclass.
3. `handles.py` + unit tests.
4. `providers/brightdata.py` — trigger/poll/fetch against a few test handles.
5. `run.py` — orchestration, flags (`--dry-run`, `--limit`, `--stale-days`), Supabase writes.
6. Live smoke test with `--limit 10`.
7. Full run.

Ask before running the first full (billed) batch.