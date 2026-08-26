"""Free-tier token quota (global + per-user monthly caps) reserve / finalize
/ release lifecycle.

Sibling to `premium_quota.py`'s credit wallet lifecycle -- both
`stream_new_chat` and `stream_resume_chat` reserve up front (so a single LLM
call can't run away with the budget), then finalize the actual token usage
reported by LiteLLM when the turn completes successfully, or release the
reservation on the cancellation / interrupted-without-finalize paths.
Token-counted instead of micros-counted, and there is no fallback tier below
this one: unlike premium exhaustion (which repins to a free model), free
exhaustion is a hard stop.

State is held by the orchestrator as a simple ``FreeQuotaReservation`` so
reservation, finalize, and release can all be reasoned about from one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.agents.chat.runtime.llm_config import AgentConfig
from app.db import shielded_async_session

if TYPE_CHECKING:
    from app.services.token_tracking_service import TokenAccumulator


@dataclass
class FreeQuotaReservation:
    """Active free-tier quota reservation for one turn.

    ``reserved_tokens`` is the up-front estimate; ``finalize`` debits the
    actual token usage, ``release`` returns it untouched. Unlike
    `CreditReservation`, there is no request_id -- neither
    `free_model_global_quota` nor `free_model_user_quota` has an
    idempotency-key column (a deliberate scope decision for this track).
    """

    reserved_tokens: int
    allowed: bool
    reason: str | None = None


def needs_free_quota(agent_config: AgentConfig | None, user_id: str | None) -> bool:
    """True only for a *platform-funded* free model resolved for a signed-in
    user.

    ``not is_premium`` alone is not the right test. ``billing_tier`` is
    hardcoded to ``"free"`` for the BYOK path in
    `app.tasks.chat.streaming.flows.shared.llm_bundle` (``config_id > 0``, a
    user's own workspace `Connection`/`Model` row carrying their own API
    key), where it has only ever meant "skip the premium credit wallet".
    Reading it as "charge this against the free-tier caps" would rate-limit
    a user's own key against a platform-wide token budget the platform
    isn't paying for, and would drain the shared global cap that other
    users' free-tier access depends on.

    ``config_id``'s sign is the existing discriminator: negative ids are
    platform/global-catalog-sourced (YAML static -1..-999, OpenRouter
    dynamic around -10000.., admin-DB-sourced -100001..), positive ids are
    BYOK workspace models. Auto mode (``config_id == 0``) is always
    resolved to one concrete id by `resolve_initial_auto_pin` before
    `load_llm_bundle` runs, so the `AgentConfig` reaching here always
    carries a resolved model's id, never the sentinel. The anonymous path
    is already excluded by the ``user_id`` check.
    """
    return bool(
        agent_config is not None
        and user_id
        and not agent_config.is_premium
        and agent_config.config_id is not None
        and agent_config.config_id < 0
    )


async def reserve_free_quota(
    *, agent_config: AgentConfig, user_id: str
) -> FreeQuotaReservation:
    """Reserve estimated tokens up front; returns the reservation handle."""
    from app.config import config
    from app.services.free_model_quota_service import free_quota_reserve

    reserve_tokens = (
        agent_config.quota_reserve_tokens or config.QUOTA_MAX_RESERVE_PER_CALL
    )

    async with shielded_async_session() as quota_session:
        quota_result = await free_quota_reserve(
            session=quota_session,
            user_id=UUID(user_id),
            reserve_tokens=reserve_tokens,
        )
    return FreeQuotaReservation(
        reserved_tokens=reserve_tokens,
        allowed=quota_result.allowed,
        reason=quota_result.reason,
    )


async def finalize_free_quota(
    *,
    reservation: FreeQuotaReservation,
    user_id: str,
    accumulator: TokenAccumulator,
) -> None:
    """Finalize using the actual token usage reported by LiteLLM, summed
    across every call in the turn.

    Best-effort: failures here must not bubble up to the SSE stream - the
    user has already received their tokens; we log and move on.

    A denied (``allowed=False``) reservation never actually reserved
    anything (``free_quota_reserve`` rolls back before returning on
    denial), so finalizing it here would debit tokens the caps never
    admitted. Guarded centrally so no call site has to remember this.
    """
    if not reservation.allowed:
        return
    try:
        from app.services.free_model_quota_service import free_quota_finalize

        async with shielded_async_session() as quota_session:
            await free_quota_finalize(
                session=quota_session,
                user_id=UUID(user_id),
                actual_tokens=accumulator.grand_total,
                reserved_tokens=reservation.reserved_tokens,
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to finalize free quota for user %s",
            user_id,
            exc_info=True,
        )


async def release_free_quota(
    *, reservation: FreeQuotaReservation, user_id: str
) -> None:
    """Release the reservation on cancellation paths; never raises.

    A denied (``allowed=False``) reservation never actually reserved
    anything -- ``free_quota_reserve`` rolls back before returning on
    denial, so nothing was added to either row's ``tokens_reserved``.
    Releasing it anyway would subtract a phantom amount from the *shared
    global* row (not just this user's own row), corrupting capacity for
    every other in-flight reservation on the platform. Every orchestrator
    call site reaches this same `finally` block regardless of whether the
    reservation was denied (the denial branch returns without clearing
    `free_reservation`), so the guard belongs here -- centralized, and
    impossible to forget at a new call site -- rather than requiring each
    denial branch to remember to null out its local variable.
    """
    if not reservation.allowed:
        return
    try:
        from app.services.free_model_quota_service import free_quota_release

        async with shielded_async_session() as quota_session:
            await free_quota_release(
                session=quota_session,
                user_id=UUID(user_id),
                reserved_tokens=reservation.reserved_tokens,
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to release free quota for user %s", user_id
        )
