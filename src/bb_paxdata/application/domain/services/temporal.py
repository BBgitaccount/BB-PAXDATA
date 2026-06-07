"""Temporal analyzer for speaker language drift detection."""

from typing import Any, Literal, Optional, get_args

import numpy as np
import structlog
from pydantic import BaseModel, field_validator

from bb_paxdata.application.domain.constants.speech_act_keys import (
    SPEECH_ACT_MODIFIER,
    SPEECH_ACT_PRIMARY,
)

from .drift_algorithms import (
    detect_illocutionary_drift,
    detect_lexical_drift,
    detect_risk_trajectory_drift,
    detect_sentiment_drift,
    detect_tone_drift,
    detect_topic_drift,
)

logger = structlog.get_logger(__name__)

_DRIFT_TYPE_V2 = Literal[
    "SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK", "ILLOCUTIONARY"
]


def normalize_drift_type(value: str) -> _DRIFT_TYPE_V2:
    if value in get_args(_DRIFT_TYPE_V2):
        return value  # type: ignore[return-value]
    return "RISK"  # Safe fallback for legacy rows


class DriftEvent(BaseModel):
    """Represents a detected drift event."""

    speaker_id: str
    panel_id: str
    drift_type: _DRIFT_TYPE_V2
    start_position: int  # global_sent_order
    end_position: int
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    before_state: str  # Örn: "cooperative tone"
    after_state: str  # Örn: "confrontational tone"
    confidence: float
    algorithm: str  # "CUSUM", "JS_DIVERGENCE", "MATTR"

    @field_validator("drift_type", mode="before")
    @classmethod
    def _coerce_legacy(cls, v: str) -> str:
        return normalize_drift_type(v)


