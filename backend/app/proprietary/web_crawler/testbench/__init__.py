# Corvos crawler engine, part of the ``app.proprietary`` package.
# Licensed under the MIT License, like the rest of Corvos. See ``app/proprietary/LICENSE``.
"""Phase 3f - manual undetectability & extraction test harness (dev tooling).

A repeatable, **manual** scorecard that grades the Universal WebURL Crawler on two
axes:

- **Suite S (stealth / anti-bot):** drives the real Scrapling tiers against the
  industry-standard bot-detection + fingerprint sites and parses each verdict.
- **Suite E (extraction correctness):** drives the real ``crawl_url`` ladder
  against ToS-safe scraping sandboxes and asserts known values.

It is **not** collected by pytest (it hits the live internet and needs proxy
creds). Run it from the backend directory:

    uv run python -m app.proprietary.web_crawler.testbench --suite all
    # or: .\\.venv\\Scripts\\python.exe -m app.proprietary.web_crawler.testbench --suite all

See ``README.md`` for the runbook and ``plans/backend/03f-undetectability-testing.md``
for the design. This package is dev/operator tooling, untouched by the product
rename, and only *measures* what 03a-03e built.
"""
