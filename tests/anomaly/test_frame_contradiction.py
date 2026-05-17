from bb_paxdata.anomaly.rules.frame_contradiction import FrameContradictionRule

from .base import BaseAnomalyTest


class TestFrameContradictionRule(BaseAnomalyTest):
    def test_contradiction_detected(self):
        analysis = self.create_mock_analysis(
            [{"text": "Barışçıl çözüm arıyoruz ama bombalayacağız.", "score": 0.0}]
        )

        self.mock_framing.detect_frames.return_value = [
            {"frame_type": "peaceful_problem", "confidence": 0.9},
            {"frame_type": "military_solution", "confidence": 0.8},
        ]

        rule = FrameContradictionRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "RULE_FRAME_CONTRADICTION")

    def test_no_contradiction_with_single_frame(self):
        analysis = self.create_mock_analysis([{"text": "Tek çerçeve.", "score": 0.0}])
        self.mock_framing.detect_frames.return_value = [
            {"frame_type": "peaceful_problem", "confidence": 0.9}
        ]
        rule = FrameContradictionRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