class TemporalAnalyzer:
    """Analyzes temporal patterns and detects speaker language drift."""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__)

    def analyze_panel_drift(
        self,
        panel_data: dict[str, Any],
        speaker_data: dict[str, Any],
        sentence_data: list[dict[str, Any]],
    ) -> list[DriftEvent]:
        """
        Analyze a complete panel for drift events.

        Args:
            panel_data: Panel metadata
            speaker_data: Speaker information
            sentence_data: List of sentence analyses with temporal order

        Returns:
            List of detected drift events
        """
        drift_events = []
        panel_id = panel_data.get("panel_id", "unknown")

        # Group sentences by speaker
        speaker_sentences: dict[str, list[dict[str, Any]]] = {}
        for sentence in sentence_data:
            speaker_id = sentence.get("speaker_id")
            if speaker_id:
                if speaker_id not in speaker_sentences:
                    speaker_sentences[speaker_id] = []
                speaker_sentences[speaker_id].append(sentence)

        # Analyze each speaker for drift
        for speaker_id, sentences in speaker_sentences.items():
            if len(sentences) < 5:  # Need minimum sentences for drift analysis
                continue

            try:
                speaker_drifts = self._analyze_speaker_drift(
                    speaker_id, panel_id, sentences
                )
                drift_events.extend(speaker_drifts)

            except Exception as e:
                self.logger.error(
                    f"Error analyzing drift for speaker {speaker_id}: {e}"
                )
                continue

        self.logger.info(
            f"Analyzed panel {panel_id} for drift",
            speakers_analyzed=len(speaker_sentences),
            drift_events_found=len(drift_events),
        )

        return drift_events

    def _analyze_speaker_drift(
        self, speaker_id: str, panel_id: str, sentences: list[dict[str, Any]]
    ) -> list[DriftEvent]:
        """Analyze drift for a single speaker across a panel."""
        drift_events = []

        # Sort sentences by global position
        sentences.sort(key=lambda x: x.get("global_sent_order", 0))

        # Extract time series for different metrics
        sentiment_series = []
        topic_distributions = []
        lexical_diversity = []
        tone_series = []
        risk_trajectory = []
        speech_act_series = []
        force_modifiers = []
        positions = []

        for sentence in sentences:
            positions.append(sentence.get("global_sent_order", 0))

            # Sentiment
            sentiment = sentence.get("AI_Duygu_Skoru")
            if sentiment is not None:
                sentiment_series.append(sentiment)

            # Topic (one-hot encoded for distribution)
            topic = sentence.get("AI_Birincil_Konu")
            if topic:
                topic_distributions.append(topic)

            # Lexical diversity (word count per sentence)
            text = sentence.get("text", "")
            if text:
                word_count = len(text.split())
                lexical_diversity.append(word_count)

            # Tone
            tone = sentence.get("AI_Diplomatik_Ton")
            if tone:
                tone_series.append(tone)

            # Risk trajectory
            risk = sentence.get("AI_Risk_Skoru")
            if risk is not None:
                risk_trajectory.append(risk)

            # Speech Act & Modifier
            sa = (
                sentence.get(SPEECH_ACT_PRIMARY)
                or sentence.get("AI_Speech_Act")
                or "ASSERTIVE"
            )
            speech_act_series.append(sa)

            sa_mod = sentence.get(SPEECH_ACT_MODIFIER) or sentence.get(
                "AI_Speech_Act_Modifier"
            )
            force_modifiers.append(sa_mod)

        # Detect different types of drift
        drift_events.extend(
            self._detect_sentiment_drift(
                speaker_id, panel_id, positions, sentiment_series
            )
        )

        drift_events.extend(
            self._detect_topic_drift(
                speaker_id, panel_id, positions, topic_distributions
            )
        )

        drift_events.extend(
            self._detect_lexical_drift(
                speaker_id, panel_id, positions, lexical_diversity
            )
        )

        drift_events.extend(
            self._detect_tone_drift(speaker_id, panel_id, positions, tone_series)
        )

        drift_events.extend(
            self._detect_risk_drift(speaker_id, panel_id, positions, risk_trajectory)
        )

        drift_events.extend(
            self._detect_illocutionary_drift(
                speaker_id, panel_id, positions, speech_act_series, force_modifiers
            )
        )

        return drift_events

    def _detect_sentiment_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        sentiment_series: list[float],
    ) -> list[DriftEvent]:
        """Detect sentiment drift using CUSUM algorithm."""
        if len(sentiment_series) < 10:
            return []

        try:
            drift_points = detect_sentiment_drift(sentiment_series)

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                # Map to sentence positions
                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                # Determine before/after states
                before_sentiment = np.mean(sentiment_series[:start_idx])
                after_sentiment = np.mean(sentiment_series[end_idx:])

                before_state = self._sentiment_to_state(float(before_sentiment))
                after_state = self._sentiment_to_state(float(after_sentiment))

                severity = self._calculate_drift_severity(
                    float(abs(after_sentiment - before_sentiment)), "sentiment"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="SENTIMENT",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=before_state,
                    after_state=after_state,
                    confidence=drift_point["confidence"],
                    algorithm="CUSUM",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting sentiment drift: {e}")
            return []

    def _detect_topic_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        topic_distributions: list[str],
    ) -> list[DriftEvent]:
        """Detect topic drift using Jensen-Shannon divergence."""
        if len(topic_distributions) < 10:
            return []

        try:
            drift_points = detect_topic_drift(topic_distributions)

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                # Determine before/after topic distributions
                before_topics = topic_distributions[:start_idx]
                after_topics = topic_distributions[end_idx:]

                before_state = self._get_dominant_topic(before_topics)
                after_state = self._get_dominant_topic(after_topics)

                severity = self._calculate_drift_severity(
                    drift_point["divergence"], "topic"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="TOPIC",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=f"Topic focus: {before_state}",
                    after_state=f"Topic focus: {after_state}",
                    confidence=drift_point["confidence"],
                    algorithm="JS_DIVERGENCE",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting topic drift: {e}")
            return []

    def _detect_lexical_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        lexical_diversity: list[int],
    ) -> list[DriftEvent]:
        """Detect lexical drift using MATTR."""
        if len(lexical_diversity) < 10:
            return []

        try:
            drift_points = detect_lexical_drift(lexical_diversity)

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                before_diversity = np.mean(lexical_diversity[:start_idx])
                after_diversity = np.mean(lexical_diversity[end_idx:])

                before_state = f"Lexical diversity: {before_diversity:.1f}"
                after_state = f"Lexical diversity: {after_diversity:.1f}"

                severity = self._calculate_drift_severity(
                    float(abs(after_diversity - before_diversity)), "lexical"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="LEXICAL",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=before_state,
                    after_state=after_state,
                    confidence=drift_point["confidence"],
                    algorithm="MATTR",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting lexical drift: {e}")
            return []

    def _detect_tone_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        tone_series: list[str],
    ) -> list[DriftEvent]:
        """Detect tone drift using Markov transition matrix."""
        if len(tone_series) < 10:
            return []

        try:
            drift_points = detect_tone_drift(tone_series)

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                before_tones = tone_series[:start_idx]
                after_tones = tone_series[end_idx:]

                before_state = self._get_dominant_tone(before_tones)
                after_state = self._get_dominant_tone(after_tones)

                severity = self._calculate_drift_severity(
                    drift_point["transition_change"], "tone"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="TONE",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=f"Tone: {before_state}",
                    after_state=f"Tone: {after_state}",
                    confidence=drift_point["confidence"],
                    algorithm="MARKOV_TRANSITION",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting tone drift: {e}")
            return []

    def _detect_risk_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        risk_trajectory: list[int],
    ) -> list[DriftEvent]:
        """Detect risk trajectory drift using slope change detection."""
        if len(risk_trajectory) < 10:
            return []

        try:
            drift_points = detect_risk_trajectory_drift(risk_trajectory)

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                before_risk = np.mean(risk_trajectory[:start_idx])
                after_risk = np.mean(risk_trajectory[end_idx:])

                before_state = f"Risk level: {before_risk:.1f}"
                after_state = f"Risk level: {after_risk:.1f}"

                severity = self._calculate_drift_severity(
                    float(abs(after_risk - before_risk)), "risk"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="RISK",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=before_state,
                    after_state=after_state,
                    confidence=drift_point["confidence"],
                    algorithm="SLOPE_CHANGE",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting risk drift: {e}")
            return []

    def _sentiment_to_state(self, sentiment: float) -> str:
        """Convert sentiment score to descriptive state."""
        if sentiment > 0.3:
            return "positive"
        elif sentiment > -0.3:
            return "neutral"
        else:
            return "negative"

    def _get_dominant_topic(self, topics: list[str]) -> str:
        """Get most frequent topic from list."""
        if not topics:
            return "unknown"

        from collections import Counter

        counter = Counter(topics)
        return counter.most_common(1)[0][0]

    def _get_dominant_tone(self, tones: list[str]) -> str:
        """Get most frequent tone from list."""
        if not tones:
            return "unknown"

        from collections import Counter

        counter = Counter(tones)
        return counter.most_common(1)[0][0]

    def _detect_illocutionary_drift(
        self,
        speaker_id: str,
        panel_id: str,
        positions: list[int],
        speech_act_series: list[str],
        force_modifiers: list[Optional[str]],
    ) -> list[DriftEvent]:
        """Detect illocutionary drift using Searle's Speech Act Theory and ratio gates."""
        if len(speech_act_series) < 3:
            return []

        try:
            drift_points = detect_illocutionary_drift(
                speech_act_series, force_modifiers
            )

            drift_events = []
            for drift_point in drift_points:
                start_idx = drift_point["start_index"]
                end_idx = drift_point["end_index"]

                # Map window indices to global sentence positions
                start_pos = (
                    positions[start_idx]
                    if start_idx < len(positions)
                    else positions[-1]
                )
                end_pos = (
                    positions[end_idx] if end_idx < len(positions) else positions[-1]
                )

                severity = self._calculate_drift_severity(
                    drift_point["magnitude"], "illocutionary"
                )

                drift_event = DriftEvent(
                    speaker_id=speaker_id,
                    panel_id=panel_id,
                    drift_type="ILLOCUTIONARY",
                    start_position=start_pos,
                    end_position=end_pos,
                    severity=severity,
                    before_state=drift_point["before_state"],
                    after_state=drift_point["after_state"],
                    confidence=drift_point["confidence"],
                    algorithm="ILLOCUTIONARY_DRIFT",
                )

                drift_events.append(drift_event)

            return drift_events

        except Exception as e:
            self.logger.error(f"Error detecting illocutionary drift: {e}")
            return []

    def _calculate_drift_severity(
        self, magnitude: float, drift_type: str
    ) -> Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        """Calculate drift severity based on magnitude and type."""
        thresholds = {
            "sentiment": {"low": 0.3, "medium": 0.6, "high": 0.9},
            "topic": {"low": 0.2, "medium": 0.5, "high": 0.8},
            "lexical": {"low": 2.0, "medium": 4.0, "high": 6.0},
            "tone": {"low": 0.3, "medium": 0.6, "high": 0.9},
            "risk": {"low": 1.0, "medium": 2.0, "high": 3.0},
            "illocutionary": {"low": 0.5, "medium": 0.9, "high": 1.3},
        }

        type_thresholds = thresholds.get(drift_type, thresholds["sentiment"])

        if magnitude >= type_thresholds["high"]:
            return "CRITICAL"
        elif magnitude >= type_thresholds["medium"]:
            return "HIGH"
        elif magnitude >= type_thresholds["low"]:
            return "MEDIUM"
        else:
            return "LOW"
