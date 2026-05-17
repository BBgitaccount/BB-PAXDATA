from bb_paxdata.anomaly.rules.tone_drift import ToneDriftRule

from .base import BaseAnomalyTest


class TestToneDriftRule(BaseAnomalyTest):
    def test_tone_drift_detected(self):
        # 2σ sapması olan veriler (Çok fazla stabil nokta + bir sapma)
        sentences_data = [{"text": "Nötr", "score": 0.0}] * 10
        sentences_data.append({"text": "Sapma", "score": 1.0})
        analysis = self.create_mock_analysis(sentences_data)
        rule = ToneDriftRule()

        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "RULE_TONE_DRIFT")
        self.assertGreater(result.confidence_score, 0.5)

    def test_no_drift_when_stable(self):
        sentences_data = [
            {"text": "Mutlu cümle 1", "score": 0.5},
            {"text": "Mutlu cümle 2", "score": 0.5},
            {"text": "Mutlu cümle 3", "score": 0.5},
        ]
        analysis = self.create_mock_analysis(sentences_data)
        rule = ToneDriftRule()

        result = rule.evaluate(analysis, self.context)

        self.assertIsNone(result)
