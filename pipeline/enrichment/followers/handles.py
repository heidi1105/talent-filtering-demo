"""
Instagram handle normalization.

Stored values in social_accounts.handle come from earlier scrape stages and
are inconsistent: a bare username, an "@username", or a full profile URL.
normalize_handle() collapses all of those to a bare username, or returns
None if the value doesn't look like a real IG username.
"""

import re
from urllib.parse import urlparse

# instagram.com path segments that are site sections, not usernames.
_RESERVED_PATHS = {
    "p", "reel", "reels", "stories", "explore", "accounts", "tv",
    "directory", "developer", "about", "legal", "web", "embed",
}

# IG usernames: letters, digits, '.', '_'; max 30 chars.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def normalize_handle(raw: str | None) -> str | None:
    """Return a bare IG username, or None if raw doesn't look like one."""
    if not raw or not isinstance(raw, str):
        return None

    value = raw.strip()
    if not value:
        return None

    if "instagram.com" in value.lower():
        if "://" not in value:
            value = "https://" + value
        path = urlparse(value).path
        segments = [s for s in path.split("/") if s]
        if not segments:
            return None
        value = segments[0]
    else:
        # Bare value may still carry a leading '@' or stray query string.
        value = value.split("?")[0].strip("/ ")

    value = value.lstrip("@").strip()

    if not value or value.lower() in _RESERVED_PATHS:
        return None

    if not _USERNAME_RE.match(value):
        return None

    return value.lower()
