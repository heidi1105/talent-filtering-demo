"""
seedlib.py — shared helpers for the Wikidata-first seed pipeline.

Wikidata SPARQL + entity access, occupation normalization, and DB connection.
Imported by 01_fetch_wikidata_seed.py, 02_normalize_merge.py,
03_reconcile_load.py, and audit_dbkpop.py. Importing this file has no side
effects (no network, no DB).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SEED_DIR   = SCRIPT_DIR / "seed"

UA         = "TalentSeed/1.1 (internal research tool)"
HEADERS    = {"User-Agent": UA}
SPARQL_URL = "https://query.wikidata.org/sparql"
WD_API     = "https://www.wikidata.org/w/api.php"
REQUEST_DELAY = 1.0

Q_SOUTH_KOREA = "Q884"

# Occupation anchors -> canonical profession label, in PRIORITY order
# (most specific performing role first; broad catch-alls last). Each anchor's
# subclass tree (P279*) is expanded, so e.g. "film actor" folds into "Actor".
OCCUPATION_ANCHORS = [
    ("Q33999",     "Actor"),
    ("Q2252262",   "Rapper"),
    ("Q177220",    "Singer"),
    ("Q5716684",   "Dancer"),
    ("Q947873",    "TV Host"),        # television presenter
    ("Q13590141",  "TV Host"),        # presenter
    ("Q4610556",   "Model"),
    ("Q245068",    "Comedian"),
    ("Q2906862",   "Influencer"),
    ("Q109459317", "Content Creator"),
    ("Q17125263",  "Content Creator"),  # YouTuber
    ("Q753110",    "Songwriter"),
    ("Q183945",    "Record Producer"),
    ("Q639669",    "Musician"),
    ("Q138858",    "Entertainer"),
]

# Occupations to drop even though they descend from an anchor (matched on label).
DROP_OCCUPATION_KEYWORDS = (
    "pornograph", "porn ", "nude", "erotic", "adult film",
    "scientific model", "ice dancer", "figure skat",
)

# Group types for member discovery — used by 01_fetch_wikidata_seed.py to find
# members of South Korean musical groups regardless of individual P106 claims.
# Each is queried with wdt:P31 (direct instance), not P279*, to stay under
# Wikidata's SPARQL timeout.
GROUP_TYPE_ANCHORS = [
    "Q215380",    # boy band
    "Q641066",    # girl group
    "Q215048",    # musical group
    "Q2088357",   # musical ensemble
    "Q5741069",   # musical duo
]

# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------

def sparql(query: str, retries: int = 5) -> list[dict]:
    wait = 5
    for attempt in range(retries):
        try:
            r = requests.get(SPARQL_URL, params={"query": query, "format": "json"},
                             headers=HEADERS, timeout=90)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(wait); wait = min(wait * 2, 120); continue
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(wait); wait = min(wait * 2, 120)
    return []

def qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]

# ---------------------------------------------------------------------------
# Entity API (batched)
# ---------------------------------------------------------------------------

def api_get(params: dict, retries: int = 6) -> dict:
    params = {**params, "maxlag": 5}   # Wikimedia etiquette: back off when the DB lags
    wait = 10
    for attempt in range(retries):
        try:
            r = requests.get(WD_API, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                ra = r.headers.get("Retry-After")
                time.sleep(int(ra) if ra and ra.isdigit() else wait)
                wait = min(wait * 2, 120); continue
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
                ra = r.headers.get("Retry-After")
                time.sleep(int(ra) if ra and ra.isdigit() else wait)
                wait = min(wait * 2, 120); continue
            return data
        except requests.RequestException:
            # Connection reset / read timeout / DNS blip — retry with backoff
            # instead of letting a transient error kill a long run.
            if attempt == retries - 1:
                raise
            time.sleep(wait); wait = min(wait * 2, 120)
    raise RuntimeError("Wikidata API request failed after retries")

def get_entities(qids: list[str]) -> dict:
    out: dict = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        data = api_get({"action": "wbgetentities", "ids": "|".join(chunk),
                        "format": "json", "props": "claims|labels|aliases",
                        "languages": "en|ko"})
        out.update(data.get("entities", {}))
        time.sleep(REQUEST_DELAY)
    return out

_LABEL_CACHE: dict[str, str] = {}

def resolve_labels(qids: list[str]) -> dict[str, str]:
    todo = [q for q in dict.fromkeys(qids) if q not in _LABEL_CACHE]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        data = api_get({"action": "wbgetentities", "ids": "|".join(chunk),
                        "format": "json", "props": "labels", "languages": "en"})
        for q, e in data.get("entities", {}).items():
            lab = e.get("labels", {}).get("en", {}).get("value", "")
            if lab:
                _LABEL_CACHE[q] = lab
        time.sleep(REQUEST_DELAY)
    return {q: _LABEL_CACHE.get(q, "") for q in qids}

# ---------------------------------------------------------------------------
# Claim extractors
# ---------------------------------------------------------------------------

def claim_qids(entity: dict, prop: str) -> list[str]:
    res = []
    for c in entity.get("claims", {}).get(prop, []):
        dv = c.get("mainsnak", {}).get("datavalue", {})
        if dv.get("type") == "wikibase-entityid":
            res.append(dv["value"]["id"])
    return res

def claim_year(entity: dict, prop: str) -> int | None:
    cs = entity.get("claims", {}).get(prop, [])
    if not cs:
        return None
    t = cs[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
    m = re.match(r"[+-](\d{4})", t)
    return int(m.group(1)) if m else None

def claim_string(entity: dict, prop: str) -> str | None:
    cs = entity.get("claims", {}).get(prop, [])
    if not cs:
        return None
    v = cs[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    return v if isinstance(v, str) else None

def image_url(entity: dict) -> str | None:
    cs = entity.get("claims", {}).get("P18", [])
    if not cs:
        return None
    try:
        fn = cs[0]["mainsnak"]["datavalue"]["value"]
        return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + quote(fn.replace(" ", "_"), safe=""))
    except (KeyError, TypeError):
        return None

def has_hangul(s: str | None) -> bool:
    return bool(s and re.search(r"[가-힣]", s))

GENDER_MAP = {"Q6581097": "Male", "Q6581072": "Female"}

# ---------------------------------------------------------------------------
# Occupation normalization
# ---------------------------------------------------------------------------

def load_occupation_closures() -> dict[str, str]:
    """Return {concrete_occupation_qid: canonical_label}. Builds the subclass
    closure of each anchor via SPARQL once, caches to
    seed/occupation_closure.json. Needs network only on first build."""
    SEED_DIR.mkdir(exist_ok=True)
    cache = SEED_DIR / "occupation_closure.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        raw = {}
        for anchor, _ in OCCUPATION_ANCHORS:
            rows = sparql(f"SELECT ?s WHERE {{ ?s wdt:P279* wd:{anchor} }}")
            raw[anchor] = [qid_from_uri(b["s"]["value"]) for b in rows]
            time.sleep(1)
        cache.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    qid2canon: dict[str, str] = {}
    for anchor, canon in OCCUPATION_ANCHORS:      # priority order: first wins
        for q in raw.get(anchor, []):
            qid2canon.setdefault(q, canon)
    return qid2canon

_ORDER = [canon for _, canon in OCCUPATION_ANCHORS]

def normalize_occupations(occ_qids: list[str], qid2canon: dict[str, str],
                          labels: dict[str, str]) -> list[str]:
    canon: list[str] = []
    for q in occ_qids:
        lab = (labels.get(q, "") or "").lower()
        if any(k in lab for k in DROP_OCCUPATION_KEYWORDS):
            continue
        c = qid2canon.get(q)
        if c and c not in canon:
            canon.append(c)
    canon.sort(key=lambda c: _ORDER.index(c) if c in _ORDER else 999)
    return canon

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def connect():
    try:
        from dotenv import load_dotenv
        load_dotenv(SCRIPT_DIR / ".env")
    except ImportError:
        pass
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set (.env)")
    return psycopg2.connect(url)
