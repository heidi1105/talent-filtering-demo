"""
Bright Data adapter — Instagram Profiles Scraper (Dataset API v3).

Implements FollowerProvider. All Bright Data specifics (endpoints, request/
response shape) live in this one file so a future provider swap (e.g. Apify)
only means writing a sibling module against the same Protocol.

Job lifecycle: trigger a collection run for a batch of profile URLs, poll
until the snapshot is ready, then download it and map each record back to
the handle that produced it.

NOTE ON FIELD MAPPING: the exact JSON keys Bright Data returns for the
Instagram Profiles dataset (follower count field name, private/not-found
signaling) should be confirmed against a real response during the live
smoke test (see FOLLOWER_ENRICHMENT.MD step 6) and this mapping adjusted
if needed. FollowerResult.raw always carries the untouched record so a
mismatch is debuggable without re-running a paid lookup.
"""

import os
import time
from dataclasses import dataclass

import requests

from ..provider_base import FollowerResult

API_BASE = "https://api.brightdata.com/datasets/v3"

TRIGGER_TIMEOUT = 30          # seconds, per HTTP call
POLL_INTERVAL = 5             # seconds between progress checks
POLL_MAX_WAIT = 600           # seconds — give up waiting after this long
MAX_RETRIES = 4               # for transient HTTP errors (429 / 5xx / network)
RETRY_BASE_DELAY = 2          # seconds; doubles each retry


class BrightDataError(RuntimeError):
    pass


@dataclass
class BrightDataConfig:
    api_key: str
    dataset_id: str

    @classmethod
    def from_env(cls) -> "BrightDataConfig":
        api_key = os.environ.get("BRIGHTDATA_API_KEY")
        dataset_id = os.environ.get("BRIGHTDATA_IG_PROFILE_DATASET_ID")
        if not api_key:
            raise BrightDataError("BRIGHTDATA_API_KEY environment variable not set.")
        if not dataset_id:
            raise BrightDataError("BRIGHTDATA_IG_PROFILE_DATASET_ID environment variable not set.")
        return cls(api_key=api_key, dataset_id=dataset_id)


class BrightDataInstagramProvider:
    """FollowerProvider implementation backed by Bright Data's Instagram
    Profiles dataset."""

    def __init__(self, config: BrightDataConfig | None = None):
        self.config = config or BrightDataConfig.from_env()
        self._headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    # -- Protocol entrypoint -------------------------------------------------

    def fetch(self, handles: list[str]) -> list[FollowerResult]:
        """Fetch follower data for a batch of handles in one Bright Data job.

        A bad handle in the batch is isolated at the mapping stage — it
        never fails the whole batch.
        """
        if not handles:
            return []

        try:
            snapshot_id = self._trigger(handles)
            self._wait_until_ready(snapshot_id)
            records = self._download(snapshot_id)
        except BrightDataError as exc:
            # Whole-batch failure (job never became ready, trigger rejected,
            # etc.) — every handle in the batch is reported as an error so
            # none of them silently vanish from the run report.
            return [
                FollowerResult(handle=h, follower_count=None, status="error",
                                error_message=str(exc))
                for h in handles
            ]

        return self._map_records(handles, records)

    # -- HTTP steps -----------------------------------------------------------

    def _trigger(self, handles: list[str]) -> str:
        url = f"{API_BASE}/trigger"
        params = {"dataset_id": self.config.dataset_id, "include_errors": "true"}
        body = [{"url": f"https://www.instagram.com/{h}/"} for h in handles]

        data = self._request_with_retry("POST", url, params=params, json=body)
        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            raise BrightDataError(f"Trigger response missing snapshot_id: {data}")
        print(f"    triggered snapshot {snapshot_id}, waiting for Bright Data...", flush=True)
        return snapshot_id

    def _wait_until_ready(self, snapshot_id: str) -> None:
        url = f"{API_BASE}/progress/{snapshot_id}"
        waited = 0
        while waited <= POLL_MAX_WAIT:
            data = self._request_with_retry("GET", url)
            status = data.get("status")
            print(f"    ...{waited}s elapsed, status={status}", flush=True)
            if status == "ready":
                return
            if status == "failed":
                raise BrightDataError(f"Snapshot {snapshot_id} failed: {data}")
            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL
        raise BrightDataError(
            f"Snapshot {snapshot_id} did not become ready within {POLL_MAX_WAIT}s"
        )

    def _download(self, snapshot_id: str) -> list[dict]:
        url = f"{API_BASE}/snapshot/{snapshot_id}"
        data = self._request_with_retry("GET", url, params={"format": "json"})
        if isinstance(data, dict):
            data = data.get("data", [])
        print(f"    downloaded {len(data or [])} records", flush=True)
        return data or []

    def _request_with_retry(self, method: str, url: str, **kwargs) -> dict | list:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.request(
                    method, url, headers=self._headers, timeout=TRIGGER_TIMEOUT, **kwargs
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise BrightDataError(f"{resp.status_code} from {url}: {resp.text[:200]}")
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, BrightDataError) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
        raise BrightDataError(f"Request to {url} failed after {MAX_RETRIES} attempts: {last_exc}")

    # -- Response mapping -----------------------------------------------------

    def _map_records(self, handles: list[str], records: list[dict]) -> list[FollowerResult]:
        by_handle = {}
        for record in records:
            handle = self._extract_handle(record)
            if handle:
                by_handle[handle.lower()] = record

        results = []
        for h in handles:
            record = by_handle.get(h.lower())
            results.append(self._map_one(h, record))
        return results

    @staticmethod
    def _extract_handle(record: dict) -> str | None:
        for key in ("account", "username", "user_name", "input_username"):
            if record.get(key):
                return str(record[key])
        for key in ("url", "input", "profile_url"):
            value = record.get(key)
            if value:
                segments = [s for s in str(value).rstrip("/").split("/") if s]
                if segments:
                    return segments[-1]
        return None

    @staticmethod
    def _map_one(handle: str, record: dict | None) -> FollowerResult:
        if record is None:
            return FollowerResult(handle=handle, follower_count=None, status="not_found")

        if record.get("error") or record.get("error_code"):
            return FollowerResult(
                handle=handle, follower_count=None, status="error", raw=record,
                error_message=str(record.get("error") or record.get("error_code")),
            )

        if record.get("is_private"):
            return FollowerResult(handle=handle, follower_count=None, status="private", raw=record)

        for key in ("followers", "followers_count", "follower_count"):
            if record.get(key) is not None:
                try:
                    return FollowerResult(
                        handle=handle, follower_count=int(record[key]), status="ok", raw=record
                    )
                except (TypeError, ValueError):
                    break

        return FollowerResult(
            handle=handle, follower_count=None, status="not_found", raw=record,
        )
