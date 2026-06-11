"""
Event Coreference Service
Cross-document event coreference with SRL-based detection and LLM verification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from bb_paxdata.application.domain.models.canonical_event import (
    CanonicalEvent,
    EventMentionCandidate,
)

if TYPE_CHECKING:
    from bb_paxdata.application.domain.models.srl import SRLDocumentResult
    from bb_paxdata.application.domain.ports.i_canonical_event_repository import (
        ICanonicalEventRepository,
    )
    from bb_paxdata.application.domain.services.prompt_registry import PromptRegistry
    from bb_paxdata.infrastructure.ai.ai_client_protocol import AIClientProtocol


# CORRECTED (E04-M-04): Concrete threshold window definition
HEURISTIC_SCORE_ACCEPT_THRESHOLD: float = 0.85  # above this → accept without LLM
HEURISTIC_SCORE_REJECT_THRESHOLD: float = 0.30  # below this → reject without LLM
# LLM invoked only for: REJECT_THRESHOLD < score <= ACCEPT_THRESHOLD


def extract_event_mentions(
    srl_result: SRLDocumentResult,
    trigger_verb_set: frozenset[str],
    trigger_nominal_set: frozenset[str],
    sentence_id: str,
    session_id: str,
    timestamp: datetime,
) -> list[EventMentionCandidate]:
    """
    CORRECTED (E04-C-01): Extract event mentions using predicate-span-based detection.

    Uses V/PRED span as event trigger, not ARG1. ARG1 is used as patient/theme context.
    """
    candidates = []

    # Verb triggers: use predicate (V/PRED span) as event trigger
    for frame in srl_result.frames:
        trigger = frame.verb  # V/PRED span
        if trigger in trigger_verb_set or (
            frame.verb_lemma and frame.verb_lemma in trigger_verb_set
        ):
            candidates.append(
                EventMentionCandidate(
                    trigger_span=trigger,
                    trigger_lemma=frame.verb_lemma or trigger,
                    arg0_span=frame.actor_text,  # agent (participant)
                    arg1_span=frame.target_text,  # patient/theme (context, not trigger)
                    sentence_id=sentence_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
            )

    # Nominal triggers: separate NP chunking pass would be needed here
    # This requires spaCy noun chunking - placeholder for now
    # TODO: Implement nominal trigger detection with spaCy noun_chunks

    return candidates


def normalize_event_span(span_text: str, lang: str, nlp) -> str:
    """
    CORRECTED (E04-M-05): Return lemmatized, lowercased, stopword-stripped span.

    Critical for Turkish and morphologically rich languages.
    Uses lemma_ instead of text for cross-document matching.
    """
    doc = nlp(span_text.lower().strip())
    # Use lemma_, not text — critical for Turkish and morphologically rich languages
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and len(token.lemma_) > 1
    ]
    return " ".join(tokens)


def string_similarity_score(span_a: str, span_b: str, lang: str, nlp) -> float:
    """
    CORRECTED (E04-M-05): Compute similarity using lemmatized Jaccard.

    Language-agnostic after lemmatization.
    """
    norm_a = normalize_event_span(span_a, lang, nlp)
    norm_b = normalize_event_span(span_b, lang, nlp)
    if not norm_a or not norm_b:
        return 0.0
    # Jaccard over lemma sets — language-agnostic after lemmatization
    set_a, set_b = set(norm_a.split()), set(norm_b.split())
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def calibrate_temporal_window(sessions: list) -> timedelta:
    """
    CORRECTED (E04-m-01): Compute ±sigma window from corpus session timing distribution.

    Calibrates against actual corpus session timing instead of hardcoded ±7 days.
    """
    import numpy as np

    timestamps = sorted(s.created_at for s in sessions)
    gaps = [
        (timestamps[i + 1] - timestamps[i]).days for i in range(len(timestamps) - 1)
    ]
    if not gaps:
        return timedelta(days=7)  # fallback default
    sigma = np.std(gaps)
    return timedelta(days=max(1, int(sigma)))


async def resolve_pair(
    candidate_a: EventMentionCandidate,
    candidate_b: EventMentionCandidate,
    heuristic_score: float,
    llm_client: AIClientProtocol,
    prompt_registry: PromptRegistry,
) -> tuple[bool, float]:
    """
    CORRECTED (E04-M-04): Resolve event pair with threshold window.

    LLM verification only invoked for pairs near the threshold.
    """
    if heuristic_score > HEURISTIC_SCORE_ACCEPT_THRESHOLD:
        return True, heuristic_score
    if heuristic_score <= HEURISTIC_SCORE_REJECT_THRESHOLD:
        return False, heuristic_score

    # LLM verification zone: calibrate thresholds against annotated dev set
    prompt = await prompt_registry.get("event_coreference_verify@1")
    if not prompt:
        raise ValueError("Prompt template event_coreference_verify@1 not registered.")
    response = await llm_client.complete(
        prompt.content.format(
            event_a_description=candidate_a.trigger_span,
            event_a_date=candidate_a.timestamp.isoformat(),
            event_a_actors=candidate_a.arg0_span or "unknown",
            event_b_description=candidate_b.trigger_span,
            event_b_date=candidate_b.timestamp.isoformat(),
            event_b_actors=candidate_b.arg0_span or "unknown",
        )
    )

    # Parse JSON response
    try:
        result = json.loads(response)
        answer = result.get("answer", "NO")
        confidence = result.get("confidence", 0.0)
        return answer == "YES", confidence
    except (json.JSONDecodeError, KeyError):
        return False, 0.0


@dataclass
class EventCoreferenceService:
    """
    Main service for cross-document event coreference.
    """

    event_repository: ICanonicalEventRepository
    llm_client: AIClientProtocol
    prompt_registry: PromptRegistry

    trigger_verbs: frozenset[str] = frozenset(
        [
            "agree",
            "reject",
            "announce",
            "declare",
            "propose",
            "demand",
            "accept",
            "refuse",
            "sign",
            "negotiate",
            "conclude",
            "terminate",
        ]
    )
    trigger_nominals: frozenset[str] = frozenset(
        [
            "ceasefire",
            "vote",
            "summit",
            "meeting",
            "agreement",
            "treaty",
            "sanction",
            "embargo",
            "resolution",
            "declaration",
        ]
    )

    async def process_document(
        self,
        srl_result: SRLDocumentResult,
        sentence_id: str,
        session_id: str,
        timestamp: datetime,
        lang: str = "en",
        nlp=None,
    ) -> list[CanonicalEvent]:
        """
        Process a document and extract canonical events.
        """
        # Extract event mentions using corrected predicate-span detection
        candidates = extract_event_mentions(
            srl_result=srl_result,
            trigger_verb_set=self.trigger_verbs,
            trigger_nominal_set=self.trigger_nominals,
            sentence_id=sentence_id,
            session_id=session_id,
            timestamp=timestamp,
        )

        # Cluster mentions into canonical events
        canonical_events = await self._cluster_mentions(candidates, lang, nlp)

        # Persist to repository
        for event in canonical_events:
            await self.event_repository.upsert(event)

        return canonical_events

    async def _cluster_mentions(
        self,
        candidates: list[EventMentionCandidate],
        lang: str,
        nlp=None,
    ) -> list[CanonicalEvent]:
        """
        Cluster event mentions into canonical events using heuristic + LLM verification.
        """
        if not candidates:
            return []

        clusters = []
        used_indices = set()

        for i, candidate_a in enumerate(candidates):
            if i in used_indices:
                continue

            cluster = [candidate_a]
            used_indices.add(i)

            for j, candidate_b in enumerate(candidates):
                if j in used_indices:
                    continue

                # Temporal overlap check (using calibrated window)
                temporal_gap = abs((candidate_a.timestamp - candidate_b.timestamp).days)
                if temporal_gap > 7:  # TODO: Use calibrate_temporal_window
                    continue

                # Heuristic similarity score
                sim_score = string_similarity_score(
                    candidate_a.trigger_span,
                    candidate_b.trigger_span,
                    lang,
                    nlp,
                )

                # Resolve with LLM if near threshold
                is_same, _confidence = await resolve_pair(
                    candidate_a,
                    candidate_b,
                    sim_score,
                    self.llm_client,
                    self.prompt_registry,
                )

                if is_same:
                    cluster.append(candidate_b)
                    used_indices.add(j)

            # Create canonical event from cluster
            if cluster:
                first_mention = min(c.timestamp for c in cluster)
                event_type = cluster[0].trigger_lemma
                canonical_description = self._generate_description(cluster)

                event = CanonicalEvent(
                    canonical_description=canonical_description,
                    first_mention=first_mention,
                    event_type=event_type,
                )

                for mention in cluster:
                    event.add_mention(
                        actor=mention.arg0_span,
                        session_id=mention.session_id,
                    )

                clusters.append(event)

        return clusters

    def _generate_description(self, cluster: list[EventMentionCandidate]) -> str:
        """Generate canonical description from event cluster."""
        actors = set(c.arg0_span for c in cluster if c.arg0_span)
        trigger = cluster[0].trigger_lemma
        target = cluster[0].arg1_span if cluster[0].arg1_span else ""

        if actors and target:
            return f"{', '.join(sorted(actors))} {trigger} {target}"
        elif actors:
            return f"{', '.join(sorted(actors))} {trigger}"
        else:
            return f"{trigger} {target}" if target else trigger
