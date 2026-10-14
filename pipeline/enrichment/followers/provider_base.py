"""
Provider interface for follower-count lookups.

Any managed scraping vendor (Bright Data today, Apify tomorrow) implements
FollowerProvider so run.py never has to know which vendor is behind it.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class FollowerResult:
    handle: str                 # normalized handle the lookup was requested for
    follower_count: int | None  # None if not found / private / errored
    status: str                 # "ok" | "not_found" | "private" | "error"
    raw: dict | None = None     # provider payload, kept for debugging
    error_message: str | None = None


class FollowerProvider(Protocol):
    def fetch(self, handles: list[str]) -> list[FollowerResult]: ...
