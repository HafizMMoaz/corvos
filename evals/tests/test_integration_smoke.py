"""Opt-in integration smoke against ``http://localhost:8000``.

Run with ``pytest -m integration``. Skipped by default. Touches the
real backend - requires it to be reachable, OPENROUTER_API_KEY
unrelated, and one credential mode set.
"""

from __future__ import annotations

import os

import httpx
import pytest

from evals.core.auth import acquire_token, client_with_auth
from evals.core.config import load_config

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_smoke_against_localhost():
    if "CORVOS_API_BASE" not in os.environ:
        pytest.skip("CORVOS_API_BASE not set; skipping integration smoke")
    config = load_config()
    if config.credential_mode() == "none":
        pytest.skip("No credentials in environment; skipping integration smoke")
    bundle = await acquire_token(config)
    async with client_with_auth(config, bundle) as client:
        response = await client.get(f"{config.corvos_api_base}/api/v1/model-connections/global")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            pytest.fail(f"Backend rejected smoke call: {exc!s}")
        assert isinstance(response.json(), list)
