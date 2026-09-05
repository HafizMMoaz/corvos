"""Google's ``/goto?url=`` encrypted redirect wrappers (2026-08 layout).

The parser keeps token hrefs as-is (no plaintext target exists in the page);
the scraper swaps them for destination URLs via :func:`resolve_goto_url`, which
follows the redirect endpoint's 302 Location. All offline (no network).
"""

import asyncio

import pytest

from app.proprietary.platforms.google_search import fetch, scraper
from app.proprietary.platforms.google_search.parsers import parse_serp
from app.proprietary.platforms.google_search.schemas import (
    OrganicResult,
    PaidProduct,
    PaidResult,
    SerpItem,
    SiteLink,
)

pytestmark = pytest.mark.unit

_GOTO_FIXTURE = """
<html><body>
  <div id="rso">
    <div class="tF2Cxc">
      <a href="/goto?url=CAESTOKEN"><h3>Wrapped Result</h3>
        <cite>https://example.com</cite></a>
      <div class="VwiC3b">Snippet text.</div>
    </div>
    <div class="tF2Cxc">
      <a href="https://direct.example/page"><h3>Direct Result</h3></a>
      <div class="VwiC3b">Snippet text.</div>
    </div>
  </div>
</body></html>
"""


def test_parser_keeps_goto_token_href():
    # A /goto-wrapped anchor still yields a result; the token is kept verbatim
    # for the scraper's resolution pass (a plaintext http anchor still wins).
    item = parse_serp(_GOTO_FIXTURE)
    assert [r.url for r in item.organicResults] == [
        "/goto?url=CAESTOKEN",
        "https://direct.example/page",
    ]


def _item_with_gotos() -> SerpItem:
    return SerpItem(
        organicResults=[
            OrganicResult(
                title="a",
                url="/goto?url=T1",
                siteLinks=[SiteLink(title="s1", url="/goto?url=T2")],
            ),
            OrganicResult(title="b", url="https://direct.example/x"),
        ],
        paidResults=[
            PaidResult(
                title="ad",
                url="/goto?url=T3",
                siteLinks=[SiteLink(title="s2", url="https://direct.example/y")],
            )
        ],
        paidProducts=[PaidProduct(title="p", url="/goto?url=T1")],
    )


def test_resolve_goto_links_swaps_tokens_in_place(monkeypatch):
    resolved_map = {
        "/goto?url=T1": "https://one.example/",
        "/goto?url=T2": "https://two.example/",
        "/goto?url=T3": "https://three.example/",
    }
    calls = {"n": 0}

    async def fake_resolve(url: str) -> str:
        calls["n"] += 1
        return resolved_map.get(url, url)

    monkeypatch.setattr(scraper, "resolve_goto_url", fake_resolve)
    item = _item_with_gotos()

    asyncio.run(scraper._resolve_goto_links(item))

    assert item.organicResults[0].url == "https://one.example/"
    assert item.organicResults[0].siteLinks[0].url == "https://two.example/"
    assert item.organicResults[1].url == "https://direct.example/x"  # untouched
    assert item.paidResults[0].url == "https://three.example/"
    assert item.paidResults[0].siteLinks[0].url == "https://direct.example/y"
    assert item.paidProducts[0].url == "https://one.example/"


def test_resolve_goto_links_noop_without_tokens():
    item = SerpItem(organicResults=[OrganicResult(title="a", url="https://x.example/")])
    # No /goto hrefs: nothing to resolve, and resolve_goto_url must not run.
    asyncio.run(scraper._resolve_goto_links(item))
    assert item.organicResults[0].url == "https://x.example/"


class _FakeResponse:
    def __init__(self, status: int, location: str | None) -> None:
        self.status = status
        self.headers = {"location": location} if location else {}


@pytest.fixture(autouse=True)
def _clean_goto_cache():
    fetch._GOTO_CACHE.clear()
    yield
    fetch._GOTO_CACHE.clear()


def test_resolve_goto_url_follows_redirect_and_caches(monkeypatch):
    fetches = {"n": 0}

    async def fake_get(url, **_kwargs):
        fetches["n"] += 1
        return _FakeResponse(302, "https://dest.example/page")

    monkeypatch.setattr(fetch, "AsyncFetcher", type("F", (), {"get": staticmethod(fake_get)}))
    goto = "/goto?url=CAESTOKEN"

    assert asyncio.run(fetch.resolve_goto_url(goto)) == "https://dest.example/page"
    assert asyncio.run(fetch.resolve_goto_url(goto)) == "https://dest.example/page"
    assert fetches["n"] == 1  # second hit served from the cache


def test_resolve_goto_url_passes_direct_urls_through():
    assert asyncio.run(fetch.resolve_goto_url("https://plain.example/")) == (
        "https://plain.example/"
    )


def test_resolve_goto_url_falls_back_to_redirect_url(monkeypatch):
    # No Location / non-redirect status: keep the absolute google.com/goto URL
    # rather than dropping the result.
    async def fake_get(url, **_kwargs):
        return _FakeResponse(200, None)

    monkeypatch.setattr(fetch, "AsyncFetcher", type("F", (), {"get": staticmethod(fake_get)}))
    assert asyncio.run(fetch.resolve_goto_url("/goto?url=CAESTOKEN")) == (
        "https://www.google.com/goto?url=CAESTOKEN"
    )
