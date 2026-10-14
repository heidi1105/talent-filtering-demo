from enrichment.brands.provider_base import AffiliationCandidate, BrandResearchResult, TalentQuery
from enrichment.brands.run import TALENTS_BY_ID_QUERY, build_talent_queries, dedupe_resolved_rows, validate_candidates


def test_talents_by_id_query_casts_the_id_array_to_uuid():
    # Same regression class as normalize.REPOINT_STMT — ANY(%s) against a
    # uuid column needs an explicit cast or it 500s live against Supabase.
    assert "ANY(%(talent_ids)s::uuid[])" in TALENTS_BY_ID_QUERY


# ---------------------------------------------------------------------------
# build_talent_queries
# ---------------------------------------------------------------------------

def test_build_talent_queries_maps_all_fields():
    rows = [("id-1", "Chaeyoung", "채영", ["Chaeng"], "TWICE", ["Singer"], "South Korean")]
    queries = build_talent_queries(rows)
    assert queries == [TalentQuery(
        talent_id="id-1", name_en="Chaeyoung", name_native="채영",
        other_names=["Chaeng"], group_name="TWICE", occupation=["Singer"], nationality="South Korean",
    )]


def test_build_talent_queries_handles_null_arrays_and_names():
    rows = [("id-1", "Someone", None, None, None, None, None)]
    queries = build_talent_queries(rows)
    assert queries[0].other_names == []
    assert queries[0].occupation == []
    assert queries[0].name_native is None


# ---------------------------------------------------------------------------
# validate_candidates
# ---------------------------------------------------------------------------

def _candidate(**overrides):
    defaults = dict(
        brand_name="Chanel", status="current", source_url="https://example.com/a",
        evidence_year=2024, confidence="high", evidence_note="named ambassador",
    )
    defaults.update(overrides)
    return AffiliationCandidate(**defaults)


def test_accepts_a_complete_grounded_candidate():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate()],
                                  observed_urls=frozenset({"example.com/a"}))
    valid, rejected = validate_candidates(result)
    assert len(valid) == 1
    assert rejected == []


def test_rejects_missing_source_url():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate(source_url="")],
                                  observed_urls=frozenset())
    valid, rejected = validate_candidates(result)
    assert valid == []
    assert rejected[0]["reasons"] == ["missing_source_url"]


def test_rejects_missing_evidence_year():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate(evidence_year=None)],
                                  observed_urls=frozenset({"example.com/a"}))
    _, rejected = validate_candidates(result)
    assert rejected[0]["reasons"] == ["missing_evidence_year"]


def test_rejects_evidence_year_before_window():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate(evidence_year=2015)],
                                  observed_urls=frozenset({"example.com/a"}))
    _, rejected = validate_candidates(result)
    assert rejected[0]["reasons"] == ["evidence_year_too_old"]


def test_rejects_url_the_provider_never_actually_saw():
    result = BrandResearchResult(
        talent_id="id-1", affiliations=[_candidate(source_url="https://fabricated.example/x")],
        observed_urls=frozenset({"example.com/a"}),
    )
    _, rejected = validate_candidates(result)
    assert rejected[0]["reasons"] == ["url_not_grounded"]


def test_rejects_status_outside_current_or_past():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate(status="not signed")],
                                  observed_urls=frozenset({"example.com/a"}))
    _, rejected = validate_candidates(result)
    assert "invalid_status" in rejected[0]["reasons"]


def test_rejects_confidence_outside_rubric():
    result = BrandResearchResult(talent_id="id-1", affiliations=[_candidate(confidence="certain")],
                                  observed_urls=frozenset({"example.com/a"}))
    _, rejected = validate_candidates(result)
    assert "invalid_confidence" in rejected[0]["reasons"]


def test_a_candidate_can_fail_multiple_checks_at_once():
    result = BrandResearchResult(
        talent_id="id-1",
        affiliations=[_candidate(source_url="", evidence_year=None)],
        observed_urls=frozenset(),
    )
    _, rejected = validate_candidates(result)
    assert set(rejected[0]["reasons"]) == {"missing_source_url", "missing_evidence_year"}


def test_provider_error_short_circuits_to_a_single_rejected_entry():
    result = BrandResearchResult(talent_id="id-1", status="error", error_message="timeout")
    valid, rejected = validate_candidates(result)
    assert valid == []
    assert rejected == [{
        "talent_id": "id-1", "brand_name": None, "source_url": None,
        "reasons": ["provider_error"], "detail": "timeout",
    }]


def test_empty_affiliations_list_is_a_valid_non_rejected_result():
    result = BrandResearchResult(talent_id="id-1", affiliations=[], observed_urls=frozenset())
    valid, rejected = validate_candidates(result)
    assert valid == []
    assert rejected == []


# ---------------------------------------------------------------------------
# dedupe_resolved_rows
# ---------------------------------------------------------------------------

def test_dedupe_keeps_the_stronger_of_two_same_brand_rows():
    rows = [
        {"talent_id": "t1", "brand_id": "b1", "evidence_year": 2020, "confidence": "low", "source_url": None},
        {"talent_id": "t1", "brand_id": "b1", "evidence_year": 2024, "confidence": "high", "source_url": "x"},
    ]
    kept, dropped = dedupe_resolved_rows(rows)
    assert len(kept) == 1
    assert kept[0]["evidence_year"] == 2024
    assert len(dropped) == 1


def test_dedupe_leaves_different_brands_alone():
    rows = [
        {"talent_id": "t1", "brand_id": "b1", "evidence_year": 2020, "confidence": "low", "source_url": None},
        {"talent_id": "t1", "brand_id": "b2", "evidence_year": 2020, "confidence": "low", "source_url": None},
    ]
    kept, dropped = dedupe_resolved_rows(rows)
    assert len(kept) == 2
    assert dropped == []
