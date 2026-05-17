from bb_paxdata.anomaly.core.models import Analysis, Segment, Sentence, Transcript
from bb_paxdata.anomaly.rules.temporal_gap import TemporalGapRule

from .base import BaseAnomalyTest


class TestTemporalGapRule(BaseAnomalyTest):
    def test_gap_with_unresolved_anaphora(self):
        # 60 saniyelik boşluk
        gaps = [(10.0, 70.0)]
        s1 = Sentence(text="Konu A", sentiment_score=0.0, start_time=0.0, end_time=10.0)
        s2 = Sentence(
            text="O önemli", sentiment_score=0.0, start_time=70.0, end_time=80.0
        )

        seg1 = Segment(
            segment_id="seg1", sentences=(s1,), start_time=0.0, end_time=10.0
        )
        seg2 = Segment(
            segment_id="seg2", sentences=(s2,), start_time=70.0, end_time=80.0
        )

        transcript = Transcript(
            segments=(seg1, seg2), total_duration=80.0, silence_gaps=gaps
        )
        analysis = Analysis(
            analysis_id="ana1", transcript=transcript, raw_text="Konu A. O önemli."
        )

        # Dependency mock: ikinci cümlede "it" (O) var ve anaphora olarak işaretlenmiş
        self.mock_dependency.extract_dependencies.return_value = [
            {"head": "Önemli", "dep": "it", "rel": "anaphora"}
        ]

        rule = TemporalGapRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.metadata["gap_duration"], 60.0)

    def test_no_anomaly_if_no_gap(self):
        analysis = self.create_mock_analysis([{"text": "test", "score": 0.0}])
        rule = TemporalGapRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
