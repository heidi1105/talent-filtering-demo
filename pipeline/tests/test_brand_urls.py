from enrichment.brands.urls import canonicalize_url


def test_strips_scheme_and_www():
    assert canonicalize_url("https://www.example.com/Article") == "example.com/Article"


def test_strips_trailing_slash():
    assert canonicalize_url("https://example.com/a/") == "example.com/a"


def test_drops_query_and_fragment():
    assert canonicalize_url("https://example.com/a?utm_source=x#section") == "example.com/a"


def test_adds_missing_scheme():
    assert canonicalize_url("example.com/a") == "example.com/a"


def test_none_and_empty_return_none():
    assert canonicalize_url(None) is None
    assert canonicalize_url("") is None
    assert canonicalize_url("   ") is None


def test_lowercases_host_but_not_path():
    assert canonicalize_url("https://EXAMPLE.com/Path") == "example.com/Path"


def test_two_urls_for_the_same_page_canonicalize_equal():
    a = canonicalize_url("https://www.example.com/news/story/?hl=en")
    b = canonicalize_url("example.com/news/story")
    assert a == b
