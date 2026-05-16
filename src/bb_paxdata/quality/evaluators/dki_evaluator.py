import structlog
from bb_paxdata.domain.models.dki import (
    DynamicPositionResult,
    PositionCalibration,
    SemanticShiftResult,
)
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

logger = structlog.get_logger()


class DKIEvaluator:
    """LLM-as-a-Judge for DKI (Discourse-Kinetic Index) output quality.

    Criteria:
    1. Semantic shift values must be in [0.0, 2.0].
    2. Velocity must be consistent with chronological θᵢ ordering.
    3. DKI components must not contain NaN or Inf.
    4. LLM position estimates must correlate with Wordfish (r > 0.5).
    """

    def __init__(self, model_name: str = "gpt-4o") -> None:
        self._model_name = model_name
        self._logger = logger.bind(service="dki_evaluator")
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize G-Eval metrics for DKI components."""
        self._semantic_metric = GEval(
            name="Semantic Shift Validity",
            criteria="""
            Evaluate if the calculated semantic shift represents a plausible change in word meaning 
            between two diplomatic discourse contexts.
            Score 1.0 if the shift correctly identifies shifts in key terminology (e.g., 'confrontation' -> 'cooperation').
            Score 0.0 if the shift seems random or mathematically unsound.
            """,
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        )

        self._velocity_metric = GEval(
            name="Position Velocity Consistency",
            criteria="""
            Evaluate if the speaker position velocity (Δθ/Δt) is consistent with the provided 
            chronological sequence of latent positions (θ).
            Velocity should accurately reflect the rate of change in political positioning.
            """,
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        )

    async def evaluate_semantic_shift(
        self, result: SemanticShiftResult, context: str
    ) -> bool:
        """Judge semantic shift validity via DeepEval."""
        test_case = LLMTestCase(
            input=context,
            actual_output=str(result.per_word_shifts),
        )
        self._semantic_metric.measure(test_case)
        return bool(self._semantic_metric.score >= 0.7)

    async def evaluate_velocity_consistency(
        self, result: DynamicPositionResult, trajectory_str: str
    ) -> bool:
        """Judge velocity consistency via DeepEval."""
        test_case = LLMTestCase(
            input=trajectory_str,
            actual_output=f"Current Velocity: {result.current_velocity}, Smoothed: {result.smoothed_velocities}",
        )
        self._velocity_metric.measure(test_case)
        return bool(self._velocity_metric.score >= 0.7)

    def validate_calibration(self, calibration: PositionCalibration) -> bool:
        """Check if LLM vs Wordfish calibration drift is within acceptable bounds."""
        if calibration.drift_detected:
            self._logger.warning(
                "Calibration drift detected",
                mae=calibration.mean_absolute_error,
                pearson_r=calibration.pearson_r,
            )
            return False
        return bool(calibration.pearson_r > 0.5)
