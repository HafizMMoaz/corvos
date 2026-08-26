"""Unit tests for the free-tier quota orchestrator wrapper
(`app.tasks.chat.streaming.flows.shared.free_quota`).

Mirrors the scope `test_premium_quota.py` would have if one existed for its
sibling `premium_quota.py`: `needs_free_quota`'s truth table, plus
reserve/finalize/release wrapper behavior against a mocked service layer
(`app.services.free_model_quota_service`) -- these tests never touch
Postgres, that coverage lives in
`tests/integration/test_free_model_quota_service.py`.
"""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.chat.runtime.llm_config import AgentConfig
from app.services.free_model_quota_service import FreeQuotaResult
from app.tasks.chat.streaming.flows.shared.free_quota import (
    FreeQuotaReservation,
    finalize_free_quota,
    needs_free_quota,
    release_free_quota,
    reserve_free_quota,
)

pytestmark = pytest.mark.unit


def _agent_config(
    *, is_premium: bool = False, quota_reserve_tokens=None, config_id: int | None = -1
) -> AgentConfig:
    """A platform-catalog-sourced config by default (`config_id=-1`, the YAML
    static range). Pass a positive `config_id` for the BYOK shape: a user's
    own workspace `Model` row, which `llm_bundle.py` also stamps
    `billing_tier="free"` / `is_premium=False` on."""
    return AgentConfig(
        provider="openai",
        model_name="gpt-test",
        api_key="sk-test",
        is_premium=is_premium,
        quota_reserve_tokens=quota_reserve_tokens,
        config_id=config_id,
    )


# ---------------------------------------------------------------------------
# needs_free_quota truth table
# ---------------------------------------------------------------------------


def test_needs_free_quota_true_for_free_agent_config_with_user_id():
    assert needs_free_quota(_agent_config(is_premium=False), "user-1") is True


def test_needs_free_quota_false_when_agent_config_is_none():
    assert needs_free_quota(None, "user-1") is False


def test_needs_free_quota_false_when_user_id_is_none():
    assert needs_free_quota(_agent_config(is_premium=False), None) is False


def test_needs_free_quota_false_when_user_id_is_empty_string():
    assert needs_free_quota(_agent_config(is_premium=False), "") is False


def test_needs_free_quota_false_when_agent_config_is_premium():
    assert needs_free_quota(_agent_config(is_premium=True), "user-1") is False


def test_needs_free_quota_false_for_byok_model():
    """A BYOK model (`config_id > 0`: a user's own workspace connection with
    their own API key) must never be charged against the platform's shared
    free-tier caps. `llm_bundle.py` hardcodes `billing_tier="free"` on that
    path, which has only ever meant "skip the premium credit wallet" -- so
    `is_premium=False` alone cannot be the test."""
    assert (
        needs_free_quota(_agent_config(is_premium=False, config_id=42), "user-1")
        is False
    )


@pytest.mark.parametrize(
    "config_id",
    [
        -1,  # YAML static range
        -999,  # YAML static range, far end
        -10_001,  # OpenRouter dynamic range
        -100_042,  # admin-DB-sourced range
    ],
)
def test_needs_free_quota_true_for_every_platform_catalog_id_range(config_id):
    """Every negative id range is platform-funded and must still be capped."""
    assert (
        needs_free_quota(_agent_config(is_premium=False, config_id=config_id), "user-1")
        is True
    )


def test_needs_free_quota_false_when_config_id_is_unset():
    """No resolved config id means nothing has been proven to be a
    platform-catalog model, so don't charge the shared caps."""
    assert (
        needs_free_quota(_agent_config(is_premium=False, config_id=None), "user-1")
        is False
    )


def test_needs_free_quota_false_for_unresolved_auto_mode_sentinel():
    """`config_id == 0` is the Auto-mode sentinel, not a model.
    `resolve_initial_auto_pin` always resolves it to one concrete id before
    `load_llm_bundle` runs, so this should be unreachable in practice -- but
    the sentinel is not a platform-funded model and must not be treated as
    one if it ever does arrive here."""
    assert (
        needs_free_quota(_agent_config(is_premium=False, config_id=0), "user-1")
        is False
    )


