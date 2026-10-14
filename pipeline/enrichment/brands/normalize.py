"""
Brand-name normalization, alias resolution, and brand merging.

Per BRAND_ENRICHMENT_PLAN.md: aliases collapse language/casing/punctuation
variants ('샤넬' -> 'Chanel') onto one brand row. They do NOT collapse
sub-brands — 'Dior' and 'Dior Beauty' stay separate rows; that distinction
is the model's job (see prompt.py), not this module's.

Layout mirrors run.py's split: pure decision logic first (unit tested
directly, no DB), then thin DB glue that just executes those decisions.

BrandCache holds the whole brands + brand_aliases table in memory for the
duration of a run. Two things make this necessary rather than a per-lookup
query: (1) hundreds of talents will repeat the same handful of major
brands, and (2) a brand created for one talent earlier in the SAME run must
resolve correctly for the next talent that mentions it, before that insert
is even committed to a fresh cursor read.
"""

import unicodedata
from dataclasses import dataclass

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}


# ---------------------------------------------------------------------------
# Pure logic — no DB / network.
# ---------------------------------------------------------------------------

def normalize_alias_key(raw: str) -> str:
    """Collapse language/casing/whitespace variants to one lookup key.

    Deliberately conservative: no punctuation stripping, no legal-suffix
    removal, no translation. Doing more than casing/whitespace risks
    collapsing genuinely distinct brands (e.g. stripping "Beauty" would
    merge 'Dior' and 'Dior Beauty', which the plan explicitly forbids).
    Cross-language collapsing ('샤넬' -> 'chanel') happens via an explicit
    brand_aliases row, not by transforming the string here.
    """
    value = unicodedata.normalize("NFKC", raw or "").casefold().strip()
    return " ".join(value.split())  # collapse internal whitespace runs


@dataclass
class BrandResolution:
    action: str              # "alias_hit" | "brand_hit" | "create"
    brand_id: str | None     # set for alias_hit / brand_hit; None for create
    alias_key: str
    display_name: str | None  # set for create: the name to insert into brands


def resolve_brand_name(
    raw_name: str, alias_map: dict[str, str], brand_name_map: dict[str, str]
) -> BrandResolution:
    """Decide how raw_name resolves against already-known aliases/brands.

    alias_map: normalize_alias_key(alias) -> brand_id, from brand_aliases.
    brand_name_map: normalize_alias_key(brands.name) -> brand_id.
    Pure — the caller (BrandCache) does the actual DB reads/writes.
    """
    key = normalize_alias_key(raw_name)
    if key in alias_map:
        return BrandResolution("alias_hit", alias_map[key], key, None)
    if key in brand_name_map:
        return BrandResolution("brand_hit", brand_name_map[key], key, None)
    display_name = " ".join((raw_name or "").strip().split())
    return BrandResolution("create", None, key, display_name)


def choose_survivor(from_row: dict, to_row: dict) -> str:
    """Given two talent_brands rows for the same talent (one currently under
    the brand being merged away, one under the merge target), decide which
    to keep. Returns "from" or "to".

    Precedence: more recent evidence_year, then higher confidence, then
    presence of a source_url, then default to "to" — the caller's chosen
    canonical id — so re-running a merge is a no-op rather than a coin flip.
    Rows are dicts with keys: evidence_year, confidence, source_url.
    """
    fy = from_row.get("evidence_year")
    ty = to_row.get("evidence_year")
    if (fy or -1) != (ty or -1):
        return "from" if (fy or -1) > (ty or -1) else "to"

    fc = _CONFIDENCE_RANK.get(from_row.get("confidence"))
    tc = _CONFIDENCE_RANK.get(to_row.get("confidence"))
    if fc != tc:
        return "from" if fc > tc else "to"

    if bool(from_row.get("source_url")) != bool(to_row.get("source_url")):
        return "from" if from_row.get("source_url") else "to"

    return "to"


@dataclass
class MergePlan:
    repoint: list[str]              # talent_ids with no conflict: brand_id -> to_id directly
    conflicts_keep_from: list[str]  # talent_ids where the from-row's data wins
    conflicts_keep_to: list[str]    # talent_ids where the existing to-row wins (from-row dropped)
    new_alias_key: str              # normalize_alias_key(from brand's name)


def plan_merge(from_name: str, from_rows: dict[str, dict], to_rows: dict[str, dict]) -> MergePlan:
    """from_rows / to_rows: talent_id -> row dict (evidence_year, confidence,
    source_url) for talent_brands currently on from_id / to_id. Pure —
    merge_brand() below just executes this plan against the DB."""
    repoint, keep_from, keep_to = [], [], []
    for talent_id, frow in from_rows.items():
        trow = to_rows.get(talent_id)
        if trow is None:
            repoint.append(talent_id)
        elif choose_survivor(frow, trow) == "from":
            keep_from.append(talent_id)
        else:
            keep_to.append(talent_id)
    return MergePlan(
        repoint=repoint, conflicts_keep_from=keep_from, conflicts_keep_to=keep_to,
        new_alias_key=normalize_alias_key(from_name),
    )


# ---------------------------------------------------------------------------
# DB glue
# ---------------------------------------------------------------------------

