"""
Enrichment prompt design for brand-affiliation research.

This is the module that stands between "open-ended web research" and a
database write. The rules baked in here are the settled decisions from
BRAND_ENRICHMENT_PLAN.md / CLAUDE.md — do not relitigate them here; if a
decision changes, change it there first and mirror it into this file.

Two tools are offered to the model in the same call:
  - `web_search` (hosted/server-side): the model researches with it freely.
    See WEB_SEARCH_TOOL_TYPE note below.
  - `submit_affiliations` (client-side, defined in this file): the model's
    forced final action. Its JSON schema is enforced by the API, so a
    malformed answer surfaces as a provider error, not a bad row that slips
    through a free-text parse.

The empty-list case is not a fallback path, it's the expected outcome for
most talents most of the time — the system prompt says so explicitly,
because a model that isn't told "no results is fine" will strain to find
something rather than say nothing.
"""

DEFAULT_MODEL = "claude-sonnet-5"

# Hosted web-search tool type string. This is a versioned/dated identifier
# on Anthropic's side (like Bright Data's dataset IDs). Confirmed present in
# the installed anthropic SDK (0.84.0) as of this writing — it also still
# ships the older "web_search_20250305" for backward compat, so if this
# dated version 404s on a future SDK upgrade, that's the fallback to try.
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"

MIN_EVIDENCE_YEAR = 2016  # "Capture 10 years (2016+)" — decisions table


SYSTEM_PROMPT = """\
You are a research assistant verifying commercial brand endorsements for a \
curated talent database. Precision matters far more than completeness: \
an EMPTY result is a good, expected outcome and is much better than a \
wrong one. Do not strain to find something. Most talents you research will \
have zero qualifying affiliations — that is normal, not a failure.

IMPORTANT: Do NOT use code_execution. Do not write or run any code. Only use \
web_search to research, then call submit_affiliations with your findings. \
Keep your research concise — read search result snippets directly, do not \
write scripts to process them.

What counts as an affiliation
- A commercial brand relationship: brand ambassador, spokesperson, face of \
a campaign, official endorsement, or a reported contract/partnership.
- Both CURRENT and PAST relationships count. Do not include anything from \
before {min_year}.
- Does NOT count: a single paparazzi/red-carpet photo of them wearing a \
brand with no reported relationship, a drama/film role (that's filmography, \
not a brand deal), a brand merely being mentioned near their name, or fan \
speculation.
- `Dior` and `Dior Beauty` (and similar sub-brand splits) are DIFFERENT \
affiliations — report the specific brand/sub-brand name exactly as your \
source names it. Do not merge or rename brands yourself; that normalization \
happens downstream.

Search requirement
- Search using BOTH names given below: the English name AND the Korean \
native name. Korean-language endorsement news (브랜드 앰버서더, 모델 발탁, etc.) \
routinely does not surface in English-only queries, and is often the only \
place a Korean brand deal is reported at all.

Evidence bar — every affiliation you report MUST have both of these, or you \
must leave it out:
1. `source_url` — a URL you actually saw in your search results. Never \
invent, guess, or reconstruct a plausible-looking URL. If you can't point \
to a specific URL you retrieved, you don't have a source.
2. `evidence_year` — the year the evidence is dated to (article/announcement \
date, or the year a contract/campaign was reported), {min_year} or later.

Confidence — apply this rubric exactly, don't soften it:
- "high": a named brand + explicit ambassador/endorsement wording, sourced \
from the brand's own PR/site or a major outlet.
- "medium": one credible source, OR the affiliation is implied rather than \
stated outright.
- "low": sourced only from a fan site, aggregator, or unofficial fan wiki.

`status` must be exactly "current" or "past" — never anything else \
(a "not signed" status is assigned manually elsewhere, not by you).

When you are done researching, call `submit_affiliations` exactly once, as \
your last action, with your final list. If you found nothing that clears \
the evidence bar, call it with an empty `affiliations` array — that is a \
complete and correct answer, not something to apologize for or work around.
""".format(min_year=MIN_EVIDENCE_YEAR)


def build_user_message(talent) -> str:
    """talent: a provider_base.TalentQuery."""
    lines = [
        f"English name: {talent.name_en}",
        f"Korean / native name: {talent.name_native or '(not on file — search English name only)'}",
    ]
    if talent.other_names:
        lines.append(f"Other known names/aliases: {', '.join(talent.other_names)}")
    if talent.group_name:
        lines.append(f"Group: {talent.group_name}")
    if talent.occupation:
        lines.append(f"Occupation: {', '.join(talent.occupation)}")
    if talent.nationality:
        lines.append(f"Nationality: {talent.nationality}")
    lines.append(
        "\nResearch this person's brand/commercial endorsement affiliations "
        "(current and past, {}+). Search in both English and Korean. Then "
        "call submit_affiliations with your findings, or with an empty list "
        "if nothing clears the evidence bar.".format(MIN_EVIDENCE_YEAR)
    )
    return "\n".join(lines)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


SUBMIT_TOOL = {
    "name": "submit_affiliations",
    "description": (
        "Submit the final list of verified brand affiliations for this talent. "
        "Call this exactly once, as your last action, even when the list is "
        "empty — an empty list is a valid and often-correct answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "affiliations": {
                "type": "array",
                "description": "Zero or more verified brand affiliations. Empty is fine and expected.",
                "items": {
                    "type": "object",
                    "properties": {
                        "brand_name": {
                            "type": "string",
                            "description": "The brand/sub-brand name exactly as your source names it.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["current", "past"],
                        },
                        "source_url": {
                            "type": "string",
                            "description": "A URL you actually retrieved in search results — never invented.",
                        },
                        "evidence_year": {
                            "type": "integer",
                            "description": f"Year the evidence is dated to, {MIN_EVIDENCE_YEAR} or later.",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "evidence_note": {
                            "type": "string",
                            "description": "One sentence, in your own words, on what the source says.",
                        },
                    },
                    "required": [
                        "brand_name", "status", "source_url",
                        "evidence_year", "confidence", "evidence_note",
                    ],
                },
            },
        },
        "required": ["affiliations"],
    },
}
