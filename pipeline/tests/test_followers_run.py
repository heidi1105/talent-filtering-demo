import json

from enrichment.followers.provider_base import FollowerResult
from enrichment.followers.run import Candidate, build_updates, chunked, normalize_candidates, write_log_atomic


def test_normalize_candidates_splits_valid_and_invalid():
    rows = [
        ("id-1", "Chaeyoung", "@chaeyoung_official"),
        ("id-2", "Bad Handle", "not a handle!"),
        ("id-3", "Full URL", "https://instagram.com/some_user/"),
    ]
    candidates, invalid = normalize_candidates(rows)

    assert [c.handle for c in candidates] == ["chaeyoung_official", "some_user"]
    assert len(invalid) == 1
    assert invalid[0]["talent_id"] == "id-2"


def test_chunked_splits_into_batches():
    batches = list(chunked([1, 2, 3, 4, 5], 2))
    assert batches == [[1, 2], [3, 4], [5]]


def test_build_updates_writes_ok_results():
    candidates = [Candidate(talent_id="id-1", name_en="Chaeyoung", handle="chaeyoung_official")]
    results = [FollowerResult(handle="chaeyoung_official", follower_count=1_200_000, status="ok")]

    updates, failures = build_updates(candidates, results)

    assert updates == [("id-1", 1_200_000)]
    assert failures == []


def test_build_updates_does_not_overwrite_on_error():
    candidates = [Candidate(talent_id="id-1", name_en="Chaeyoung", handle="chaeyoung_official")]
    results = [FollowerResult(handle="chaeyoung_official", follower_count=None, status="error",
                               error_message="timeout")]

    updates, failures = build_updates(candidates, results)

    assert updates == []
    assert failures == [{
        "talent_id": "id-1", "name_en": "Chaeyoung", "handle": "chaeyoung_official",
        "status": "error", "error_message": "timeout",
    }]


def test_build_updates_does_not_overwrite_on_not_found():
    candidates = [Candidate(talent_id="id-1", name_en="Chaeyoung", handle="chaeyoung_official")]
    results = [FollowerResult(handle="chaeyoung_official", follower_count=None, status="not_found")]

    updates, failures = build_updates(candidates, results)

    assert updates == []
    assert failures[0]["status"] == "not_found"


def test_build_updates_handles_missing_response_entry():
    candidates = [Candidate(talent_id="id-1", name_en="Chaeyoung", handle="chaeyoung_official")]

    updates, failures = build_updates(candidates, results=[])

    assert updates == []
    assert failures[0]["status"] == "missing_from_response"


def test_build_updates_case_insensitive_handle_match():
    candidates = [Candidate(talent_id="id-1", name_en="Chaeyoung", handle="chaeyoung_official")]
    results = [FollowerResult(handle="Chaeyoung_Official", follower_count=500, status="ok")]

    updates, _ = build_updates(candidates, results)

    assert updates == [("id-1", 500)]


def test_write_log_atomic_writes_readable_json(tmp_path):
    log_path = tmp_path / "failures_test.json"
    write_log_atomic(log_path, {"batches_completed": 1, "failures": [{"handle": "x"}]})

    assert log_path.exists()
    assert not log_path.with_suffix(".json.tmp").exists()
    with open(log_path) as f:
        data = json.load(f)
    assert data["batches_completed"] == 1


def test_write_log_atomic_overwrites_previous_version(tmp_path):
    log_path = tmp_path / "failures_test.json"
    write_log_atomic(log_path, {"batches_completed": 1})
    write_log_atomic(log_path, {"batches_completed": 2})

    with open(log_path) as f:
        data = json.load(f)
    assert data["batches_completed"] == 2
