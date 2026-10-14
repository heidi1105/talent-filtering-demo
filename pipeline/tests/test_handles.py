from enrichment.followers.handles import normalize_handle


def test_bare_username():
    assert normalize_handle("chaeyoung_official") == "chaeyoung_official"


def test_at_prefixed():
    assert normalize_handle("@chaeyoung_official") == "chaeyoung_official"


def test_full_url():
    assert normalize_handle("https://www.instagram.com/chaeyoung_official/") == "chaeyoung_official"


def test_url_with_query_string():
    assert normalize_handle("https://instagram.com/chaeyoung_official/?hl=en") == "chaeyoung_official"


def test_bare_domain_no_scheme():
    assert normalize_handle("instagram.com/chaeyoung_official") == "chaeyoung_official"


def test_mixed_case_normalizes_lowercase():
    assert normalize_handle("Chaeyoung_Official") == "chaeyoung_official"


def test_invalid_empty():
    assert normalize_handle("") is None


def test_invalid_none():
    assert normalize_handle(None) is None


def test_invalid_reserved_path():
    assert normalize_handle("https://www.instagram.com/p/Cabc123/") is None


def test_invalid_bad_characters():
    assert normalize_handle("not a handle!") is None


def test_invalid_too_long():
    assert normalize_handle("a" * 31) is None
