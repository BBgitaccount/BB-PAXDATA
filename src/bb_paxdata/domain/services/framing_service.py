"""Framing analysis service for diplomatic discourse.

This service detects and analyzes framing strategies in diplomatic discourse.
It identifies different frame types, evidence types, appraisal attitudes, and
target audiences to understand how issues are presented and positioned.
"""

from typing import Any, ClassVar

from ...application.protocols import (
    BaseService,
    FrameResult,
    FramingServiceProtocol,
    NERServiceProtocol,
)
from ...domain.enums import AppraisalAttitude, AudienceType, EvidenceType, FrameType
from ...domain.models.sentence import Sentence


class FramingService(BaseService, FramingServiceProtocol):
    """Service for framing analysis in diplomatic discourse."""

    # Frame lexicon organized by topic (from DatabaseBuilder_v5_8.py)
    FRAME_LEXICON: ClassVar[dict[str, dict[str, list[str]]]] = {
        "Gazze_Filistin_İsrail": {
            "conflict_frame": [
                "war",
                "conflict",
                "violence",
                "aggression",
                "attack",
                "military",
            ],
            "humanitarian_frame": [
                "humanitarian",
                "aid",
                "refugees",
                "civilians",
                "suffering",
                "crisis",
            ],
            "political_frame": [
                "negotiation",
                "diplomacy",
                "solution",
                "peace",
                "agreement",
                "settlement",
            ],
            "legal_frame": [
                "international law",
                "genocide",
                "war crimes",
                "justice",
                "court",
                "violation",
            ],
        },
        "Ukrayna_Rusya": {
            "conflict_frame": [
                "invasion",
                "war",
                "aggression",
                "attack",
                "military",
                "defense",
            ],
            "sovereignty_frame": [
                "sovereignty",
                "territorial integrity",
                "independence",
                "freedom",
                "self-determination",
            ],
            "security_frame": [
                "security",
                "nato",
                "alliance",
                "deterrence",
                "threat",
                "defense",
            ],
            "economic_frame": [
                "sanctions",
                "economy",
                "energy",
                "trade",
                "financial",
                "reconstruction",
            ],
        },
        "BM_Reformu": {
            "reform_frame": [
                "reform",
                "change",
                "modernize",
                "transform",
                "update",
                "improve",
            ],
            "representation_frame": [
                "representation",
                "inclusion",
                "voice",
                "participation",
                "equality",
            ],
            "legitimacy_frame": [
                "legitimacy",
                "authority",
                "credibility",
                "respect",
                "recognition",
            ],
            "effectiveness_frame": [
                "effective",
                "efficient",
                "functional",
                "capable",
                "responsive",
            ],
        },
        "Ekonomi_Ticaret_Enerji": {
            "cooperation_frame": [
                "cooperation",
                "partnership",
                "collaboration",
                "joint",
                "shared",
            ],
            "development_frame": [
                "development",
                "growth",
                "progress",
                "prosperity",
                "advancement",
            ],
            "competition_frame": [
                "competition",
                "rivalry",
                "contest",
                "compete",
                "challenge",
            ],
            "sustainability_frame": [
                "sustainable",
                "environment",
                "climate",
                "green",
                "renewable",
            ],
        },
        "Güvenlik_Çatışma": {
            "threat_frame": ["threat", "danger", "risk", "menace", "hazard", "peril"],
            "stability_frame": [
                "stability",
                "peace",
                "calm",
                "order",
                "security",
                "tranquility",
            ],
            "deterrence_frame": [
                "deterrence",
                "prevention",
                "deter",
                "discourage",
                "prevent",
            ],
            "escalation_frame": [
                "escalation",
                "increase",
                "rise",
                "grow",
                "intensify",
                "worsen",
            ],
        },
    }

    # Evidence types classification
    EVIDENCE_TYPES: ClassVar[dict[str, list[str]]] = {
        "statistical": [
            "data",
            "statistics",
            "numbers",
            "figures",
            "percent",
            "rate",
            "survey",
        ],
        "expert": [
            "expert",
            "specialist",
            "authority",
            "professional",
            "scholar",
            "academic",
        ],
        "historical": [
            "history",
            "historical",
            "past",
            "traditionally",
            "historically",
            "ancient",
        ],
        "testimonial": [
            "testimony",
            "witness",
            "account",
            "experience",
            "story",
            "personal",
        ],
        "documentary": ["document", "report", "record", "file", "evidence", "proof"],
        "anecdotal": [
            "anecdote",
            "example",
            "instance",
            "case",
            "illustration",
            "story",
        ],
    }

    # Appraisal signals
    APPRAISAL_SIGNALS: ClassVar[dict[str, list[str]]] = {
        "positive": [
            "good",
            "positive",
            "beneficial",
            "helpful",
            "valuable",
            "important",
            "effective",
        ],
        "negative": [
            "bad",
            "negative",
            "harmful",
            "dangerous",
            "problematic",
            "serious",
            "critical",
        ],
        "neutral": [
            "neutral",
            "objective",
            "balanced",
            "impartial",
            "unbiased",
            "fair",
            "moderate",
        ],
    }

    # Audience signals
    AUDIENCE_SIGNALS: ClassVar[dict[str, list[str]]] = {
        "international": [
            "international",
            "global",
            "world",
            "un",
            "foreign",
            "abroad",
        ],
        "domestic": ["domestic", "national", "local", "internal", "home", "citizen"],
        "expert": ["expert", "technical", "professional", "academic", "specialized"],
        "general": ["people", "public", "everyone", "society", "community"],
    }

    def __init__(self, ner_service: NERServiceProtocol | None = None) -> None:
        """Initialize the framing service.

        Args:
            ner_service: Optional NER service for enhanced analysis
        """
        super().__init__()
        self._ner_service = ner_service

    def analyze(self, sentence: Sentence, **kwargs: Any) -> Any:
        """Analyze framing in a sentence.

        Args:
            sentence: The sentence to analyze
            **kwargs: Additional analysis parameters

        Returns:
            FramingResult containing frame analysis
        """
        return self.detect_frame(sentence)

    def detect_frame(self, sentence: Sentence) -> FrameResult:
        """Detect framing in a sentence.

        Args:
            sentence: The sentence to analyze

        Returns:
            FrameResult containing frame type and related information
        """
        text = sentence.text.lower()

        # Get dominant topic if available
        dominant_topic = getattr(sentence, "dominant_topic", None)
        if not dominant_topic:
            # Try to infer topic from text
            dominant_topic = self._infer_topic(text)

        # Detect frame type
        frame_type = self._detect_frame_type(text, dominant_topic)

        # Classify evidence types
        evidence_types = self._classify_evidence(text)

        # Determine appraisal attitude
        appraisal_attitude = self._appraisal_score(text)

        # Detect audience type
        audience_type = self._detect_audience(text)

        # Calculate confidence
        confidence = self._calculate_confidence(text, frame_type, evidence_types)

        return FrameResult(
            frame_type=frame_type,
            evidence_types=evidence_types,
            appraisal_attitude=appraisal_attitude,
            audience_type=audience_type,
            confidence=confidence,
        )

    def _infer_topic(self, text: str) -> str | None:
        """Infer the dominant topic from text.

        Args:
            text: Text to analyze

        Returns:
            Inferred topic name or None
        """
        topic_scores = {}

        for topic, frames in self.FRAME_LEXICON.items():
            score = 0
            for _frame_type, keywords in frames.items():
                for keyword in keywords:
                    if keyword in text:
                        score += 1
            topic_scores[topic] = score

        if not topic_scores or all(score == 0 for score in topic_scores.values()):
            return None

        return max(topic_scores, key=lambda k: float(topic_scores[k]))

    def _detect_frame_type(self, text: str, topic: str | None) -> FrameType:
        """Detect the dominant frame type.

        Args:
            text: Text to analyze
            topic: Optional topic for context-aware framing

        Returns:
            Detected frame type
        """
        frame_scores = {}

        # If topic is known, use topic-specific frames
        if topic and topic in self.FRAME_LEXICON:
            for frame_type, keywords in self.FRAME_LEXICON[topic].items():
                score = sum(1 for keyword in keywords if keyword in text)
                frame_scores[frame_type] = score
        else:
            # Check all frames across all topics
            for topic_data in self.FRAME_LEXICON.values():
                for frame_type, keywords in topic_data.items():
                    if frame_type not in frame_scores:
                        frame_scores[frame_type] = 0
                    score = sum(1 for keyword in keywords if keyword in text)
                    frame_scores[frame_type] += score

        if not frame_scores or all(score == 0 for score in frame_scores.values()):
            return FrameType.NEUTRAL

        # Map frame names to FrameType enum
        frame_mapping = {
            "conflict_frame": FrameType.CONFLICT_FRAME,
            "humanitarian_frame": FrameType.HUMANITARIAN_FRAME,
            "political_frame": FrameType.NEGOTIATION_FRAME,
            "legal_frame": FrameType.LEGAL_FRAME,
            "sovereignty_frame": FrameType.SOVEREIGNTY_FRAME,
            "security_frame": FrameType.SECURITY_FRAME,
            "economic_frame": FrameType.EFFECTIVENESS_FRAME,
            "reform_frame": FrameType.NEGOTIATION_FRAME,
            "representation_frame": FrameType.MULTILATERAL_FRAME,
            "legitimacy_frame": FrameType.SOVEREIGNTY_FRAME,
            "effectiveness_frame": FrameType.EFFECTIVENESS_FRAME,
            "cooperation_frame": FrameType.PEACE_FRAME,
            "development_frame": FrameType.EFFECTIVENESS_FRAME,
            "competition_frame": FrameType.SECURITY_FRAME,
            "sustainability_frame": FrameType.EFFECTIVENESS_FRAME,
            "threat_frame": FrameType.THREAT_FRAME,
            "stability_frame": FrameType.PEACE_FRAME,
            "deterrence_frame": FrameType.DETERRENCE_FRAME,
            "escalation_frame": FrameType.THREAT_FRAME,
        }

        dominant_frame = max(frame_scores, key=lambda k: float(frame_scores[k]))
        return frame_mapping.get(dominant_frame, FrameType.NEUTRAL)

    def _classify_evidence(self, text: str) -> list[EvidenceType]:
        """Classify evidence types used in the text.

        Args:
            text: Text to analyze

        Returns:
            List of detected evidence types
        """
        detected_types = []

        for evidence_type, keywords in self.EVIDENCE_TYPES.items():
            if any(keyword in text for keyword in keywords):
                if evidence_type == "statistical":
                    detected_types.append(EvidenceType.STATISTICAL)
                elif evidence_type == "expert":
                    detected_types.append(EvidenceType.AUTHORITY)
                elif evidence_type == "historical":
                    detected_types.append(EvidenceType.HISTORICAL)
                elif evidence_type == "testimonial":
                    detected_types.append(EvidenceType.AUTHORITY)
                elif evidence_type == "documentary":
                    detected_types.append(EvidenceType.LOGICAL)
                elif evidence_type == "anecdotal":
                    detected_types.append(EvidenceType.ANECDOTAL)

        return detected_types if detected_types else [EvidenceType.NONE]

    def _appraisal_score(self, text: str) -> AppraisalAttitude:
        """Determine the appraisal attitude.

        Args:
            text: Text to analyze

        Returns:
            Appraisal attitude
        """
        positive_count = sum(
            1 for word in self.APPRAISAL_SIGNALS["positive"] if word in text
        )
        negative_count = sum(
            1 for word in self.APPRAISAL_SIGNALS["negative"] if word in text
        )
        neutral_count = sum(
            1 for word in self.APPRAISAL_SIGNALS["neutral"] if word in text
        )

        if positive_count > negative_count and positive_count > neutral_count:
            return AppraisalAttitude.JUDGEMENT_POSITIVE
        elif negative_count > positive_count and negative_count > neutral_count:
            return AppraisalAttitude.JUDGEMENT_NEGATIVE
        elif neutral_count > 0:
            return AppraisalAttitude.NEUTRAL
        elif positive_count == negative_count:
            return AppraisalAttitude.NEUTRAL
        elif positive_count > 0:
            return AppraisalAttitude.JUDGEMENT_POSITIVE
        elif negative_count > 0:
            return AppraisalAttitude.JUDGEMENT_NEGATIVE
        else:
            return AppraisalAttitude.NEUTRAL

    def _detect_audience(self, text: str) -> AudienceType:
        """Detect the target audience.

        Args:
            text: Text to analyze

        Returns:
            Target audience type
        """
        # Check for NER GPE references for international audience
        gpe_count = 0
        if self._ner_service:
            entities = self._ner_service.extract_entities(text)
            gpe_count = len(entities.get("GPE", []))

        international_count = sum(
            1 for word in self.AUDIENCE_SIGNALS["international"] if word in text
        )
        domestic_count = sum(
            1 for word in self.AUDIENCE_SIGNALS["domestic"] if word in text
        )
        expert_count = sum(
            1 for word in self.AUDIENCE_SIGNALS["expert"] if word in text
        )
        general_count = sum(
            1 for word in self.AUDIENCE_SIGNALS["general"] if word in text
        )

        # Enhanced international detection with GPE entities
        international_score = international_count + (gpe_count * 0.5)

        if international_score > domestic_count and international_score > expert_count:
            return AudienceType.GLOBAL_AUDIENCE
        elif domestic_count > expert_count and domestic_count > general_count:
            return AudienceType.DOMESTIC_AUDIENCE
        elif expert_count > general_count:
            return AudienceType.INSTITUTIONAL_AUDIENCE
        elif general_count > 0:
            return AudienceType.GENERAL
        else:
            return AudienceType.GENERAL

    def _calculate_confidence(
        self, text: str, frame_type: FrameType, evidence_types: list[EvidenceType]
    ) -> float:
        """Calculate confidence score for the analysis.

        Args:
            text: Original text
            frame_type: Detected frame type
            evidence_types: Detected evidence types

        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5  # Base confidence

        # Increase confidence if frame is not neutral
        if frame_type != FrameType.NEUTRAL:
            confidence += 0.2

        # Increase confidence based on evidence types
        if evidence_types and evidence_types != [EvidenceType.NONE]:
            confidence += 0.1 * min(len(evidence_types), 2)  # Cap at 0.2

        # Increase confidence for longer texts (more context)
        word_count = len(text.split())
        if word_count > 10:
            confidence += 0.1

        return min(1.0, confidence)