# ---------------------------------------------------------------------------
# reserve_free_quota
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reserve_free_quota_allowed_uses_model_quota_reserve_tokens():
    user_id = str(uuid4())
    with patch(
        "app.services.free_model_quota_service.free_quota_reserve",
        new_callable=AsyncMock,
    ) as mock_reserve:
        mock_reserve.return_value = FreeQuotaResult(allowed=True)

        reservation = await reserve_free_quota(
            agent_config=_agent_config(quota_reserve_tokens=1234), user_id=user_id
        )

    assert reservation.allowed is True
    assert reservation.reserved_tokens == 1234
    assert reservation.reason is None
    mock_reserve.assert_awaited_once()
    _, kwargs = mock_reserve.await_args
    assert str(kwargs["user_id"]) == user_id
    assert kwargs["reserve_tokens"] == 1234


@pytest.mark.asyncio
async def test_reserve_free_quota_falls_back_to_config_default_reserve():
    from app.config import config

    user_id = str(uuid4())
    with patch(
        "app.services.free_model_quota_service.free_quota_reserve",
        new_callable=AsyncMock,
    ) as mock_reserve:
        mock_reserve.return_value = FreeQuotaResult(allowed=True)

        reservation = await reserve_free_quota(
            agent_config=_agent_config(quota_reserve_tokens=None), user_id=user_id
        )

    assert reservation.reserved_tokens == config.QUOTA_MAX_RESERVE_PER_CALL


@pytest.mark.asyncio
async def test_reserve_free_quota_denied_propagates_reason():
    user_id = str(uuid4())
    with patch(
        "app.services.free_model_quota_service.free_quota_reserve",
        new_callable=AsyncMock,
    ) as mock_reserve:
        mock_reserve.return_value = FreeQuotaResult(
            allowed=False, reason="global_cap_exhausted"
        )

        reservation = await reserve_free_quota(
            agent_config=_agent_config(quota_reserve_tokens=500), user_id=user_id
        )

    assert reservation.allowed is False
    assert reservation.reason == "global_cap_exhausted"


# ---------------------------------------------------------------------------
# finalize_free_quota
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_free_quota_uses_accumulator_grand_total():
    user_id = str(uuid4())
    reservation = FreeQuotaReservation(reserved_tokens=1000, allowed=True)
    accumulator = AsyncMock()
    accumulator.grand_total = 777

    with patch(
        "app.services.free_model_quota_service.free_quota_finalize",
        new_callable=AsyncMock,
    ) as mock_finalize:
        await finalize_free_quota(
            reservation=reservation, user_id=user_id, accumulator=accumulator
        )

    mock_finalize.assert_awaited_once()
    _, kwargs = mock_finalize.await_args
    assert str(kwargs["user_id"]) == user_id
    assert kwargs["actual_tokens"] == 777
    assert kwargs["reserved_tokens"] == 1000


