"""Integration tests for Paddle subscription checkout (Phase E, Track 2 of
the super admin dashboard): `app.routes.paddle_routes` and
`app.services.paddle_service`.

Route handlers and service functions are called directly (session + real
`Request`/`AuthContext` objects passed in), the same pattern
`tests/integration/routes/test_admin_billing_routes.py` uses -- this file
has no shared fixture module to import helpers from, so they're duplicated
here, same as that file does. Every outbound Paddle HTTP call is mocked via
`app.services.paddle_service.httpx.AsyncClient` -- no test in this file ever
makes a real network call to Paddle.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.context import AuthContext
from app.db import (
    CreditPurchaseStatus,
    PaddleCustomer,
    PaddleSubscription,
    PaddleTransaction,
    PersonalAccessToken,
    Plan,
    User,
)
from app.routes import paddle_routes as routes
from app.schemas.paddle import CreateSubscriptionCheckoutRequest
from app.services import paddle_service
from app.tasks.celery_tasks import paddle_reconciliation_task
from app.users import require_session_context

pytestmark = pytest.mark.integration

_WEBHOOK_SECRET = "whsec_test_secret"


# ---------------------------------------------------------------------------
# Local helpers (duplicated from test_admin_billing_routes.py's own pattern)
# ---------------------------------------------------------------------------


def _auth(user: User) -> AuthContext:
    return AuthContext.session(user)


async def _make_user(session: AsyncSession, *, email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email or f"{uuid.uuid4()}@corvos.test",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _make_plan(
    session: AsyncSession,
    *,
    plan_key: str | None = None,
    monthly_credit_micros: int = 5_000_000,
    paddle_price_id: str | None = None,
    is_active: bool = True,
) -> Plan:
    plan = Plan(
        plan_key=plan_key or f"plan_{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_credit_micros=monthly_credit_micros,
        paddle_price_id=paddle_price_id or f"pri_{uuid.uuid4().hex[:12]}",
        is_active=is_active,
    )
    session.add(plan)
    await session.flush()
    return plan


def _sign(body: bytes, ts: int, secret: str = _WEBHOOK_SECRET) -> str:
    signed_payload = f"{ts}:{body.decode()}".encode()
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


def _make_webhook_request(body: bytes, *, signature: str | None) -> Request:
    raw_headers = []
    if signature is not None:
        raw_headers.append((b"paddle-signature", signature.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "headers": raw_headers,
        "client": ("127.0.0.1", 0),
    }
    consumed = False

    async def receive():
        nonlocal consumed
        if consumed:
            return {"type": "http.disconnect"}
        consumed = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _transaction_completed_payload(
    *,
    transaction_id: str,
    customer_id: str,
    subscription_id: str | None = "sub_placeholder",
    price_id: str | None = None,
    grand_total: str = "1000",
    currency: str = "USD",
) -> dict:
    items = [{"price": {"id": price_id}, "quantity": 1}] if price_id else []
    return {
        "id": transaction_id,
        "status": "completed",
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "currency_code": currency,
        "details": {"totals": {"grand_total": grand_total}},
        "items": items,
    }


def _subscription_payload(
    *,
    subscription_id: str,
    customer_id: str,
    price_id: str | None = None,
    status: str = "active",
    period_end: str = "2026-09-15T00:00:00Z",
    scheduled_change: dict | None = None,
) -> dict:
    items = [{"price": {"id": price_id}, "quantity": 1}] if price_id else []
    return {
        "id": subscription_id,
        "status": status,
        "customer_id": customer_id,
        "current_billing_period": {
            "starts_at": "2026-08-15T00:00:00Z",
            "ends_at": period_end,
        },
        "scheduled_change": scheduled_change,
        "items": items,
    }


class _FakeResponse:
    def __init__(self, *, json_data: dict, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self
            )

    def json(self) -> dict:
        return self._json


class _FakePaddleAsyncClient:
    """Drop-in for `httpx.AsyncClient` used by `paddle_service._paddle_request`.

    `responder(method, url, json_body)` must return a `_FakeResponse` (or
    raise an `httpx.HTTPError`); never touches the network.
    """

    def __init__(self, responder):
        self._responder = responder
        self.calls: list[tuple[str, str, dict | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method: str, url: str, *, headers=None, json=None):
        self.calls.append((method, url, json))
        return self._responder(method, url, json)


def _patch_paddle_async_client(monkeypatch, responder) -> _FakePaddleAsyncClient:
    client = _FakePaddleAsyncClient(responder)
    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda *args, **kwargs: client,
    )
    return client


class _FakeSessionContextManager:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ---------------------------------------------------------------------------
# app.services.paddle_service.fulfill_completed_transaction
# ---------------------------------------------------------------------------


class TestFulfillCompletedTransaction:
    async def test_first_delivery_grants_credit_and_creates_completed_row(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, monthly_credit_micros=5_000_000)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_first_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        data = _transaction_completed_payload(
            transaction_id="txn_first_1",
            customer_id="ctm_first_1",
            price_id=plan.paddle_price_id,
        )
        await paddle_service.fulfill_completed_transaction(db_session, data)

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance + 5_000_000

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_first_1"
                )
            )
        ).scalar_one()
        assert purchase.status == CreditPurchaseStatus.COMPLETED
        assert purchase.credit_micros_granted == 5_000_000
        assert purchase.plan_id == plan.id
        assert purchase.amount_total == 1000
        assert purchase.currency == "USD"
        assert purchase.completed_at is not None

    async def test_second_delivery_does_not_double_grant(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, monthly_credit_micros=3_000_000)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_retry_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        data = _transaction_completed_payload(
            transaction_id="txn_retry_1",
            customer_id="ctm_retry_1",
            price_id=plan.paddle_price_id,
        )

        await paddle_service.fulfill_completed_transaction(db_session, data)
        await db_session.refresh(user)
        balance_after_first = user.credit_micros_balance
        assert balance_after_first == original_balance + 3_000_000

        # Simulate a webhook retry delivering the exact same transaction id.
        await paddle_service.fulfill_completed_transaction(db_session, data)
        await db_session.refresh(user)
        assert user.credit_micros_balance == balance_after_first

        rows = (
            (
                await db_session.execute(
                    select(PaddleTransaction).where(
                        PaddleTransaction.paddle_transaction_id == "txn_retry_1"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    async def test_unknown_price_id_does_not_crash_stores_null_plan(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_unknown_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        data = _transaction_completed_payload(
            transaction_id="txn_unknown_1",
            customer_id="ctm_unknown_1",
            price_id="pri_does_not_match_any_plan",
        )
        await paddle_service.fulfill_completed_transaction(db_session, data)

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_unknown_1"
                )
            )
        ).scalar_one()
        assert purchase.plan_id is None
        assert purchase.credit_micros_granted == 0
        assert purchase.status == CreditPurchaseStatus.COMPLETED

    async def test_trimmed_items_fallback_resolves_price_and_grants_credit(
        self, db_session: AsyncSession, monkeypatch
    ):
        """Happy path for the `get_transaction` fallback: the webhook payload's
        `items` is trimmed/absent, so `fulfill_completed_transaction` must fall
        back to `GET /transactions/{id}` to resolve the price id -- no existing
        test exercised this path before (every other payload supplies `items`
        directly), so this confirms the fallback actually works, not just that
        it exists."""
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, monthly_credit_micros=4_000_000)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_fallback_ok_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", "test_api_key")

        def _responder(method, url, json_body):
            assert method == "GET"
            assert url.endswith("/transactions/txn_fallback_ok_1")
            return _FakeResponse(
                json_data={
                    "data": _transaction_completed_payload(
                        transaction_id="txn_fallback_ok_1",
                        customer_id="ctm_fallback_ok_1",
                        price_id=plan.paddle_price_id,
                    )
                }
            )

        _patch_paddle_async_client(monkeypatch, _responder)

        # Webhook payload with no items -- forces the get_transaction fallback.
        data = _transaction_completed_payload(
            transaction_id="txn_fallback_ok_1",
            customer_id="ctm_fallback_ok_1",
            price_id=None,
        )
        assert data["items"] == []
        await paddle_service.fulfill_completed_transaction(db_session, data)

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance + 4_000_000

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_fallback_ok_1"
                )
            )
        ).scalar_one()
        assert purchase.status == CreditPurchaseStatus.COMPLETED
        assert purchase.plan_id == plan.id
        assert purchase.credit_micros_granted == 4_000_000

    async def test_trimmed_items_fallback_failure_leaves_row_pending(
        self, db_session: AsyncSession, monkeypatch
    ):
        """When items is trimmed/absent AND the get_transaction fallback call
        itself fails (timeout/5xx/etc), the row must stay PENDING (not get
        marked COMPLETED with 0 credit granted) so the reconciliation task can
        retry it later -- fix for the review finding that a transient Paddle
        API failure was previously indistinguishable from a price id that
        genuinely doesn't map to any plan."""
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_fallback_fail_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", "test_api_key")

        def _responder(method, url, json_body):
            raise httpx.ConnectTimeout("simulated Paddle API timeout")

        _patch_paddle_async_client(monkeypatch, _responder)

        data = _transaction_completed_payload(
            transaction_id="txn_fallback_fail_1",
            customer_id="ctm_fallback_fail_1",
            price_id=None,
        )
        assert data["items"] == []
        await paddle_service.fulfill_completed_transaction(db_session, data)

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_fallback_fail_1"
                )
            )
        ).scalar_one()
        assert purchase.status == CreditPurchaseStatus.PENDING
        assert purchase.plan_id is None
        assert purchase.credit_micros_granted == 0

    async def test_non_subscription_transaction_is_skipped(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_nosub_1")
        )
        await db_session.flush()

        data = _transaction_completed_payload(
            transaction_id="txn_nosub_1",
            customer_id="ctm_nosub_1",
            subscription_id=None,
        )
        await paddle_service.fulfill_completed_transaction(db_session, data)

        row = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_nosub_1"
                )
            )
        ).scalar_one_or_none()
        assert row is None


