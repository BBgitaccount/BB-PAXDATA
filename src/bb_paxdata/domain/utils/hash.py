from __future__ import annotations

import hashlib


def compute_audit_hash(*data: str) -> str:
    """Audit trail için deterministik SHA256 hash hesaplar.

    Args:
        *data: Hash hesaplanacak string veriler.

    Returns:
        SHA256 hash hex string.
    """
    hasher = hashlib.sha256()
    for item in data:
        hasher.update(item.encode("utf-8"))
    return hasher.hexdigest()
