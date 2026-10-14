"""
07_scrape_kprofiles_groups.py — harvest active K-pop group rosters from Kprofiles.

Wikidata's group-membership graph (P463/P527) is incomplete and lags for many
groups — see seed/group_membership.json: ~1/3 of groups resolve to exactly one
member (multinational groups filtered by citizenship, or members whose
Wikidata item exists but was never linked to the group). Kprofiles maintains
full current rosters per group regardless of individual members' Wikidata
status, so it's the authoritative source for "who is in this group right now."

This script is intentionally separate from the Wikidata pipeline (01-06):
it scrapes HTML instead of querying SPARQL, and it seeds GROUP ROSTERS only —
it does not touch seed/wikidata_raw.json or the DB. Reconciling these rosters
against seed/talents_seed.json (attaching wikidata_id where a name matches) is
a follow-up step, not done here.

SCOPE: active boy groups + active girl groups only (per project decision —
disbanded groups excluded). Two Kprofiles listing pages are the entry point:
  https://kprofiles.com/k-pop-boy-groups/
  https://kprofiles.com/k-pop-girl-groups/

CRASH-SAFE / RESUMABLE, same pattern as 01_fetch_wikidata_seed.py:
  - seed/kprofiles_group_index.json caches the listing scrape (group name,
    profile URL, pre-debut flag). A restart does not re-scrape the 2 index
    pages unless --refresh-index is passed.
  - seed/kprofiles_groups_raw.json caches each group's parsed page. Re-running
    skips any group URL already present, so an interrupted run resumes.
  - Every fetched page is cached as raw HTML under seed/kprofiles_html_cache/
    (keyed by URL) so a re-parse (e.g. after fixing a parsing bug) never
    re-hits the network — delete that folder, or pass --refresh, to force a
    real re-fetch.

OUTPUT (the two deliverables):
  seed/kprofiles_members.json — flat list, one row per member:
      name_en, name_native, other_names, birth_year, nationality,
      social_media, image_url, group_name, group_url, source
  seed/kprofiles_groups.json — one row per group, members nested:
      group_name, group_url, category, pre_debut, official_sns,
      members: [ {name_en, name_native, other_names, birth_year,
                  nationality, social_media, image_url} ]

  other_names is an array of individual name tokens, not one joined string —
  e.g. "Lee Chang Min (이창민)" -> ["Lee Chang Min", "이창민"]; a parenthetical
  with multiple "/"-separated scripts (common for Japanese members, who get
  both a kanji and a Korean-pronunciation rendering) becomes one array entry
  per script.
  social_media values are bare handles, not URLs (both per-member and in
  official_sns) — e.g. ".../instagram.com/handle/?hl=en" -> "handle" — except
  "website", which has no handle concept and keeps the full URL/domain.
  image_url is attributed positionally (the photo nearest to a member's own
  fields, not by any name/alt-text match) — see the image-attribution note
  below.

IMPORTANT — read before trusting the output blindly:
  Kprofiles' page format has drifted over the group's history (older groups
  use "Stage Name:" + "Birth Name:" fields; some newer pages only use
  "Birth Name:"; the newest ones drop "Stage Name" entirely and put the role
  in the heading instead, e.g. "Sophia (Leader)"). The parser below was built
  and verified against one real example of each style, but with 700+ group
  pages there will be formats it doesn't handle. Three things make gaps
  visible rather than silent:
    - every group with zero members parsed, or a "Facts:" line that leaked
      into a field, is printed in the summary and written to
      seed/kprofiles_parse_issues.json for manual spot-checking.
    - pre-debut detection (from the listing page's "*pre-debut" annotation)
      is best-effort text-proximity matching — seed/kprofiles_group_index.json
      is the place to eyeball/correct it before a big run, via --debug-index.
    - image_url attribution assumes each member's photo sits near their own
      "Stage Name:"/"Birth Name:" block (true on the sampled pages) — if a
      page instead puts all member photos in one gallery above the text
      profiles, attribution breaks (photos land on the wrong member, or the
      last member absorbs several). Any group where more than one photo was
      found before the FIRST member's fields is flagged in
      seed/kprofiles_parse_issues.json as "possible top photo-gallery
      layout" — treat image_url as unverified for those until spot-checked.
  Also: I was not able to test this against live Kprofiles HTML from this
  session (kprofiles.com is not reachable from this sandbox) — run it here
  first with --limit 10 and skim the output before doing a full run.

Run:
  python 07_scrape_kprofiles_groups.py --limit 10       # smoke test, 10 groups
  python 07_scrape_kprofiles_groups.py                  # full run (resumes)
  python 07_scrape_kprofiles_groups.py --refresh-index   # re-scrape the 2 listing pages
  python 07_scrape_kprofiles_groups.py --refresh         # ignore all caches, re-fetch everything
  python 07_scrape_kprofiles_groups.py --debug-index     # dump listing-page parse for review, no group pages fetched
Requires network. No DB access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4 import NavigableString, Tag

BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "ul", "ol", "tr", "table", "blockquote", "figure"}

IMG_MARKER = "\x00IMG\x00"   # unlikely-to-collide prefix distinguishing an image "line" from real text

def _img_src(tag) -> str | None:
    """Prefer a lazy-load attribute over `src` — WP lazy-load plugins commonly
    leave a placeholder (often a tiny base64 blob) in `src` and put the real
    URL in data-src/data-lazy-src."""
    for attr in ("data-lazy-src", "data-src", "src"):
        v = (tag.get(attr) or "").strip()
        if v and not v.startswith("data:"):
            return v
    for attr in ("data-srcset", "srcset"):
        v = (tag.get(attr) or "").strip()
        if v:
            first = v.split(",")[0].strip().split(" ")[0].strip()
            if first and not first.startswith("data:"):
                return first
    return None

def flatten_lines(node) -> list[str]:
    """Text of `node`, one entry per visual line: <br> and block-level tags
    (p/div/hN/li/...) start a new line; inline tags (a/strong/em/span/...)
    stay on the current line. Plain get_text("\n") puts every text node
    (including each <a>'s text) on its own line, which splits "Instagram:"
    from the linked "@handle" that follows it — this keeps label and value
    together. An <img> becomes its own marker line ("\\x00IMG\\x00<url>") so
    per-member photos can be attributed positionally later."""
    lines: list[str] = []
    buf: list[str] = []

    def flush():
        text = "".join(buf).strip()
        if text:
            lines.append(text)
        buf.clear()

    def walk(n):
        for child in n.children:
            if isinstance(child, NavigableString):
                buf.append(str(child))
            elif isinstance(child, Tag):
                if child.name == "br":
                    flush()
                elif child.name == "img":
                    flush()
                    src = _img_src(child)
                    if src:
                        lines.append(IMG_MARKER + src)
                elif child.name in BLOCK_TAGS:
                    flush()
                    walk(child)
                    flush()
                else:
                    walk(child)

    walk(node)
    flush()
    return lines

import seedlib as S

SEED        = S.SEED_DIR
HTML_CACHE  = SEED / "kprofiles_html_cache"
INDEX_FILE  = SEED / "kprofiles_group_index.json"
RAW_FILE    = SEED / "kprofiles_groups_raw.json"
MEMBERS_OUT = SEED / "kprofiles_members.json"
GROUPS_OUT  = SEED / "kprofiles_groups.json"
ISSUES_OUT  = SEED / "kprofiles_parse_issues.json"

LISTING_URLS = {
    "boy":  "https://kprofiles.com/k-pop-boy-groups/",
    "girl": "https://kprofiles.com/k-pop-girl-groups/",
}

REQUEST_DELAY   = 1.5   # be polite — kprofiles is a small fan site, not an API
CHECKPOINT_EVERY = 50   # write seed/kprofiles_groups_raw.json every N group pages
UA = S.UA if hasattr(S, "UA") else "TalentSeed/1.1 (internal research tool)"
HEADERS = {"User-Agent": UA}

# ---------------------------------------------------------------------------
# HTTP with on-disk cache (every fetched page, listing or profile)
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path).strip("-")[:60]
    HTML_CACHE.mkdir(parents=True, exist_ok=True)
    return HTML_CACHE / f"{slug or 'page'}-{h}.html"

def fetch(url: str, refresh: bool = False, retries: int = 5) -> str:
    cp = _cache_path(url)
    if not refresh and cp.exists():
        return cp.read_text(encoding="utf-8")
    wait = 5
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(wait); wait = min(wait * 2, 60); continue
            r.raise_for_status()
            cp.write_text(r.text, encoding="utf-8")
            time.sleep(REQUEST_DELAY)
            return r.text
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(wait); wait = min(wait * 2, 60)
    raise RuntimeError(f"failed to fetch {url}")

# ---------------------------------------------------------------------------
# Listing pages -> group index (name, url, pre-debut flag)
# ---------------------------------------------------------------------------

PREDEBUT_RE = re.compile(r"pre[\s-]?debut", re.IGNORECASE)
EXCLUDE_HREF_RE = re.compile(
    r"/(tag|category|author)/"                                  # taxonomy/author archive links, anywhere in the path
    r"|/(disbanded[\w-]*|pre-debut-groups|k-pop-(boy|girl)-groups)/?$",  # nav links back to the listing pages themselves
    re.IGNORECASE,
)

def _trailing_annotation(a_tag) -> str:
    """Text immediately following this <a>, up to the next <a> or <br>,
    walking up through bold/em wrapper tags if the <a> has no siblings of
    its own. Best-effort — see module docstring."""
    node = a_tag
    text = ""
    while node is not None:
        for sib in node.next_siblings:
            name = getattr(sib, "name", None)
            if name == "a":
                return text
            if name == "br":
                return text
            text += sib.get_text() if hasattr(sib, "get_text") else str(sib)
            if len(text) > 80:
                return text
        # nothing more at this level — climb to the parent's siblings once,
        # but only if this level contributed no text (avoids re-walking a
        # long article's entire remaining content for the last link on it)
        if text.strip():
            return text
        parent = node.parent
        if parent is None or parent.name in ("body", "article", "div", None):
            break
        node = parent
    return text

def parse_group_listing(html: str, category: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    content = (soup.select_one("article .entry-content")
               or soup.select_one(".entry-content")
               or soup.select_one("article")
               or soup.body or soup)
    seen: dict[str, dict] = {}
    for a in content.find_all("a", href=True):
        href = a["href"].strip()
        if "kprofiles.com" not in href:
            continue
        if EXCLUDE_HREF_RE.search(href):
            continue
        name = a.get_text(strip=True)
        if not name or len(name) > 80:
            continue
        trailing = _trailing_annotation(a)
        pre_debut = bool(PREDEBUT_RE.search(trailing))
        url = href.split("#")[0].rstrip()
        if not url.endswith("/"):
            url += "/"
        # keep the first occurrence; if the same group is linked twice
        # (rare — e.g. once in a "sub-unit of X" note) prefer whichever
        # occurrence carries the pre-debut flag
        if url in seen:
            seen[url]["pre_debut"] = seen[url]["pre_debut"] or pre_debut
            continue
        seen[url] = {
            "name": name,
            "url": url,
            "category": category,
            "pre_debut": pre_debut,
            "_trailing_raw": trailing.strip()[:60],
        }
    return list(seen.values())

def build_index(refresh_index: bool, debug: bool) -> list[dict]:
    if INDEX_FILE.exists() and not refresh_index:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    entries: dict[str, dict] = {}
    for category, url in LISTING_URLS.items():
        print(f"Fetching listing: {category} -> {url}")
        html = fetch(url, refresh=refresh_index)
        found = parse_group_listing(html, category)
        print(f"  parsed {len(found)} group links")
        for e in found:
            entries[e["url"]] = e
    result = sorted(entries.values(), key=lambda e: (e["category"], e["name"]))
    INDEX_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(result)} groups -> {INDEX_FILE}")
    pre_debut_n = sum(1 for e in result if e["pre_debut"])
    print(f"  {pre_debut_n} flagged pre-debut")
    if debug:
        for e in result:
            flag = "  [PRE-DEBUT]" if e["pre_debut"] else ""
            print(f"  {e['category']:5} {e['name']:<30} {e['url']}{flag}  trailing={e['_trailing_raw']!r}")
    return result

# ---------------------------------------------------------------------------
# Group profile pages -> official SNS + member rows
# ---------------------------------------------------------------------------

FIELD_LABELS = [
    "Stage Name", "Birth Name", "Real Name", "English Name",
    "Position(s)", "Position", "Nationality", "Birthday", "Born",
    "Instagram", "Twitter", "X", "TikTok", "Tik Tok", "YouTube", "Youtube",
    "Weverse", "Facebook", "Website", "Threads",
]
FIELD_RE = re.compile(
    r"^(" + "|".join(re.escape(l) for l in FIELD_LABELS) + r")\s*:\s*(.+)$",
    re.IGNORECASE,
)
ANCHOR_LABELS = ("Stage Name", "Birth Name", "Real Name")
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")
SOCIAL_LABELS = {
    "instagram": "instagram", "twitter": "twitter", "x": "twitter",
    "tiktok": "tiktok", "tik tok": "tiktok", "youtube": "youtube",
    "weverse": "weverse", "facebook": "facebook", "website": "website",
    "threads": "threads",
}
PLATFORM_URL_TEMPLATE = {
    "instagram": "https://www.instagram.com/{h}/",
    "twitter":   "https://x.com/{h}/",
    "tiktok":    "https://www.tiktok.com/@{h}/",
    "youtube":   "https://www.youtube.com/@{h}/",
    "threads":   "https://www.threads.net/@{h}/",
}

def split_name_variants(value: str | None) -> list[str]:
    """'Lee Chang Min (이창민)' -> ['Lee Chang Min', '이창민'];
    'Nakakita Yuma (中耒田悠真 / 나카키타 유마)' -> ['Nakakita Yuma', '中耒田悠真', '나카키타 유마'].
    Splits the parenthetical on '/' since some members (esp. Japanese
    members) get both a kanji and a Korean-pronunciation rendering there."""
    if not value or not value.strip():
        return []
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", value.strip())
    if not m:
        return [value.strip()]
    main = m.group(1).strip()
    variants = [p.strip() for p in m.group(2).split("/") if p.strip()]
    return ([main] if main else []) + variants

def parse_name_native(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", value.strip())
    if m:
        name, native = m.group(1).strip(), m.group(2).strip()
        if not NON_ASCII_RE.search(native):
            # parenthetical with no non-Latin script is a role/status
            # annotation (e.g. "(Leader)"), not a native-script name
            return name, None
        return name, native
    return value.strip(), None

def extract_year(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"((?:19|20)\d{2})", value)
    return int(m.group(1)) if m else None

def build_href_index(soup: BeautifulSoup) -> dict[str, str]:
    """anchor visible-text (normalized) -> href, for resolving social handles
    to real URLs. Last occurrence wins (fields near the bottom of a card are
    more likely to be the actual link than something incidentally matching
    earlier in the page)."""
    idx: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        t = a.get_text(strip=True).lstrip("@").lower()
        if t:
            idx[t] = a["href"]
    return idx

def resolve_social_url(platform: str, raw_value: str, href_index: dict[str, str]) -> str:
    handle = raw_value.strip()
    # strip a trailing "(Company)"/"(Personal)" style annotation
    handle = re.sub(r"\s*\([^)]*\)\s*$", "", handle).strip()
    key = handle.lstrip("@").lower()
    if key in href_index:
        return href_index[key]
    if handle.startswith("http"):
        return handle
    template = PLATFORM_URL_TEMPLATE.get(platform)
    if template and re.match(r"^[\w.\-]+$", key):
        return template.format(h=key)
    return handle  # last resort: just the raw text, better than nothing

_JUNK_PATH_SEGMENTS = {"", "!", "#", "#!"}

def extract_handle(url_or_text: str) -> str:
    """'https://www.instagram.com/0430_live_boy/?hl=en' -> '0430_live_boy';
    'https://twitter.com/#!/dlwnsghek' -> 'dlwnsghek' (old-style Twitter URLs
    put the handle after a '#!/' fragment, which urlparse reports separately
    from the path — both are checked). Falls back to the input stripped of a
    leading '@' if it isn't a URL at all (e.g. a Weverse name that never
    resolved to a link)."""
    if not url_or_text:
        return url_or_text
    if not url_or_text.startswith("http"):
        return url_or_text.strip().lstrip("@")
    parsed = urlparse(url_or_text)
    raw_segments = parsed.path.split("/") + parsed.fragment.split("/")
    segments = [s for s in raw_segments if s and s not in _JUNK_PATH_SEGMENTS]
    if not segments:
        return url_or_text.lstrip("@")
    return segments[0].lstrip("@")

def segment_members(lines: list[str]) -> list[tuple[str | None, list[str], str | None, int]]:
    """Returns (heading, field_lines, image_url, pre_member_image_count) per
    member.

    Image attribution is positional and best-effort: within the gap between
    the previous member's field-anchor and this one's (which is where a
    per-member heading + photo normally sits), take the LAST <img> marker —
    closest to this member's own fields — as their photo. This breaks if a
    page instead puts all member photos in one gallery above the whole text
    block rather than interleaved per member; pre_member_image_count (>1
    images in the zone before the FIRST member) is a signal that's happening
    on this page, surfaced in seed/kprofiles_parse_issues.json for review."""
    present = {lbl: any(re.match(rf"^{re.escape(lbl)}\s*:", l.strip(), re.I)
                         for l in lines if l.strip())
               for lbl in ANCHOR_LABELS}
    anchor_label = next((l for l in ANCHOR_LABELS if present[l]), None)
    if not anchor_label:
        return []
    idxs = [i for i, l in enumerate(lines)
            if re.match(rf"^{re.escape(anchor_label)}\s*:", l.strip(), re.I)]
    blocks = []
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else min(start + 60, len(lines))
        zone_lower = idxs[n - 1] if n > 0 else 0

        heading = None
        for back in range(1, 7):
            j = start - back
            if j < zone_lower or j < 0:
                break
            cand = lines[j].strip()
            if not cand or cand.startswith(IMG_MARKER):
                continue
            if FIELD_RE.match(cand) or cand.lower().endswith("facts:"):
                break
            heading = cand
            break

        image_url = None
        pre_image_count = 0
        for j in range(zone_lower, start):
            if lines[j].startswith(IMG_MARKER):
                pre_image_count += 1
                image_url = lines[j][len(IMG_MARKER):]   # keep overwriting -> last one wins

        block_lines = [l for l in lines[start:end] if not l.startswith(IMG_MARKER)]
        blocks.append((heading, block_lines, image_url, pre_image_count if n == 0 else 0))
    return blocks

def parse_member_block(heading: str | None, block_lines: list[str], image_url: str | None,
                        href_index: dict[str, str]) -> dict:
    fields: dict[str, str] = {}
    for l in block_lines:
        m = FIELD_RE.match(l.strip())
        if m:
            label = m.group(1).strip().lower()
            fields.setdefault(label, m.group(2).strip())

    stage_val = fields.get("stage name") or fields.get("real name")
    if stage_val:
        name, native = parse_name_native(stage_val)
    elif heading:
        h = re.sub(r"^\d+\.\s*", "", heading).strip()
        name, native = parse_name_native(h)
    else:
        name, native = parse_name_native(fields.get("birth name"))

    birth_val = fields.get("birth name")
    other_raw = []
    if birth_val and birth_val.strip() != (stage_val or name or "").strip():
        other_raw.extend(split_name_variants(birth_val))
    if fields.get("english name"):
        other_raw.extend(split_name_variants(fields["english name"]))
    exclude = {(name or "").lower(), (native or "").lower()}
    other_names = []
    for o in other_raw:
        if o.lower() in exclude or o.lower() in {x.lower() for x in other_names}:
            continue
        other_names.append(o)

    social_media = {}
    for label_key, platform in SOCIAL_LABELS.items():
        raw = fields.get(label_key)
        if raw and raw.upper() != "N/A" and platform not in social_media:
            url = resolve_social_url(platform, raw, href_index)
            social_media[platform] = url if platform == "website" else extract_handle(url)

    return {
        "name_en": name,
        "name_native": native,
        "other_names": other_names,
        "birth_year": extract_year(fields.get("birthday") or fields.get("born")),
        "nationality": fields.get("nationality") if (fields.get("nationality", "").upper() != "N/A") else None,
        "social_media": social_media,
        "image_url": image_url,
        "_position": fields.get("position(s)") or fields.get("position"),  # kept for QA, not a requested field
    }

def clean_group_title(raw: str) -> str:
    t = raw
    t = re.sub(r"\s*Members?\s*Profile.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(Updated!?\)\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*Kpop Profiles\s*$", "", t, flags=re.IGNORECASE)
    return t.strip()

def parse_official_sns(lines: list[str], first_anchor_idx: int,
                        href_index: dict[str, str]) -> dict:
    start = None
    for i, l in enumerate(lines[:first_anchor_idx]):
        if re.match(r"^official\s+sns", l.strip(), re.I):
            start = i
            break
    if start is None:
        return {}
    sns = {}
    for l in lines[start + 1:min(start + 16, first_anchor_idx)]:
        m = FIELD_RE.match(l.strip())
        if not m:
            continue
        label = m.group(1).strip().lower()
        platform = SOCIAL_LABELS.get(label)
        if not platform:
            continue
        url = resolve_social_url(platform, m.group(2), href_index)
        sns[platform] = url if platform == "website" else extract_handle(url)
    return sns

def parse_group_page(html: str, group_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content = (soup.select_one("article .entry-content")
               or soup.select_one(".entry-content")
               or soup.select_one("article")
               or soup.body or soup)

    title_tag = soup.find("h1") or soup.find("title")
    raw_title = title_tag.get_text(strip=True) if title_tag else ""
    group_title = clean_group_title(raw_title)

    breadcrumb_text = ""
    bc = soup.select_one(".breadcrumb, nav.breadcrumbs, #breadcrumbs")
    if bc:
        breadcrumb_text = bc.get_text(" ", strip=True)
    is_predebut_page = bool(re.search(r"pre[\s-]?debut", breadcrumb_text, re.I))

    lines = flatten_lines(content)
    href_index = build_href_index(content)

    blocks = segment_members(lines)
    first_anchor_line = None
    for i, l in enumerate(lines):
        if re.match(r"^(Stage Name|Birth Name|Real Name)\s*:", l.strip(), re.I):
            first_anchor_line = i
            break
    official_sns = parse_official_sns(lines, first_anchor_line or len(lines), href_index)

    members = [parse_member_block(h, b, img, href_index) for h, b, img, _pre_cnt in blocks]
    suspected_gallery = any(pre_cnt > 1 for _, _, _, pre_cnt in blocks)

    return {
        "group_title": group_title,
        "official_sns": official_sns,
        "members": members,
        "is_predebut_page": is_predebut_page,
        "member_count_raw": len(members),
        "suspected_photo_gallery_layout": suspected_gallery,
    }

# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def scrape_groups(index: list[dict], refresh: bool, limit: int | None) -> list[dict]:
    raw: dict[str, dict] = {}
    if RAW_FILE.exists() and not refresh:
        for row in json.loads(RAW_FILE.read_text(encoding="utf-8")):
            raw[row["url"]] = row

    todo = index if limit is None else index[:limit]
    total = len(todo)
    for i, entry in enumerate(todo, 1):
        url = entry["url"]
        if not refresh and url in raw:
            continue
        try:
            html = fetch(url, refresh=refresh)
            parsed = parse_group_page(html, url)
        except Exception as ex:  # noqa: BLE001 — log and keep going, 700+ pages
            print(f"  [{i}/{total}] ERROR {url}: {ex}")
            parsed = {"group_title": entry["name"], "official_sns": {},
                      "members": [], "is_predebut_page": False,
                      "member_count_raw": 0, "_error": str(ex)}
        row = {
            "url": url,
            "listing_name": entry["name"],
            "category": entry["category"],
            "pre_debut": entry["pre_debut"] or parsed.get("is_predebut_page", False),
            **{k: v for k, v in parsed.items() if k != "is_predebut_page"},
        }
        raw[url] = row
        n = len(row["members"])
        flag = " [ZERO MEMBERS]" if n == 0 else ""
        print(f"  [{i}/{total}] {row['group_title']:<30} {n} members{flag}")
        if i % CHECKPOINT_EVERY == 0 or i == total:
            RAW_FILE.write_text(json.dumps(list(raw.values()), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  --- checkpoint saved ({i}/{total}) -> {RAW_FILE.name} ---")
    RAW_FILE.write_text(json.dumps(list(raw.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    return list(raw.values())

# Fields a member dict should have. Backfilled onto rows loaded from an
# older seed/kprofiles_groups_raw.json cache that predates a field being
# added (e.g. image_url) — otherwise build_outputs crashes with a KeyError
# on any group that was cached before the new field existed and therefore
# gets skipped by the resume logic in scrape_groups(). Re-run with --refresh
# (or just delete kprofiles_groups_raw.json — cached HTML is unaffected, so
# a re-run without --refresh re-parses it for free) to actually backfill the
# new field's real values instead of these defaults.
MEMBER_DEFAULTS = {
    "name_en": None, "name_native": None, "other_names": [],
    "birth_year": None, "nationality": None, "social_media": {},
    "image_url": None,
}

def _with_member_defaults(m: dict) -> dict:
    return {**MEMBER_DEFAULTS, **m}

def display_group_name(row: dict) -> str:
    name = row["group_title"] or row["listing_name"]
    if row["pre_debut"] and "pre-debut" not in name.lower():
        name = f"{name} (pre-debut)"
    return name

def build_outputs(raw_rows: list[dict]) -> None:
    members_flat = []
    groups_out = []
    issues = []

    for row in raw_rows:
        gname = display_group_name(row)
        if row.get("_error"):
            issues.append({"group": gname, "url": row["url"], "issue": f"fetch/parse error: {row['_error']}"})
        elif row["member_count_raw"] == 0:
            issues.append({"group": gname, "url": row["url"], "issue": "zero members parsed"})
        if row.get("suspected_photo_gallery_layout"):
            issues.append({"group": gname, "url": row["url"],
                            "issue": "multiple photos found before the first member's fields — "
                                     "page likely uses a top photo gallery rather than one photo "
                                     "per member block; image_url attribution is unreliable here"})
        for m in row["members"]:
            m = _with_member_defaults(m)
            if not m.get("birth_year") and not m.get("nationality"):
                issues.append({"group": gname, "member": m.get("name_en"),
                                "url": row["url"], "issue": "missing both birth_year and nationality"})
            members_flat.append({
                "name_en": m["name_en"],
                "name_native": m["name_native"],
                "other_names": m["other_names"],
                "birth_year": m["birth_year"],
                "nationality": m["nationality"],
                "social_media": m["social_media"],
                "image_url": m["image_url"],
                "group_name": gname,
                "group_url": row["url"],
                "source": "kprofiles",
            })
        groups_out.append({
            "group_name": gname,
            "group_url": row["url"],
            "category": row["category"],
            "pre_debut": row["pre_debut"],
            "official_sns": row["official_sns"],
            "members": [{
                "name_en": m["name_en"],
                "name_native": m["name_native"],
                "other_names": m["other_names"],
                "birth_year": m["birth_year"],
                "nationality": m["nationality"],
                "social_media": m["social_media"],
                "image_url": m["image_url"],
            } for m in (_with_member_defaults(m) for m in row["members"])],
        })

    MEMBERS_OUT.write_text(json.dumps(members_flat, ensure_ascii=False, indent=2), encoding="utf-8")
    GROUPS_OUT.write_text(json.dumps(groups_out, ensure_ascii=False, indent=2), encoding="utf-8")
    ISSUES_OUT.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSaved {len(members_flat)} members across {len(groups_out)} groups")
    print(f"  -> {MEMBERS_OUT}")
    print(f"  -> {GROUPS_OUT}")
    zero = sum(1 for r in raw_rows if r["member_count_raw"] == 0)
    predebut = sum(1 for r in groups_out if r["pre_debut"])
    with_image = sum(1 for m in members_flat if m.get("image_url"))
    gallery = sum(1 for r in raw_rows if r.get("suspected_photo_gallery_layout"))
    print(f"  {zero} groups parsed with 0 members (see {ISSUES_OUT.name})")
    print(f"  {predebut} groups flagged pre-debut")
    print(f"  {with_image}/{len(members_flat)} members got an image_url")
    print(f"  {gallery} groups flagged as a possible top photo-gallery layout (image_url unreliable)")
    print(f"  {len(issues)} total issues logged -> {ISSUES_OUT}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap number of group pages fetched (smoke test)")
    ap.add_argument("--refresh-index", action="store_true", help="re-scrape the 2 listing pages instead of using the cached index")
    ap.add_argument("--refresh", action="store_true", help="ignore all caches (index + per-group HTML); re-fetch everything")
    ap.add_argument("--debug-index", action="store_true", help="print the parsed listing index (name/url/pre-debut) and exit — no group pages fetched")
    args = ap.parse_args()

    SEED.mkdir(exist_ok=True)
    index = build_index(refresh_index=args.refresh_index or args.refresh, debug=args.debug_index)
    if args.debug_index:
        return

    print(f"\nScraping {len(index) if args.limit is None else min(args.limit, len(index))} group pages...")
    raw_rows = scrape_groups(index, refresh=args.refresh, limit=args.limit)
    build_outputs(raw_rows)

if __name__ == "__main__":
    main()
