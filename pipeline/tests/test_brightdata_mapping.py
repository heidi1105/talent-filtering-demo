from enrichment.followers.providers.brightdata import BrightDataInstagramProvider


def test_map_one_ok():
    record = {"username": "chaeyoung_official", "followers": 1_200_000}
    result = BrightDataInstagramProvider._map_one("chaeyoung_official", record)
    assert result.status == "ok"
    assert result.follower_count == 1_200_000


def test_map_one_private():
    record = {"username": "chaeyoung_official", "is_private": True}
    result = BrightDataInstagramProvider._map_one("chaeyoung_official", record)
    assert result.status == "private"
    assert result.follower_count is None


def test_map_one_error():
    record = {"error": "profile removed"}
    result = BrightDataInstagramProvider._map_one("chaeyoung_official", record)
    assert result.status == "error"
    assert result.error_message == "profile removed"


def test_map_one_missing_record_is_not_found():
    result = BrightDataInstagramProvider._map_one("chaeyoung_official", None)
    assert result.status == "not_found"
    assert result.follower_count is None


def test_map_records_matches_by_handle_case_insensitively():
    provider = BrightDataInstagramProvider.__new__(BrightDataInstagramProvider)
    records = [{"username": "Chaeyoung_Official", "followers": 42}]
    results = provider._map_records(["chaeyoung_official"], records)
    assert results[0].status == "ok"
    assert results[0].follower_count == 42


def test_extract_handle_from_url_field():
    record = {"url": "https://www.instagram.com/some_user/"}
    assert BrightDataInstagramProvider._extract_handle(record) == "some_user"