@pytest.mark.asyncio
async def test_finalize_free_quota_swallows_exceptions():
    reservation = FreeQuotaReservation(reserved_tokens=1000, allowed=True)
    accumulator = AsyncMock()
    accumulator.grand_total = 100

    with patch(
        "app.services.free_model_quota_service.free_quota_finalize",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        # Must not raise -- best-effort, same as finalize_credit.
        await finalize_free_quota(
            reservation=reservation, user_id=str(uuid4()), accumulator=accumulator
        )


@pytest.mark.asyncio
async def test_finalize_free_quota_denied_reservation_never_calls_service():
    """Regression test for the Critical bug found in review: a denied
    (`allowed=False`) reservation never actually reserved anything --
    `free_quota_reserve` rolls back before returning on denial -- so
    finalizing it would debit tokens the caps never admitted. Must be a
    guaranteed no-op, not just a coincidentally-harmless one."""
    reservation = FreeQuotaReservation(
        reserved_tokens=8000, allowed=False, reason="user_cap_exhausted"
    )
    accumulator = AsyncMock()
    accumulator.grand_total = 100

    with patch(
        "app.services.free_model_quota_service.free_quota_finalize",
        new_callable=AsyncMock,
    ) as mock_finalize:
        await finalize_free_quota(
            reservation=reservation, user_id=str(uuid4()), accumulator=accumulator
        )

    mock_finalize.assert_not_called()


# ---------------------------------------------------------------------------
# release_free_quota
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_release_free_quota_passes_reserved_tokens_through():
    user_id = str(uuid4())
    reservation = FreeQuotaReservation(reserved_tokens=250, allowed=True)

    with patch(
        "app.services.free_model_quota_service.free_quota_release",
        new_callable=AsyncMock,
    ) as mock_release:
        await release_free_quota(reservation=reservation, user_id=user_id)

    mock_release.assert_awaited_once()
    _, kwargs = mock_release.await_args
    assert str(kwargs["user_id"]) == user_id
    assert kwargs["reserved_tokens"] == 250


@pytest.mark.asyncio
async def test_release_free_quota_swallows_exceptions():
    reservation = FreeQuotaReservation(reserved_tokens=250, allowed=True)

    with patch(
        "app.services.free_model_quota_service.free_quota_release",
        new_callable=AsyncMock,
        side_effect=RuntimeError("boom"),
    ):
        # Must not raise -- never raises, same as release_credit.
        await release_free_quota(reservation=reservation, user_id=str(uuid4()))


@pytest.mark.asyncio
async def test_release_free_quota_denied_reservation_never_calls_service():
    """Regression test for the Critical bug found in review: both
    orchestrators' denial branch returns without clearing
    `free_reservation`, so the shielded `finally` block still calls
    `release_free_quota` with the denied (`allowed=False`) reservation.
    Since `free_quota_reserve` already rolled back on denial (nothing was
    added to either row's `tokens_reserved`), calling the real
    `free_quota_release` here would subtract a phantom amount from the
    *shared global* row -- corrupting capacity for every other user's
    in-flight reservation, not just this one. Must never reach the service
    layer for a denied reservation."""
    reservation = FreeQuotaReservation(
        reserved_tokens=8000, allowed=False, reason="global_cap_exhausted"
    )

    with patch(
        "app.services.free_model_quota_service.free_quota_release",
        new_callable=AsyncMock,
    ) as mock_release:
        await release_free_quota(reservation=reservation, user_id=str(uuid4()))

    mock_release.assert_not_called()


# ---------------------------------------------------------------------------
# Orchestrator wiring: both stream_new_chat and stream_resume_chat must
# actually import and reference the free-quota gate. Neither orchestrator's
# free-tier branch is exercised end-to-end by any existing SSE-stream test
# harness (no fixture constructs a resolved free-tier AgentConfig through
# the full stream), so this is a coverage gap flagged in the track report --
# this test only proves the wiring exists, not that it behaves correctly
# under a live stream. Behavioral coverage of the gate logic itself lives in
# the reserve/finalize/release tests above and the integration tests against
# real Postgres.
# ---------------------------------------------------------------------------

_ORCHESTRATOR_MODULES = [
    "app.tasks.chat.streaming.flows.new_chat.orchestrator",
    "app.tasks.chat.streaming.flows.resume_chat.orchestrator",
]

_EXPECTED_REFERENCES = [
    "needs_free_quota",
    "reserve_free_quota",
    "finalize_free_quota",
    "release_free_quota",
    "FreeQuotaReservation",
]


@pytest.mark.parametrize("module_name", _ORCHESTRATOR_MODULES)
def test_orchestrator_imports_cleanly(module_name: str) -> None:
    importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", _ORCHESTRATOR_MODULES)
def test_orchestrator_source_references_free_quota_gate(module_name: str) -> None:
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    for name in _EXPECTED_REFERENCES:
        assert name in source, f"{module_name} does not reference {name}"
