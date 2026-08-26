"""Unit tests for `app.services.paddle_service.verify_paddle_signature`.

Pure signature-verification logic -- no database, no network calls. DB- and
Paddle-API-touching service function coverage (`fulfill_completed_transaction`,
`upsert_subscription_from_webhook`, idempotency, and the route/reconciliation
layers built on top of them) lives in
`tests/integration/routes/test_paddle_routes.py` instead, mirroring the
unit/integration split established by
`tests/unit/services/test_entitlement_service.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from app.services.paddle_service import verify_paddle_signature

pytestmark = pytest.mark.unit

_SECRET = "whsec_test_secret"
_BODY = b'{"event_type": "transaction.completed", "data": {"id": "txn_1"}}'


def _sign(body: bytes, ts: int, secret: str = _SECRET) -> str:
    signed_payload = f"{ts}:{body.decode()}".encode()
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={digest}"


class TestVerifyPaddleSignature:
    def test_valid_signature_accepted(self):
        ts = int(time.time())
        header = _sign(_BODY, ts)
        assert verify_paddle_signature(_BODY, header, _SECRET) is True

    def test_wrong_secret_rejected(self):
        ts = int(time.time())
        header = _sign(_BODY, ts, secret="whsec_wrong")
        assert verify_paddle_signature(_BODY, header, _SECRET) is False

    def test_tampered_body_rejected(self):
        ts = int(time.time())
        header = _sign(_BODY, ts)
        tampered = _BODY.replace(b"txn_1", b"txn_evil")
        assert verify_paddle_signature(tampered, header, _SECRET) is False

    def test_stale_timestamp_rejected(self):
        ts = int(time.time()) - 301
        header = _sign(_BODY, ts)
        assert verify_paddle_signature(_BODY, header, _SECRET) is False

    def test_timestamp_within_tolerance_accepted(self):
        ts = int(time.time()) - 299
        header = _sign(_BODY, ts)
        assert verify_paddle_signature(_BODY, header, _SECRET) is True

    def test_future_timestamp_beyond_tolerance_rejected(self):
        ts = int(time.time()) + 301
        header = _sign(_BODY, ts)
        assert verify_paddle_signature(_BODY, header, _SECRET) is False

    def test_malformed_header_rejected(self):
        assert verify_paddle_signature(_BODY, "not-a-valid-header", _SECRET) is False

    def test_missing_ts_rejected(self):
        assert verify_paddle_signature(_BODY, "h1=deadbeef", _SECRET) is False

    def test_missing_h1_rejected(self):
        ts = int(time.time())
        assert verify_paddle_signature(_BODY, f"ts={ts}", _SECRET) is False

    def test_empty_header_rejected(self):
        assert verify_paddle_signature(_BODY, "", _SECRET) is False

    def test_non_integer_timestamp_rejected(self):
        header = "ts=not-a-number;h1=deadbeef"
        assert verify_paddle_signature(_BODY, header, _SECRET) is False
