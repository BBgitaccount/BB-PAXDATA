# src/bb_paxdata/domain/services/narrative_salience_tracker.py
import math

import structlog

from bb_paxdata.application.domain.models.frame_annotation import FrameSalienceResult
from bb_paxdata.application.domain.models.speech_act import (
    SpeechActClassification,
    SpeechActType,
)

logger = structlog.get_logger(__name__)


class NarrativeSalienceTracker:
    """Computes narrative salience scores integrating Frame Salience and Speech Act modifiers."""

    def __init__(
        self, speech_act_weight: float = 0.25, sigmoid_scale: float = 1.5
    ) -> None:
        self.speech_act_weight = speech_act_weight
        self.sigmoid_scale = sigmoid_scale
        self._log = logger.bind(service="narrative_salience_tracker")

    def calculate_speech_act_modifier(
        self, speech_act: SpeechActClassification | None
    ) -> float:
        """Computes speech act multiplier Omega(d).

        Directive and Declarative types increase weight. ASSERTIVE types receive no
        modifier (returns 1.0).
        Reference: Searle (1969) speech act taxonomy as applied in TASK-A04.
        """
        if not speech_act:
            return 1.0

        # Self-contained coercive check (Option B from FINDING P-02)
        coercive_modifiers = frozenset(
            {"strongly", "firmly", "categorically", "unconditionally", "immediately"}
        )
        is_coercive = (
            speech_act.force_modifier is not None
            and speech_act.force_modifier.lower() in coercive_modifiers
        )

        if speech_act.primary_type in (
            SpeechActType.DIRECTIVE,
            SpeechActType.DECLARATIVE,
        ):
            modifier = 1.0 + (self.speech_act_weight * speech_act.confidence)
            if is_coercive:
                modifier += 0.15
            return modifier

        return 1.0

    def compute_salience(
        self,
        base_frequency: int,
        frame_salience: FrameSalienceResult | None,
        speech_act: SpeechActClassification | None,
    ) -> float:
        """Calculates normalized salience score: Freq * FrameAlignment * SpeechActModifier."""
        if base_frequency <= 0:
            return 0.0

        # Get frame alignment from Entman dominant frame salience
        frame_alignment = 1.0
        if frame_salience and frame_salience.dominant_frame:
            dominant_score = frame_salience.salience_scores.get(
                frame_salience.dominant_frame, 0.0
            )
            frame_alignment = max(0.5, dominant_score)

        speech_act_mod = self.calculate_speech_act_modifier(speech_act)

        # Calculate raw score and map to [0.0, 1.0] interval using sigmoidal scaling
        raw_score = float(base_frequency) * frame_alignment * speech_act_mod

        # Sigmoid compression to fit [0.0, 1.0] range (FINDING P-04 calibrated sigmoid_scale)
        salience_score = 2.0 / (1.0 + math.exp(-raw_score / self.sigmoid_scale)) - 1.0

        return round(max(0.0, min(1.0, salience_score)), 4)
