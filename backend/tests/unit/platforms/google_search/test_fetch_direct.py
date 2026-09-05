"""No-proxy (direct-render) branch of :func:`fetch_serp_html`.

The wall is soft on a clean direct IP: a fresh session's first render eats a
429 /sorry page and the same-session re-fetch passes, so the branch retries a
bounded number of times instead of giving up after one render. These tests pin
the retry count and the give-up path offline (no browser, no network).
"""

import asyncio

import pytest

from app.proprietary.platforms.google_search import fetch

pytestmark = pytest.mark.unit

_GOOD_HTML = '<div id="search">results</div>'
_WALL_HTML = "<html>unusual traffic /sorry/</html>"


class _Page:
    def __init__(self, status: int, html: str) -> None:
        self.status = status
        self.html_content = html


def _direct_mode(monkeypatch, pages_or_exc):
    """Point fetch_serp_html at the no-proxy path with scripted renders."""
    monkeypatch.setattr(fetch, "get_proxy_url", lambda: None)
    monkeypatch.setattr(fetch, "_DIRECT_RETRY_BACKOFF_S", 0)
    calls = {"n": 0}

    async def fake_render(url, proxy, mobile=False):
        assert proxy is None, "no-proxy mode must render direct"
        out = pages_or_exc[calls["n"]]
        calls["n"] += 1
        if isinstance(out, Exception):
            raise out
        return out

    monkeypatch.setattr(fetch, "_render", fake_render)
    return calls


def test_direct_retry_passes_after_soft_wall(monkeypatch):
    # Render 1 eats the 429 wall; render 2 lands results -> html returned.
    _direct_mode(
        monkeypatch,
        [_Page(429, _WALL_HTML), _Page(200, _GOOD_HTML)],
    )

    async def main():
        return await fetch.fetch_serp_html("https://www.google.com/search?q=x")

    assert asyncio.run(main()) == _GOOD_HTML


def test_direct_gives_up_after_bounded_attempts(monkeypatch):
    calls = _direct_mode(
        monkeypatch,
        [_Page(429, _WALL_HTML)] * fetch._DIRECT_RENDER_ATTEMPTS,
    )

    async def main():
        return await fetch.fetch_serp_html("https://www.google.com/search?q=x")

    assert asyncio.run(main()) is None
    assert calls["n"] == fetch._DIRECT_RENDER_ATTEMPTS


def test_direct_render_error_is_retried_not_fatal(monkeypatch):
    # A transient browser error on render 1 must not end the attempt loop.
    _direct_mode(
        monkeypatch,
        [RuntimeError("TargetClosedError"), _Page(200, _GOOD_HTML)],
    )

    async def main():
        return await fetch.fetch_serp_html("https://www.google.com/search?q=x")

    assert asyncio.run(main()) == _GOOD_HTML
