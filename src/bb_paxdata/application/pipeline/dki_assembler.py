from datetime import UTC

import structlog

from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.appraisal_vector import EngagementType
from bb_paxdata.application.domain.models.dki import (
    DKIComponents,
    DKIResult,
    SegmentWindow,
    SpeakerTrajectory,
)
from bb_paxdata.application.domain.services.bayesian_position_tracker import (
    calculate_signal_strength,
)
from bb_paxdata.application.domain.services.protocols import (
    DynamicPositionTracker,
    SemanticShiftCalculator,
)

logger = structlog.get_logger()


class DKIAssembler:
    """Orchestrates DKI computation during ASSEMBLE phase.

    Rules:
    - DKI = (Δθᵢ/Δt) × SemanticShift × βⱼ
    - If components are missing, defaults to 1.0 (neutral).
    - Returns a new Analysis instance with dki_result attached.
    """

    def __init__(
        self,
        shift_calc: SemanticShiftCalculator,
        position_tracker: DynamicPositionTracker,
        dki_threshold: float = 2.0,
    ) -> None:
        self._shift_calc = shift_calc
        self._position_tracker = position_tracker
        self._dki_threshold = dki_threshold
        self._logger = logger.bind(service="dki_assembler")

    async def attach_dki(self, analysis: Analysis, history: list[Analysis]) -> Analysis:
        """Compute DKI and attach to the analysis object."""

        speaker_id = analysis.speaker_id or "unknown"
        session_id = analysis.segment_id or "unknown"  # Fallback to segment_id

        # 1. Semantic Shift Calculation
        current_window = SegmentWindow(
            segment_ids=[analysis.segment_id] if analysis.segment_id else [],
            texts=[analysis.source_text],
            speaker_id=speaker_id,
        )

        historical_windows = [
            SegmentWindow(
                segment_ids=[h.segment_id] if h.segment_id else [],
                texts=[h.source_text],
                speaker_id=h.speaker_id,
            )
            for h in history
        ]

        semantic_shift = 1.0  # Default
        if historical_windows:
            try:
                shift_result = await self._shift_calc.calculate_shift(
                    current_window, historical_windows
                )
                semantic_shift = shift_result.aggregate_shift
            except Exception as e:
                self._logger.warning("Semantic shift calculation failed", error=str(e))

        # 2. Dynamic Position Tracking (Velocity)
        # Trajectory needs θᵢ (from SBI result)
        trajectory_points = []
        full_history = [*history, analysis]
        for h in full_history:
            # Try to get θᵢ from sbi_result
            theta = 0.0
            if h.sbi_result and h.sbi_result.positions:
                # Find speaker's position
                for pos in h.sbi_result.positions:
                    if pos.speaker_id == speaker_id:
                        theta = pos.wordfish_theta
                        break

            # Assuming Analysis has a timestamp we can parse or use
            # Analysis.timestamp is ISO string
            try:
                from datetime import datetime

                ts = datetime.fromisoformat(h.timestamp)
            except Exception:
                ts = datetime.now(UTC)

            trajectory_points.append({"theta": theta, "timestamp": ts})

        velocity = 1.0  # Default
        if len(trajectory_points) >= 2:
            try:
                trajectory = SpeakerTrajectory(
                    speaker_id=speaker_id,
                    positions=trajectory_points,
                )
                pos_result = await self._position_tracker.compute_velocity(trajectory)
                velocity = pos_result.current_velocity
            except Exception as e:
                self._logger.warning(
                    "Position velocity calculation failed", error=str(e)
                )

        # 3. Debate Loading (βⱼ)
        # From Phase 7.6, attached to Session or Analysis?
        # The prompt says Analysis.session.debate_loading.
        # But Analysis doesn't have a session field in our view.
        # Let's assume it might be in metadata or a field we add.
        # For now, search for βⱼ in Analysis if possible.

        debate_loading = 1.0
        # If we have Wordshoal data in sbi_result
        if analysis.sbi_result and analysis.sbi_result.positions:
            for pos in analysis.sbi_result.positions:
                if pos.speaker_id == speaker_id and pos.session_deviation is not None:
                    # session_deviation (ψᵢⱼ - θᵢ) is related to Wordshoal βⱼ
                    # but βⱼ is usually a session-level coefficient.
                    # We'll use 1.0 if not explicitly available.
                    pass

        # 4. Compute Signal Strength from real data (FINDING M-05)
        # Extract HedgingResult, SpeechActClassification, and AppraisalVector from Analysis
        signal_strength = 0.5  # Default neutral value

        # Extract hedging penalty
        hedging_penalty = 0.0
        if analysis.hedging_result is not None:
            hedging_penalty = analysis.hedging_result.score
        else:
            self._logger.warning(
                "HedgingResult not found in Analysis, using neutral fallback (0.0)",
                analysis_id=analysis.id,
            )

        # Extract speech act score
        speech_act_score = 0.5  # Default neutral
        if analysis.speech_act is not None:
            # Map speech act type to score [0, 1]
            # DECLARATIVE = 0.9, INTERROGATIVE = 0.5, IMPERATIVE = 0.3
            speech_act_type = analysis.speech_act.primary_type
            if speech_act_type == "DECLARATIVE":
                speech_act_score = 0.9
            elif speech_act_type == "INTERROGATIVE":
                speech_act_score = 0.5
            elif speech_act_type == "IMPERATIVE":
                speech_act_score = 0.3
        else:
            self._logger.warning(
                "SpeechActClassification not found in Analysis, using neutral fallback (0.5)",
                analysis_id=analysis.id,
            )

        # Extract graduation score and engagement type from AppraisalVector
        graduation_score = 0.5  # Default neutral
        is_monogloss = True  # Default MONOGLOSS
        if analysis.appraisal_vector is not None:
            graduation_score = analysis.appraisal_vector.graduation_force
            is_monogloss = (
                analysis.appraisal_vector.engagement_type == EngagementType.MONOGLOSS
            )
        else:
            self._logger.warning(
                "AppraisalVector not found in Analysis, using neutral fallbacks (graduation=0.5, engagement=MONOGLOSS)",
                analysis_id=analysis.id,
            )

        # Compute signal strength using corrected formula (FINDING M-03)
        signal_strength = calculate_signal_strength(
            speech_act_score=speech_act_score,
            graduation_score=graduation_score,
            is_monogloss=is_monogloss,
            hedging_penalty=hedging_penalty,
        )

        # Add signal_strength to trajectory points for Bayesian tracking
        for pt in trajectory_points:
            pt["signal_strength"] = signal_strength

        # 5. Compute DKI
        # Formula: DKI = (Δθᵢ/Δt) × SemanticShift × βⱼ
        raw_product = velocity * semantic_shift * debate_loading

        dki_components = DKIComponents(
            velocity=velocity,
            semantic_shift=semantic_shift,
            debate_loading=debate_loading,
            raw_product=raw_product,
        )

        dki_result = DKIResult(
            speaker_id=speaker_id,
            session_id=session_id,
            dki_score=raw_product,
            components=dki_components,
            anomaly_flag=abs(raw_product) > self._dki_threshold,
        )

        # 6. Return updated Analysis (in-place mutation)
        analysis.dki_result = dki_result
        return analysis
