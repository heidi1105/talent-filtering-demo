from enrichment.brands.normalize import (
    REPOINT_STMT, BrandCache, BrandResolution, choose_survivor, normalize_alias_key, plan_merge, resolve_brand_name,
)


def test_repoint_stmt_casts_the_talent_id_array_to_uuid():
    # Regression guard: psycopg2 adapts a Python list to an untyped array
    # literal; without this cast, ANY(%s) against a uuid column 500s live
    # with "operator does not exist: uuid = text" — a scalar %s doesn't
    # need it, only the ANY(...) array form does. Caught by a live check
    # against Supabase, not by mocks, so pinned here too.
    assert "ANY(%s::uuid[])" in REPOINT_STMT


# ---------------------------------------------------------------------------
# normalize_alias_key
# ---------------------------------------------------------------------------

def test_lowercases_and_trims():
    assert normalize_alias_key("  Chanel  ") == "chanel"


def test_collapses_internal_whitespace():
    assert normalize_alias_key("Dior   Beauty") == "dior beauty"


def test_casefolds_unicode():
    assert normalize_alias_key("CHANEL") == normalize_alias_key("chanel")


def test_does_not_collapse_sub_brands():
    # Sub-brand distinctions (Dior vs Dior Beauty) must survive normalization
    # untouched — collapsing them is explicitly out of scope for this key.
    assert normalize_alias_key("Dior") != normalize_alias_key("Dior Beauty")


# ---------------------------------------------------------------------------
# resolve_brand_name
# ---------------------------------------------------------------------------

def test_resolve_alias_hit():
    resolution = resolve_brand_name("샤넬", alias_map={"샤넬": "brand-1"}, brand_name_map={})
    assert resolution == BrandResolution("alias_hit", "brand-1", "샤넬", None)


def test_resolve_brand_hit_case_insensitive():
    resolution = resolve_brand_name("CHANEL", alias_map={}, brand_name_map={"chanel": "brand-1"})
    assert resolution.action == "brand_hit"
    assert resolution.brand_id == "brand-1"


def test_resolve_creates_new_brand_when_unmatched():
    resolution = resolve_brand_name("  Some New Brand  ", alias_map={}, brand_name_map={})
    assert resolution.action == "create"
    assert resolution.brand_id is None
    assert resolution.display_name == "Some New Brand"


def test_resolve_alias_takes_precedence_over_brand_name_match():
    resolution = resolve_brand_name(
        "chanel", alias_map={"chanel": "brand-alias-target"}, brand_name_map={"chanel": "brand-direct"}
    )
    assert resolution.brand_id == "brand-alias-target"


# ---------------------------------------------------------------------------
# choose_survivor
# ---------------------------------------------------------------------------

def test_survivor_prefers_more_recent_evidence_year():
    from_row = {"evidence_year": 2024, "confidence": "low", "source_url": None}
    to_row = {"evidence_year": 2020, "confidence": "high", "source_url": "x"}
    assert choose_survivor(from_row, to_row) == "from"


def test_survivor_prefers_higher_confidence_on_year_tie():
    from_row = {"evidence_year": 2022, "confidence": "high", "source_url": None}
    to_row = {"evidence_year": 2022, "confidence": "low", "source_url": "x"}
    assert choose_survivor(from_row, to_row) == "from"


def test_survivor_prefers_source_url_presence_on_full_tie():
    from_row = {"evidence_year": 2022, "confidence": "medium", "source_url": "x"}
    to_row = {"evidence_year": 2022, "confidence": "medium", "source_url": None}
    assert choose_survivor(from_row, to_row) == "from"


def test_survivor_defaults_to_to_on_complete_tie():
    row = {"evidence_year": 2022, "confidence": "medium", "source_url": "x"}
    assert choose_survivor(dict(row), dict(row)) == "to"


def test_survivor_treats_missing_evidence_year_as_worst():
    from_row = {"evidence_year": None, "confidence": "high", "source_url": "x"}
    to_row = {"evidence_year": 2020, "confidence": "low", "source_url": None}
    assert choose_survivor(from_row, to_row) == "to"


# ---------------------------------------------------------------------------
# plan_merge
# ---------------------------------------------------------------------------

def test_plan_merge_no_conflict_repoints_directly():
    from_rows = {"t1": {"evidence_year": 2022, "confidence": "high", "source_url": "x"}}
    plan = plan_merge("Chanel", from_rows, to_rows={})
    assert plan.repoint == ["t1"]
    assert plan.conflicts_keep_from == []
    assert plan.conflicts_keep_to == []
    assert plan.new_alias_key == "chanel"


def test_plan_merge_conflict_delegates_to_choose_survivor():
    from_rows = {"t1": {"evidence_year": 2024, "confidence": "high", "source_url": "x"}}
    to_rows = {"t1": {"evidence_year": 2020, "confidence": "low", "source_url": None}}
    plan = plan_merge("Chanel", from_rows, to_rows)
    assert plan.conflicts_keep_from == ["t1"]
    assert plan.repoint == []
    assert plan.conflicts_keep_to == []


def test_plan_merge_mixed_talents():
    from_rows = {
        "t1": {"evidence_year": 2022, "confidence": "high", "source_url": "x"},  # no conflict
        "t2": {"evidence_year": 2018, "confidence": "low", "source_url": None},  # loses conflict
    }
    to_rows = {"t2": {"evidence_year": 2023, "confidence": "high", "source_url": "y"}}
    plan = plan_merge("Chanel", from_rows, to_rows)
    assert plan.repoint == ["t1"]
    assert plan.conflicts_keep_to == ["t2"]
    assert plan.conflicts_keep_from == []


# ---------------------------------------------------------------------------
# BrandCache.preview_resolve — in-memory only, no DB writes.
# ---------------------------------------------------------------------------

class _FakeCursor:
    """Serves canned fetchall() results for BrandCache's two init SELECTs.
    preview_resolve() never calls .execute() again after construction, so
    this is all BrandCache needs for the preview path."""

    def __init__(self, alias_rows, brand_rows):
        self._queue = [alias_rows, brand_rows]
        self._current = None

    def execute(self, query, params=None):
        self._current = self._queue.pop(0)

    def fetchall(self):
        return self._current


def test_brand_cache_preview_resolve_alias_hit():
    cur = _FakeCursor(alias_rows=[("샤넬", "brand-1")], brand_rows=[("brand-1", "Chanel")])
    cache = BrandCache(cur)
    resolution = cache.preview_resolve("샤넬")
    assert resolution.action == "alias_hit"
    assert resolution.brand_id == "brand-1"


def test_brand_cache_preview_resolve_new_brand_then_reuses_in_memory():
    cur = _FakeCursor(alias_rows=[], brand_rows=[])
    cache = BrandCache(cur)

    first = cache.preview_resolve("New Brand")
    assert first.action == "create"

    # A second mention within the same preview session resolves as if the
    # brand already existed — without a single additional DB call.
    second = cache.preview_resolve("new brand")
    assert second.action == "brand_hit"
