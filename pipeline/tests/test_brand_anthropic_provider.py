from types import SimpleNamespace

from enrichment.brands.providers.anthropic_web_search import _extract_observed_urls, _extract_submit_tool_input


def test_extract_submit_tool_input_finds_the_tool_use_block():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="text", text="researching..."),
        SimpleNamespace(type="tool_use", name="submit_affiliations", input={"affiliations": []}),
    ])
    assert _extract_submit_tool_input(response) == {"affiliations": []}


def test_extract_submit_tool_input_ignores_other_tool_use_blocks():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="web_search", input={"query": "x"}),
    ])
    assert _extract_submit_tool_input(response) is None


def test_extract_submit_tool_input_missing_returns_none():
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="...")])
    assert _extract_submit_tool_input(response) is None


def test_extract_observed_urls_collects_and_canonicalizes_dict_items():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="web_search_tool_result", content=[
            {"url": "https://www.example.com/article/?utm_source=x"},
            {"url": "https://example.com/other"},
        ]),
        SimpleNamespace(type="text", text="..."),
    ])
    assert _extract_observed_urls(response) == frozenset({"example.com/article", "example.com/other"})


def test_extract_observed_urls_collects_object_items():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="web_search_tool_result", content=[
            SimpleNamespace(url="https://example.com/a"),
        ]),
    ])
    assert _extract_observed_urls(response) == frozenset({"example.com/a"})


def test_extract_observed_urls_merges_across_multiple_search_blocks():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="web_search_tool_result", content=[{"url": "https://example.com/a"}]),
        SimpleNamespace(type="text", text="..."),
        SimpleNamespace(type="web_search_tool_result", content=[{"url": "https://example.com/b"}]),
    ])
    assert _extract_observed_urls(response) == frozenset({"example.com/a", "example.com/b"})


def test_extract_observed_urls_ignores_non_search_blocks():
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="submit_affiliations", input={}),
    ])
    assert _extract_observed_urls(response) == frozenset()


def test_extract_observed_urls_handles_empty_content():
    response = SimpleNamespace(content=[])
    assert _extract_observed_urls(response) == frozenset()


def test_extract_observed_urls_skips_a_failed_search_error_block():
    # block.content is a union: a list of results, OR a single
    # WebSearchToolResultError object (not iterable) when the search
    # itself failed. Must not raise, must not contribute a URL.
    error_content = SimpleNamespace(type="web_search_tool_result_error", error_code="unavailable")
    response = SimpleNamespace(content=[
        SimpleNamespace(type="web_search_tool_result", content=error_content),
        SimpleNamespace(type="web_search_tool_result", content=[{"url": "https://example.com/ok"}]),
    ])
    assert _extract_observed_urls(response) == frozenset({"example.com/ok"})
