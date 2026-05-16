from dataclasses import dataclass

from ..core.context import AnalysisContext
from ..core.models import Analysis, AnomalyResult, AnomalySeverity, SegmentRef
from .base import BaseAnomalyRule


@dataclass(frozen=True)
class FrameContradictionConfig:
    """Frame Contradiction kuralı için konfigürasyon."""

    contradiction_matrix: dict[tuple[str, str], float] = None
    min_frame_confidence: float = 0.7

    def __post_init__(self):
        # Varsayılan çelişki matrisi
        if self.contradiction_matrix is None:
            object.__setattr__(
                self,
                "contradiction_matrix",
                {
                    ("peaceful_problem", "military_solution"): 0.95,
                    ("economic_growth", "economic_collapse"): 0.90,
                    ("diplomatic_solution", "aggressive_action"): 0.85,
                },
            )


class FrameContradictionRule(BaseAnomalyRule):
    """
    ID: RULE_FRAME_CONTRADICTION
    Mantık: Problem tanımı ile çözüm önerisi çerçevelerinin çelişmesi.
    """

    def __init__(self, config: FrameContradictionConfig | None = None):
        self._config = config or FrameContradictionConfig()

    @property
    def rule_id(self) -> str:
        return "RULE_FRAME_CONTRADICTION"

    @property
    def rule_name(self) -> str:
        return "Frame Contradiction (Çerçeve Çelişkisi)"

    @property
    def severity(self) -> AnomalySeverity:
        return AnomalySeverity.HIGH

    def evaluate(
        self, analysis: Analysis, context: AnalysisContext
    ) -> AnomalyResult | None:
        # Tüm metin için framing sonuçlarını al
        frames = context.get_cached(
            f"frames_{analysis.analysis_id}",
            lambda: context.framing_service.detect_frames(analysis.raw_text),
        )

        if not frames or len(frames) < 2:
            return None

        max_confidence = 0.0
        best_pair = None

        for i, frame1 in enumerate(frames):
            for frame2 in frames[i + 1 :]:
                f1_type = frame1.get("frame_type", "")
                f2_type = frame2.get("frame_type", "")
                f1_conf = frame1.get("confidence", 0.0)
                f2_conf = frame2.get("confidence", 0.0)

                if (
                    f1_conf < self._config.min_frame_confidence
                    or f2_conf < self._config.min_frame_confidence
                ):
                    continue

                # Matris üzerinden çelişkiyi kontrol et
                contradiction = self._config.contradiction_matrix.get(
                    (f1_type, f2_type)
                )
                if contradiction is None:
                    contradiction = self._config.contradiction_matrix.get(
                        (f2_type, f1_type)
                    )

                if contradiction:
                    confidence = contradiction * min(f1_conf, f2_conf)
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_pair = (f1_type, f2_type, contradiction, f1_conf, f2_conf)

        if not best_pair:
            return None

        return AnomalyResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            severity=self.severity,
            confidence_score=max_confidence,
            description=f"Çelişkili çerçeveler tespit edildi: {best_pair[0]} vs {best_pair[1]}.",
            affected_segments=[
                SegmentRef(
                    segment_id=(
                        analysis.transcript.segments[0].segment_id
                        if analysis.transcript.segments
                        else "unknown"
                    ),
                    start_time=(
                        analysis.transcript.segments[0].start_time
                        if analysis.transcript.segments
                        else 0.0
                    ),
                    end_time=(
                        analysis.transcript.segments[-1].end_time
                        if analysis.transcript.segments
                        else 0.0
                    ),
                )
            ],
            metadata={
                "frame1": best_pair[0],
                "frame2": best_pair[1],
                "contradiction_score": best_pair[2],
                "frame1_confidence": best_pair[3],
                "frame2_confidence": best_pair[4],
            },
        )
