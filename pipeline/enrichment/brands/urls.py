"""
URL canonicalization for source-URL grounding checks.

The same page can be referenced by two slightly different URL strings (with
or without scheme, trailing slash, query string, tracking params, fragment).
canonicalize_url() collapses those differences so a candidate's source_url
can be compared against the set of URLs the web-search tool actually
returned, without false mismatches on cosmetic variation.

This deliberately does NOT try to resolve redirects or follow shortlinks —
it's a string-level normalization, not a network call.
"""

from urllib.parse import urlparse


def canonicalize_url(raw: str | None) -> str | None:
    """Return a comparison-stable form of a URL, or None if raw is empty."""
    if not raw or not isinstance(raw, str):
        return None

    value = raw.strip()
    if not value:
        return None

    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    path = parsed.path.rstrip("/")
    # Query string and fragment are dropped: tracking params (utm_*, ?hl=en,
    # #comments) shouldn't make an otherwise-identical URL look ungrounded.
    return f"{host}{path}"