# ---------------------------------------------------------------------------
# app.services.paddle_service.upsert_subscription_from_webhook
# ---------------------------------------------------------------------------


class TestUpsertSubscriptionFromWebhook:
    async def test_create_then_update_results_in_exactly_one_row(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_sub_upsert_1")
        )
        await db_session.flush()

        created = _subscription_payload(
            subscription_id="sub_upsert_1",
            customer_id="ctm_sub_upsert_1",
            price_id=plan.paddle_price_id,
            status="trialing",
        )
        await paddle_service.upsert_subscription_from_webhook(db_session, created)

        updated = _subscription_payload(
            subscription_id="sub_upsert_1",
            customer_id="ctm_sub_upsert_1",
            price_id=plan.paddle_price_id,
            status="active",
        )
        await paddle_service.upsert_subscription_from_webhook(db_session, updated)

        rows = (
            (
                await db_session.execute(
                    select(PaddleSubscription).where(
                        PaddleSubscription.paddle_subscription_id == "sub_upsert_1"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == "active"
        assert rows[0].plan_id == plan.id
        assert rows[0].user_id == user.id

    async def test_subscription_canceled_sets_status_canceled(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_sub_cancel_1")
        )
        await db_session.flush()

        created = _subscription_payload(
            subscription_id="sub_cancel_1",
            customer_id="ctm_sub_cancel_1",
            status="active",
        )
        await paddle_service.upsert_subscription_from_webhook(db_session, created)

        canceled = _subscription_payload(
            subscription_id="sub_cancel_1",
            customer_id="ctm_sub_cancel_1",
            status="canceled",
        )
        await paddle_service.upsert_subscription_from_webhook(db_session, canceled)

        row = (
            await db_session.execute(
                select(PaddleSubscription).where(
                    PaddleSubscription.paddle_subscription_id == "sub_cancel_1"
                )
            )
        ).scalar_one()
        assert row.status == "canceled"

    async def test_scheduled_cancel_sets_cancel_at_period_end(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_sub_sched_1")
        )
        await db_session.flush()

        data = _subscription_payload(
            subscription_id="sub_sched_1",
            customer_id="ctm_sub_sched_1",
            status="active",
            scheduled_change={
                "action": "cancel",
                "effective_at": "2026-09-15T00:00:00Z",
            },
        )
        await paddle_service.upsert_subscription_from_webhook(db_session, data)

        row = (
            await db_session.execute(
                select(PaddleSubscription).where(
                    PaddleSubscription.paddle_subscription_id == "sub_sched_1"
                )
            )
        ).scalar_one()
        assert row.cancel_at_period_end is True
        assert row.status == "active"


# ---------------------------------------------------------------------------
# POST /paddle/webhook
# ---------------------------------------------------------------------------


class TestPaddleWebhookRoute:
    async def test_webhook_503s_when_secret_unset(
        self, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(routes.config, "PADDLE_WEBHOOK_SECRET", None)
        request = _make_webhook_request(b"{}", signature=None)

        with pytest.raises(HTTPException) as exc:
            await routes.paddle_webhook(request, db_session=db_session)
        assert exc.value.status_code == 503

    async def test_webhook_400s_on_missing_signature(
        self, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(routes.config, "PADDLE_WEBHOOK_SECRET", _WEBHOOK_SECRET)
        request = _make_webhook_request(b"{}", signature=None)

        with pytest.raises(HTTPException) as exc:
            await routes.paddle_webhook(request, db_session=db_session)
        assert exc.value.status_code == 400

    async def test_webhook_400s_on_bad_signature(
        self, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(routes.config, "PADDLE_WEBHOOK_SECRET", _WEBHOOK_SECRET)
        body = b'{"event_type": "transaction.completed", "data": {}}'
        request = _make_webhook_request(body, signature="ts=123;h1=deadbeef")

        with pytest.raises(HTTPException) as exc:
            await routes.paddle_webhook(request, db_session=db_session)
        assert exc.value.status_code == 400

    async def test_webhook_200s_and_noops_on_unrecognized_event_type(
        self, db_session: AsyncSession, monkeypatch
    ):
        monkeypatch.setattr(routes.config, "PADDLE_WEBHOOK_SECRET", _WEBHOOK_SECRET)
        body = json.dumps(
            {"event_type": "customer.created", "data": {"id": "ctm_ignored"}}
        ).encode()
        ts = int(time.time())
        header = _sign(body, ts)
        request = _make_webhook_request(body, signature=header)

        response = await routes.paddle_webhook(request, db_session=db_session)
        assert response.received is True

    async def test_webhook_fulfills_transaction_completed_event(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, monthly_credit_micros=1_000_000)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_webhook_1")
        )
        await db_session.flush()
        original_balance = user.credit_micros_balance

        monkeypatch.setattr(routes.config, "PADDLE_WEBHOOK_SECRET", _WEBHOOK_SECRET)
        payload = {
            "event_id": "evt_1",
            "event_type": "transaction.completed",
            "data": _transaction_completed_payload(
                transaction_id="txn_webhook_1",
                customer_id="ctm_webhook_1",
                price_id=plan.paddle_price_id,
            ),
        }
        body = json.dumps(payload).encode()
        header = _sign(body, int(time.time()))
        request = _make_webhook_request(body, signature=header)

        response = await routes.paddle_webhook(request, db_session=db_session)
        assert response.received is True

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance + 1_000_000


# ---------------------------------------------------------------------------
# POST /paddle/create-subscription-checkout
# ---------------------------------------------------------------------------


class TestCreateSubscriptionCheckoutRoute:
    async def test_404s_on_unknown_plan(self, db_session: AsyncSession):
        user = await _make_user(db_session)

        with pytest.raises(HTTPException) as exc:
            await routes.create_subscription_checkout(
                CreateSubscriptionCheckoutRequest(plan_id=999_999_999),
                auth=_auth(user),
                db_session=db_session,
            )
        assert exc.value.status_code == 404

    async def test_404s_on_inactive_plan(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, is_active=False)

        with pytest.raises(HTTPException) as exc:
            await routes.create_subscription_checkout(
                CreateSubscriptionCheckoutRequest(plan_id=plan.id),
                auth=_auth(user),
                db_session=db_session,
            )
        assert exc.value.status_code == 404

    async def test_503s_when_api_key_unset(self, db_session: AsyncSession, monkeypatch):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session)
        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", None)

        with pytest.raises(HTTPException) as exc:
            await routes.create_subscription_checkout(
                CreateSubscriptionCheckoutRequest(plan_id=plan.id),
                auth=_auth(user),
                db_session=db_session,
            )
        assert exc.value.status_code == 503

    async def test_creates_checkout_and_returns_url(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session)
        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", "test_api_key")

        def _responder(method, url, json_body):
            if method == "POST" and url.endswith("/customers"):
                assert json_body == {"email": user.email}
                return _FakeResponse(json_data={"data": {"id": "ctm_new_checkout_1"}})
            if method == "POST" and url.endswith("/transactions"):
                assert json_body["items"] == [
                    {"price_id": plan.paddle_price_id, "quantity": 1}
                ]
                assert json_body["customer_id"] == "ctm_new_checkout_1"
                return _FakeResponse(
                    json_data={
                        "data": {
                            "checkout": {
                                "url": "https://paddle.test/checkout/abc?_ptxn=txn_x"
                            }
                        }
                    }
                )
            raise AssertionError(f"unexpected Paddle call: {method} {url}")

        _patch_paddle_async_client(monkeypatch, _responder)

        response = await routes.create_subscription_checkout(
            CreateSubscriptionCheckoutRequest(plan_id=plan.id),
            auth=_auth(user),
            db_session=db_session,
        )
        assert response.checkout_url == "https://paddle.test/checkout/abc?_ptxn=txn_x"

        customer = (
            await db_session.execute(
                select(PaddleCustomer).where(PaddleCustomer.user_id == user.id)
            )
        ).scalar_one()
        assert customer.paddle_customer_id == "ctm_new_checkout_1"


# ---------------------------------------------------------------------------
# GET /paddle/subscription-status
# ---------------------------------------------------------------------------


class TestSubscriptionStatusRoute:
    async def test_returns_no_subscription_when_none_exists(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)

        response = await routes.get_subscription_status(
            auth=_auth(user), db_session=db_session
        )
        assert response.has_subscription is False

    async def test_returns_subscription_and_plan_info(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, plan_key="pro_status_test")
        db_session.add(
            PaddleSubscription(
                user_id=user.id,
                plan_id=plan.id,
                paddle_subscription_id="sub_status_1",
                paddle_customer_id="ctm_status_1",
                status="active",
                cancel_at_period_end=False,
            )
        )
        await db_session.commit()

        response = await routes.get_subscription_status(
            auth=_auth(user), db_session=db_session
        )
        assert response.has_subscription is True
        assert response.status == "active"
        assert response.plan_key == "pro_status_test"
        assert response.cancel_at_period_end is False


# ---------------------------------------------------------------------------
# GET /paddle/plans
# ---------------------------------------------------------------------------


class TestListAvailablePlansRoute:
    async def test_active_plan_appears_with_exactly_the_public_fields(
        self, db_session: AsyncSession
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(
            db_session,
            plan_key="pub_active_1",
            monthly_credit_micros=7_000_000,
            paddle_price_id="pri_should_never_appear",
        )

        response = await routes.list_available_plans(
            auth=_auth(user), db_session=db_session
        )

        entry = next((p for p in response if p.plan_key == "pub_active_1"), None)
        assert entry is not None
        assert entry.id == plan.id
        assert entry.name == plan.name
        assert entry.description == plan.description
        assert entry.monthly_credit_micros == 7_000_000

        # Assert paddle_price_id is genuinely absent from the serialized
        # response, not just unused on the Pydantic model instance.
        serialized = entry.model_dump()
        assert set(serialized.keys()) == {
            "id",
            "plan_key",
            "name",
            "description",
            "monthly_credit_micros",
        }
        assert "paddle_price_id" not in serialized

    async def test_inactive_plan_is_excluded(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        await _make_plan(db_session, plan_key="pub_inactive_1", is_active=False)

        response = await routes.list_available_plans(
            auth=_auth(user), db_session=db_session
        )

        assert all(p.plan_key != "pub_inactive_1" for p in response)

    async def test_ordinary_session_user_can_call_it_no_permission_required(
        self, db_session: AsyncSession
    ):
        """`list_available_plans` never calls `check_platform_permission` --
        an ordinary, non-admin session user (no platform permissions at all)
        must succeed, unlike `GET /admin/plans` (PLANS_READ-gated)."""
        user = await _make_user(db_session)
        await _make_plan(db_session, plan_key="pub_no_perm_needed_1")

        response = await routes.list_available_plans(
            auth=_auth(user), db_session=db_session
        )

        assert any(p.plan_key == "pub_no_perm_needed_1" for p in response)

    async def test_requires_an_interactive_session_not_a_pat(
        self, db_session: AsyncSession
    ):
        """The route depends on `require_session_context`, the same
        dependency `create-subscription-checkout`/`subscription-status` use
        -- a PAT-authenticated principal is rejected with 403. (Route
        handlers in this file are invoked directly rather than through a
        live HTTP client, same as every other test here, so this exercises
        the actual dependency the route declares rather than the route
        function body.)"""
        user = await _make_user(db_session)
        pat = PersonalAccessToken(
            user_id=user.id,
            user=user,
            token_hash="0" * 64,
            token_prefix="ss_pat_test",
            label="Test PAT",
        )
        pat_auth = AuthContext.pat_auth(user, pat)

        with pytest.raises(HTTPException) as exc:
            await require_session_context(auth=pat_auth)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Reconciliation task
# ---------------------------------------------------------------------------


class TestPaddleReconciliation:
    async def test_stale_pending_row_fulfilled_when_paddle_reports_completed(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await _make_user(db_session)
        plan = await _make_plan(db_session, monthly_credit_micros=2_000_000)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_recon_1")
        )
        stale_created_at = datetime.now(UTC) - timedelta(minutes=30)
        db_session.add(
            PaddleTransaction(
                user_id=user.id,
                paddle_transaction_id="txn_recon_1",
                status=CreditPurchaseStatus.PENDING,
                created_at=stale_created_at,
            )
        )
        await db_session.commit()
        original_balance = user.credit_micros_balance

        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", "test_api_key")
        monkeypatch.setattr(
            paddle_reconciliation_task.config,
            "PADDLE_RECONCILIATION_LOOKBACK_MINUTES",
            10,
        )
        monkeypatch.setattr(
            paddle_reconciliation_task.config, "PADDLE_RECONCILIATION_BATCH_SIZE", 20
        )
        monkeypatch.setattr(
            paddle_reconciliation_task,
            "get_celery_session_maker",
            lambda: lambda: _FakeSessionContextManager(db_session),
        )

        def _responder(method, url, json_body):
            assert method == "GET"
            assert url.endswith("/transactions/txn_recon_1")
            return _FakeResponse(
                json_data={
                    "data": _transaction_completed_payload(
                        transaction_id="txn_recon_1",
                        customer_id="ctm_recon_1",
                        price_id=plan.paddle_price_id,
                    )
                }
            )

        _patch_paddle_async_client(monkeypatch, _responder)

        await paddle_reconciliation_task._reconcile_pending_paddle_transactions()

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance + 2_000_000

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_recon_1"
                )
            )
        ).scalar_one()
        assert purchase.status == CreditPurchaseStatus.COMPLETED

    async def test_stale_pending_row_marked_failed_when_paddle_reports_canceled(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await _make_user(db_session)
        db_session.add(
            PaddleCustomer(user_id=user.id, paddle_customer_id="ctm_recon_2")
        )
        stale_created_at = datetime.now(UTC) - timedelta(minutes=30)
        db_session.add(
            PaddleTransaction(
                user_id=user.id,
                paddle_transaction_id="txn_recon_2",
                status=CreditPurchaseStatus.PENDING,
                created_at=stale_created_at,
            )
        )
        await db_session.commit()
        original_balance = user.credit_micros_balance

        monkeypatch.setattr(paddle_service.config, "PADDLE_API_KEY", "test_api_key")
        monkeypatch.setattr(
            paddle_reconciliation_task.config,
            "PADDLE_RECONCILIATION_LOOKBACK_MINUTES",
            10,
        )
        monkeypatch.setattr(
            paddle_reconciliation_task.config, "PADDLE_RECONCILIATION_BATCH_SIZE", 20
        )
        monkeypatch.setattr(
            paddle_reconciliation_task,
            "get_celery_session_maker",
            lambda: lambda: _FakeSessionContextManager(db_session),
        )

        def _responder(method, url, json_body):
            return _FakeResponse(
                json_data={"data": {"id": "txn_recon_2", "status": "canceled"}}
            )

        _patch_paddle_async_client(monkeypatch, _responder)

        await paddle_reconciliation_task._reconcile_pending_paddle_transactions()

        await db_session.refresh(user)
        assert user.credit_micros_balance == original_balance

        purchase = (
            await db_session.execute(
                select(PaddleTransaction).where(
                    PaddleTransaction.paddle_transaction_id == "txn_recon_2"
                )
            )
        ).scalar_one()
        assert purchase.status == CreditPurchaseStatus.FAILED
