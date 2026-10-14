"""
Provider interface for brand-affiliation web research.

Any AI/web-research backend (Anthropic today) implements BrandProvider so
run.py and calibrate.py never have to know which vendor or prompt mechanics
are behind it. Mirrors enrichment/followers/provider_base.py — but note the
shape is different in one important way: FollowerResult is a deterministic
lookup answer, while BrandResearchResult is an open-ended research answer
that carries its own evidence (observed_urls, raw) so the caller can check
it rather than trust it. See run.py's validate_candidates().
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TalentQuery:
    """Everything the prompt needs to identify a talent and search for them
    in both English and Korean."""
    talent_id: str
    name_en: str
    name_native: str | None
    other_names: list[str]
    group_name: str | None
    occupation: list[str]
    nationality: str | None


@dataclass
class AffiliationCandidate:
    """One brand affiliation as reported by the provider — not yet
    validated. brand_name is the raw string the model used; run.py resolves
    it to a brand_id via normalize.py before anything is written."""
    brand_name: str
    status: str                    # "current" | "past" (model-constrained; never "not signed")
    source_url: str
    evidence_year: int | None
    confidence: str                # "high" | "medium" | "low"
    evidence_note: str | None = None


@dataclass
class BrandResearchResult:
    talent_id: str
    affiliations: list[AffiliationCandidate] = field(default_factory=list)
    status: str = "ok"             # "ok" | "error"
    error_message: str | None = None
    # URLs the provider's web-search tool actually returned during this
    # talent's research call, canonicalized (see urls.py). Used to check
    # that a candidate's source_url wasn't invented — it must be a URL the
    # model actually saw, not just a plausible-looking one.
    observed_urls: frozenset[str] = field(default_factory=frozenset)
    raw: dict | None = None        # full provider response, logged to disk


class BrandProvider(Protocol):
    def research(self, talents: list[TalentQuery]) -> list[BrandResearchResult]: ...
