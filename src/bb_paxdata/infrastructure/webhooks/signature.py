# src/bb_paxdata/infrastructure/webhooks/signature.py
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone


def generate_webhook_signature(payload: dict, secret: str) -> tuple[str, str]:
    """
    Returns: (signature_header, timestamp_str)
    Header format: t=<ts>,v1=<hex_signature>
    """
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    serialized_body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    # Timestamp + payload birlikte imzalanır
    signed_payload = f"{ts}.{serialized_body}"

    sig = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"t={ts},v1={sig}", ts


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Webhook alıcısının (harici sistemin) imzayı doğrulamak için kullanacağı fonksiyon.
    Referans implementasyon olarak SDK'ya eklenecektir.

    Args:
        raw_body: HTTP body'nin ham byte içeriği (JSON decode yapılmadan önce).
        signature_header: X-Paxdata-Signature başlık değeri.
        secret: Webhook kayıt sırasında verilen shared secret.
        tolerance_seconds: Replay attack penceresi (varsayılan 5 dakika).

    Returns:
        True ise imza geçerli ve timestamp tolerans içinde.
    """
    try:
        parts = dict(item.split("=", 1) for item in signature_header.split(","))
        ts_str = parts.get("t", "")
        received_sig = parts.get("v1", "")

        if not ts_str or not received_sig:
            return False

        ts = int(ts_str)
        now = int(datetime.now(timezone.utc).timestamp())

        # Replay attack: timestamp 5 dakikadan eski veya gelecekten geliyorsa reddet
        if abs(now - ts) > tolerance_seconds:
            return False

        signed_payload = f"{ts_str}.{raw_body.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Timing-safe karşılaştırma (timing attack'a karşı)
        return hmac.compare_digest(received_sig, expected_sig)

    except (ValueError, KeyError):
        return False
