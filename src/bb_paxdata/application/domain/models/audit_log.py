"""
Immutable Audit Log Domain Model

Provides tamper-evident audit trail with hash chain verification.
Each entry references the previous entry's hash, creating an immutable chain.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AuditLogEntry:
    """
    Immutable audit log entry with hash chain verification.

    Each entry contains:
    - Core fields: id, timestamp, actor_id, action, resource_type, resource_id
    - State tracking: before_state, after_state (JSON diff)
    - Context: correlation_id, ip_address, user_agent
    - Integrity: hash_chain (SHA-256 of previous entry)
    """

    id: str
    timestamp: datetime
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    hash_chain: str | None = None  # Hash of previous entry for chain verification

    def compute_entry_hash(self) -> str:
        """
        Compute SHA-256 hash of this entry's content.

        The hash is computed from all immutable fields to ensure
        tamper-evidence. Excludes the hash_chain field itself.
        """
        fingerprint = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "correlation_id": self.correlation_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }
        fingerprint_str = json.dumps(fingerprint, sort_keys=True, default=str)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()

    def verify_chain_integrity(self, previous_hash: str | None) -> bool:
        """
        Verify that this entry's hash_chain matches the previous entry's hash.

        Args:
            previous_hash: The hash of the previous entry in the chain

        Returns:
            True if the chain is intact, False otherwise
        """
        if self.hash_chain is None:
            # First entry in chain has no previous hash
            return previous_hash is None
        return self.hash_chain == previous_hash


@dataclass
class AuditLogVerificationResult:
    """Result of audit log chain verification."""

    is_valid: bool
    total_entries: int
    verified_entries: int
    first_violation_index: int | None = None
    first_violation_details: str | None = None
    violations: list[dict[str, Any]] = field(default_factory=list)