class BrandCache:
    """In-memory view of brands + brand_aliases, kept consistent with the DB
    as resolve() creates new brands mid-run. Not thread-safe; one per run.
    """

    def __init__(self, cur):
        self._cur = cur
        cur.execute("SELECT alias, brand_id::text FROM brand_aliases")
        self._alias_map: dict[str, str] = dict(cur.fetchall())
        cur.execute("SELECT id::text, name FROM brands")
        self._brand_name_map: dict[str, str] = {
            normalize_alias_key(name): brand_id for brand_id, name in cur.fetchall()
        }
        self.newly_created: list[dict] = []  # {"brand_id","name"} — for the per-run log

    def resolve(self, raw_name: str) -> str:
        """Return a brand_id for raw_name, creating the brand (+ its own
        alias entry) if it's new. Never returns None."""
        resolution = resolve_brand_name(raw_name, self._alias_map, self._brand_name_map)
        if resolution.action in ("alias_hit", "brand_hit"):
            return resolution.brand_id

        self._cur.execute(
            "INSERT INTO brands (name) VALUES (%s) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
            "RETURNING id::text",
            (resolution.display_name,),
        )
        brand_id = self._cur.fetchone()[0]
        self._brand_name_map[resolution.alias_key] = brand_id
        self._cur.execute(
            "INSERT INTO brand_aliases (alias, brand_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (resolution.alias_key, brand_id),
        )
        self._alias_map[resolution.alias_key] = brand_id
        self.newly_created.append({"brand_id": brand_id, "name": resolution.display_name})
        return brand_id

    def preview_resolve(self, raw_name: str) -> BrandResolution:
        """Read-only version of resolve() for calibration reports — never
        inserts. Still updates the in-memory maps for THIS preview session
        only, so repeated mentions within one calibration run report
        consistently ("would reuse the brand just previewed above") without
        touching the database."""
        resolution = resolve_brand_name(raw_name, self._alias_map, self._brand_name_map)
        if resolution.action == "create":
            self._brand_name_map[resolution.alias_key] = f"<would-create:{resolution.display_name}>"
        return resolution


# psycopg2 adapts a Python list to an untyped array literal, and Postgres
# has no implicit uuid[] <-> text[] cast (unlike a scalar %s, which resolves
# fine against a uuid column) — ANY(%s) against a uuid column needs the
# explicit cast or it 500s with "operator does not exist: uuid = text".
REPOINT_STMT = "UPDATE talent_brands SET brand_id = %s WHERE brand_id = %s AND talent_id = ANY(%s::uuid[])"


def merge_brand(cur, from_id: str, to_id: str) -> dict:
    """Repoints talent_brands from from_id onto to_id, resolves any
    per-talent conflicts via choose_survivor, repoints from_id's existing
    aliases onto to_id, deletes the from_id brand row, and adds the old
    brand's own name as a new alias -> to_id.

    Returns a report dict; raises ValueError if from_id == to_id or either
    id doesn't exist as a brand.
    """
    if from_id == to_id:
        raise ValueError("merge_brand: from_id and to_id are the same brand")

    cur.execute("SELECT name FROM brands WHERE id = %s", (from_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"merge_brand: from_id {from_id} is not a brand")
    from_name = row[0]

    cur.execute("SELECT 1 FROM brands WHERE id = %s", (to_id,))
    if cur.fetchone() is None:
        raise ValueError(f"merge_brand: to_id {to_id} is not a brand")

    def rows_for(brand_id):
        cur.execute(
            "SELECT talent_id::text, evidence_year, confidence, source_url "
            "FROM talent_brands WHERE brand_id = %s",
            (brand_id,),
        )
        return {
            talent_id: {"evidence_year": year, "confidence": confidence, "source_url": source_url}
            for talent_id, year, confidence, source_url in cur.fetchall()
        }

    from_rows = rows_for(from_id)
    to_rows = rows_for(to_id)
    plan = plan_merge(from_name, from_rows, to_rows)

    if plan.repoint:
        cur.execute(REPOINT_STMT, (to_id, from_id, plan.repoint))
    for talent_id in plan.conflicts_keep_from:
        cur.execute("DELETE FROM talent_brands WHERE talent_id = %s AND brand_id = %s", (talent_id, to_id))
        cur.execute(
            "UPDATE talent_brands SET brand_id = %s WHERE talent_id = %s AND brand_id = %s",
            (to_id, talent_id, from_id),
        )
    for talent_id in plan.conflicts_keep_to:
        cur.execute("DELETE FROM talent_brands WHERE talent_id = %s AND brand_id = %s", (talent_id, from_id))

    cur.execute("UPDATE brand_aliases SET brand_id = %s WHERE brand_id = %s", (to_id, from_id))
    aliases_repointed = cur.rowcount

    cur.execute("DELETE FROM brands WHERE id = %s", (from_id,))

    cur.execute("SELECT brand_id::text FROM brand_aliases WHERE alias = %s", (plan.new_alias_key,))
    existing = cur.fetchone()
    alias_conflict = None
    if existing is None:
        cur.execute(
            "INSERT INTO brand_aliases (alias, brand_id) VALUES (%s, %s)",
            (plan.new_alias_key, to_id),
        )
    elif existing[0] != to_id:
        # The old brand's name-as-alias already points somewhere else —
        # surfaced, not silently overwritten (see cleanup.py precedent).
        alias_conflict = {"alias": plan.new_alias_key, "existing_brand_id": existing[0]}

    return {
        "from_id": from_id, "to_id": to_id, "from_name": from_name,
        "repointed": len(plan.repoint),
        "conflicts_kept_from": len(plan.conflicts_keep_from),
        "conflicts_kept_to": len(plan.conflicts_keep_to),
        "aliases_repointed": aliases_repointed,
        "alias_conflict": alias_conflict,
    }


def _main() -> None:
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(
        description="Merge one brand row into another (repoint talent_brands, delete the dupe, alias the old name)."
    )
    parser.add_argument("--from-id", required=True, help="brand id to merge away (deleted)")
    parser.add_argument("--to-id", required=True, help="brand id to keep (survives)")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    import psycopg2

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        report = merge_brand(cur, args.from_id, args.to_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    _main()
