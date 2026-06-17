"""
Presupposition Extraction Service
Domain service for presupposition extraction with async support.
Registered as lazy singleton in ServiceContainer.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from spacy.tokens import Doc, Token

from bb_paxdata.application.domain.lexicon.presupposition_triggers import (
    PresuppositionLexicon,
)
from bb_paxdata.application.domain.models.negation_cue import LanguageCode
from bb_paxdata.application.domain.models.presupposition import (
    Presupposition,
    PresuppositionCandidate,
    PresuppositionExtractionResult,
    TriggerType,
    VerificationMethod,
)
from bb_paxdata.application.domain.services.negation_detector_protocol import (
    NegationDetectorProtocol,
)
from bb_paxdata.application.domain.services.presupposition_verifier import (
    PresuppositionVerifier,
)

logger = structlog.get_logger(__name__)


class PresuppositionService:
    """
    Domain service for presupposition extraction.
    Registered as lazy singleton in ServiceContainer.
    """

    def __init__(
        self,
        verifier: PresuppositionVerifier,
        lexicon: PresuppositionLexicon,
        negation_detector: NegationDetectorProtocol,
        llm_confidence_threshold: float = 0.85,
        use_llm_verification: bool = True,
    ) -> None:
        """
        Initialize the presupposition service.

        Args:
            verifier: LLM verifier for low-confidence candidates
            lexicon: Language-aware trigger lexicon
            negation_detector: Existing negation detector for projection
            llm_confidence_threshold: Threshold for LLM verification
            use_llm_verification: Whether to use LLM verification
        """
        self._verifier = verifier
        self._lexicon = lexicon
        self._negation_detector = negation_detector
        self._llm_confidence_threshold = llm_confidence_threshold
        self._use_llm_verification = use_llm_verification

    async def extract(
        self,
        doc: Doc,
        segment_id: str,
        speaker: str,
        timestamp: float | None = None,
        language: str = "en",
    ) -> PresuppositionExtractionResult:
        """
        Extract presuppositions from a spaCy Doc.

        Args:
            doc: spaCy Doc object with dependency parse
            segment_id: ID of the source segment
            speaker: Speaker who uttered the text
            timestamp: Timestamp of the utterance
            language: Language code ("en" or "tr")

        Returns:
            PresuppositionExtractionResult with extracted presuppositions
        """
        start_time = time.time()

        # Rule-based layer is CPU-bound (spaCy token iteration)
        candidates = await asyncio.to_thread(
            self._run_rule_layer, doc, segment_id, speaker, timestamp, language
        )

        total_triggers = len(candidates)

        # Apply negation projection
        candidates = await self._apply_negation_projection(doc, candidates, language)

        # Filter and verify
        if self._use_llm_verification:
            low_conf = [
                c for c in candidates if c.confidence < self._llm_confidence_threshold
            ]
            high_conf = [
                c for c in candidates if c.confidence >= self._llm_confidence_threshold
            ]

            verified_low = await self._verifier.verify_batch(low_conf)
            candidates = high_conf + verified_low

        # Build result
        presuppositions = [
            (
                c
                if isinstance(c, Presupposition)
                else self._candidate_to_presupposition(c, VerificationMethod.RULE)
            )
            for c in candidates
        ]

        processing_time_ms = (time.time() - start_time) * 1000

        return PresuppositionExtractionResult(
            presuppositions=presuppositions,
            total_triggers_found=total_triggers,
            verified_count=len(
                [
                    p
                    for p in presuppositions
                    if p.verification_method == VerificationMethod.LLM
                ]
            ),
            false_positive_filtered=total_triggers - len(presuppositions),
            processing_time_ms=processing_time_ms,
            language_detected=language,
        )

    def _run_rule_layer(
        self,
        doc: Doc,
        segment_id: str,
        speaker: str,
        timestamp: float | None,
        language: str,
    ) -> list[PresuppositionCandidate]:
        """
        CPU-bound rule-based extraction layer.
        Runs in thread pool via asyncio.to_thread.
        """
        candidates: list[PresuppositionCandidate] = []
        segment_text = doc.text

        # Get language-specific lexicon
        lexicon = PresuppositionLexicon.for_language(language)

        for token in doc:
            lemma = token.lemma_.lower()

            # Check if token is a trigger
            trigger_type = lexicon.get_trigger_type(lemma)
            if trigger_type is None:
                continue

            # Extract presupposed content based on trigger type
            presupposed_content = self._extract_presupposed_content(
                token, doc, trigger_type, language
            )

            if not presupposed_content:
                continue

            # Calculate base confidence using domain model rules
            confidence = PresuppositionCandidate.calculate_confidence(
                trigger_lemma=lemma,
                presupposed_content=presupposed_content,
                sentence_length=len(token.sent),
            )

            candidate = PresuppositionCandidate(
                trigger_word=token.text,
                trigger_type=trigger_type,
                presupposed_content=presupposed_content,
                confidence=confidence,
                segment_id=segment_id,
                speaker=speaker,
                segment_text=segment_text,
                timestamp=timestamp,
            )
            candidates.append(candidate)

        return candidates

    async def _apply_negation_projection(
        self,
        doc: Doc,
        candidates: list[PresuppositionCandidate],
        language: str,
    ) -> list[PresuppositionCandidate]:
        """
        Apply presupposition projection under negation.
        Presuppositions of factive, implicative, and change-of-state verbs
        survive sentential negation. Temporal adverb presuppositions do NOT
        project under all negation scopes (cancellable in "not anymore").
        """
        if not candidates:
            return candidates

        # Get negation cues from the detector
        lang_code = LanguageCode.TR if language == "tr" else LanguageCode.EN
        negation_result = await self._negation_detector.detect_with_doc(
            doc, "temp", lang_code
        )

        filtered_candidates: list[PresuppositionCandidate] = []

        for candidate in candidates:
            # Find the trigger token in the doc
            trigger_token = self._find_token_by_text(doc, candidate.trigger_word)
            if not trigger_token:
                filtered_candidates.append(candidate)
                continue

            # Check if trigger is in negation scope
            in_negation_scope = self._is_in_negation_scope(
                trigger_token, negation_result
            )

            if in_negation_scope:
                if candidate.trigger_type in {
                    TriggerType.FACTIVE_VERB,
                    TriggerType.IMPLICATIVE_VERB,
                    TriggerType.CHANGE_OF_STATE,
                }:
                    # Presupposition projects: mark as negation-projected
                    # Slight confidence downgrade
                    candidate.confidence *= 0.95
                    filtered_candidates.append(candidate)
                elif candidate.trigger_type == TriggerType.TEMPORAL_ADVERB:
                    # "no longer X" cancels the temporal presupposition
                    if trigger_token.text.lower() in {"anymore", "no longer", "artık"}:
                        logger.debug(
                            "Filtered temporal presupposition under negation",
                            trigger=trigger_token.text,
                        )
                        continue  # Filter out
                    else:
                        filtered_candidates.append(candidate)
                else:
                    filtered_candidates.append(candidate)
            else:
                filtered_candidates.append(candidate)

        return filtered_candidates

    def _extract_presupposed_content(
        self,
        token: Token,
        doc: Doc,
        trigger_type: TriggerType,
        language: str,
    ) -> str:
        """
        Extract the presupposed content based on trigger type.
        """
        if trigger_type == TriggerType.FACTIVE_VERB:
            # Factive verbs presuppose their complement
            that_clause = self._extract_that_clause(token, doc)
            if that_clause:
                return that_clause
            # Fallback: object
            obj = self._find_object(token, doc)
            return obj if obj else ""

        elif trigger_type == TriggerType.IMPLICATIVE_VERB:
            # Implicative verbs presuppose success or failure
            obj = self._find_object(token, doc)
            return obj if obj else ""

        elif trigger_type in (
            TriggerType.TEMPORAL_ADVERB,
            TriggerType.TEMPORAL_MULTIWORD,
        ):
            # Temporal adverbs presuppose previous state
            subject = self._find_subject(token, doc)
            action = self._extract_action(token, doc)
            return f"{subject} {action}" if subject and action else ""

        elif trigger_type == TriggerType.CHANGE_OF_STATE:
            # Change of state verbs presuppose previous state
            subject = self._find_subject(token, doc)
            return f"{subject} existed" if subject else ""

        elif trigger_type == TriggerType.DEFINITE_NP:
            # Definite NPs presuppose existence
            return token.text

        elif trigger_type == TriggerType.CLEFT_CONSTRUCTION:
            # Cleft constructions presuppose uniqueness
            focus = self._extract_focus_np(token, doc)
            return focus if focus else ""

        return ""

    # ===== Helper Functions (C-06) =====

    def _find_subject(self, token: Token, doc: Doc) -> str:
        """
        Find the nominal subject of a token using nsubj/nsubjpass dependency arcs.
        Falls back to empty string if no subject is found.
        """
        for child in token.children:
            if child.dep_ in ("nsubj", "nsubjpass", "csubj"):
                # Return the full span of the subject NP
                return doc[child.left_edge.i : child.right_edge.i + 1].text
        # Walk up to find a subject attached to a head verb
        if token.head != token and token.head.pos_ == "VERB":
            return self._find_subject(token.head, doc)
        return ""

    def _find_object(self, token: Token, doc: Doc) -> str:
        """
        Find the direct object of a token using dobj/iobj dependency arcs.
        """
        for child in token.children:
            if child.dep_ in ("dobj", "iobj"):
                return doc[child.left_edge.i : child.right_edge.i + 1].text
        return ""

    def _extract_focus_np(self, token: Token, doc: Doc) -> str:
        """
        Extract the focused noun phrase in cleft constructions.
        """
        # Look for cleft pattern: "It is/was X that/who Y"
        if token.text.lower() in ("it", "this"):
            for child in token.children:
                if child.dep_ == "attr" or child.pos_ == "NOUN":
                    return doc[child.left_edge.i : child.right_edge.i + 1].text
        return ""

    def _extract_that_clause(self, token: Token, doc: Doc) -> str:
        """
        Extract the that-clause complement of a verb.
        """
        for child in token.children:
            if child.dep_ in ("ccomp", "mark"):
                # Find the clausal complement
                if child.text.lower() == "that":
                    # Get the next sibling which should be the clause
                    for sibling in child.rights:
                        if sibling.dep_ in ("ccomp", "advcl"):
                            return doc[
                                sibling.left_edge.i : sibling.right_edge.i + 1
                            ].text
                else:
                    return doc[child.left_edge.i : child.right_edge.i + 1].text
        return ""

    def _extract_action(self, token: Token, doc: Doc) -> str:
        """
        Extract the action/verb phrase associated with a token.
        """
        if token.pos_ == "VERB":
            return doc[token.left_edge.i : token.right_edge.i + 1].text
        if token.head.pos_ == "VERB":
            return doc[token.head.left_edge.i : token.head.right_edge.i + 1].text
        return ""

    def _is_known_entity(self, entity_text: str, doc: Doc) -> bool:
        """
        Check if a noun is a named entity recognized by spaCy NER.
        Does NOT call an external entity list — uses the NER spans already
        on the Doc object (populated by SpacyAdapter upstream).
        """
        ent_texts = {ent.text.lower() for ent in doc.ents}
        return entity_text.lower() in ent_texts

    def _find_token_by_text(self, doc: Doc, text: str) -> Token | None:
        """Find a token in the doc by its text."""
        for token in doc:
            if token.text == text:
                return token
        return None

    def _is_in_negation_scope(
        self,
        token: Token,
        negation_result: Any,
    ) -> bool:
        """
        Check if a token is within the scope of negation.
        """
        if not negation_result or not negation_result.cues:
            return False

        for cue in negation_result.cues:
            # Check if token index is within cue scope
            # NegationCue has scope_tokens which is a tuple of token texts
            # We need to check if our token is in that scope
            if hasattr(cue, "scope_tokens") and cue.scope_tokens:
                # Simple check: if token text is in scope_tokens
                if token.text in cue.scope_tokens:
                    return True

        return False

    def _candidate_to_presupposition(
        self,
        candidate: PresuppositionCandidate,
        verification_method: VerificationMethod,
    ) -> Presupposition:
        """Convert a candidate to a Presupposition model."""
        return Presupposition(
            trigger_word=candidate.trigger_word,
            trigger_type=candidate.trigger_type,
            presupposed_content=candidate.presupposed_content,
            confidence=candidate.confidence,
            segment_id=candidate.segment_id,
            speaker=candidate.speaker,
            timestamp=candidate.timestamp,
            verification_method=verification_method,
        )
