"""
Canonical Event Domain Model
Cross-document event coreference with deterministic ID generation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class EventMentionCandidate:
    """
    Event mention extracted from SRL frames using predicate-span-based detection.

    CORRECTED (E04-C-01): Uses V/PRED span as event trigger, not ARG1.
    ARG1 is used as patient/theme context, not the trigger itself.
    """

    trigger_span: str  # V/PRED span — the event trigger
    trigger_lemma: str  # lemmatized trigger for cross-document matching
    arg0_span: str | None  # agent (participating actor)
    arg1_span: str | None  # patient/theme (event description context)
    sentence_id: str
    session_id: str
    timestamp: datetime


@dataclass
class CanonicalEvent:
    """
    Canonical event representing a real-world event across multiple mentions.

    CORRECTED (E04-C-02): Uses SHA-256 deterministic ID generation.
    Event ID is stable across pipeline re-runs for identical events.
    """

    canonical_description: str
    first_mention: datetime
    event_type: str  # verb lemma or nominal lemma of the trigger

    # Derived fields (post-init)
    event_id: str = field(init=False)
    mention_count: int = field(default=1)
    participating_actors: list[str] = field(default_factory=list)
    related_sessions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """
        Generate deterministic event ID using SHA-256.

        The ID is computed from a canonical tuple that uniquely identifies
        the event across re-runs, ensuring idempotency and deduplication.
        """
        # Deterministic ID: stable across re-runs for identical events
        fingerprint = (
            f"{self.event_type}|"
            f"{self.canonical_description[:100].lower().strip()}|"
            f"{self.first_mention.date().isoformat()}"
        )
        self.event_id = (
            "EVT_"
            + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16].upper()
        )

    def add_mention(
        self, actor: str | None = None, session_id: str | None = None
    ) -> None:
        """
        Register a new mention of this canonical event.
        """
        self.mention_count += 1
        if actor and actor not in self.participating_actors:
            self.participating_actors.append(actor)
        if session_id and session_id not in self.related_sessions:
            self.related_sessions.append(session_id)
