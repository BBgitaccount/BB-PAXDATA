# tests/infrastructure/webhooks/test_signature.py
from __future__ import annotations

import json
import time

from bb_paxdata.infrastructure.webhooks.signature import (
    generate_webhook_signature,
    verify_webhook_signature,
)


def test_signature_valid_flow():
    payload = {"event": "analysis_completed", "data": {"id": 123}}
    secret = "super-secret-key"

    sig_header, ts = generate_webhook_signature(payload, secret)

    assert sig_header.startswith(f"t={ts},v1=")

    # Serialize correctly to bytes (simulate HTTP raw body)
    raw_body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")

    # Validation should succeed
    assert verify_webhook_signature(raw_body, sig_header, secret)


def test_signature_invalid_secret():
    payload = {"event": "analysis_completed"}
    secret = "super-secret-key"
    wrong_secret = "wrong-secret"

    sig_header, _ = generate_webhook_signature(payload, secret)
    raw_body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")

    # Validation should fail
    assert not verify_webhook_signature(raw_body, sig_header, wrong_secret)


def test_signature_invalid_body():
    payload = {"event": "analysis_completed"}
    modified_payload = {"event": "analysis_tampered"}
    secret = "super-secret-key"

    sig_header, _ = generate_webhook_signature(payload, secret)
    raw_body = json.dumps(modified_payload, sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )

    # Validation should fail
    assert not verify_webhook_signature(raw_body, sig_header, secret)


def test_signature_expired_timestamp():
    payload = {"event": "analysis_completed"}
    secret = "super-secret-key"

    # Generate signature using an expired timestamp (e.g., 10 minutes ago)
    old_ts = str(int(time.time()) - 600)
    serialized_body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    signed_payload = f"{old_ts}.{serialized_body}"

    import hashlib
    import hmac

    sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    expired_header = f"t={old_ts},v1={sig}"
    raw_body = serialized_body.encode("utf-8")

    # Should fail with 5 minutes (300s) default tolerance
    assert not verify_webhook_signature(raw_body, expired_header, secret)


def test_signature_malformed_header():
    payload = {"event": "analysis_completed"}
    secret = "super-secret-key"
    raw_body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")

    assert not verify_webhook_signature(raw_body, "invalid_header", secret)
    assert not verify_webhook_signature(raw_body, "t=12345", secret)
    assert not verify_webhook_signature(raw_body, "v1=abcde", secret)
