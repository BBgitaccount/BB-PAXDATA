from unittest.mock import MagicMock

from bb_paxdata_anomaly.core.service import CrossAnomalyService
from bb_paxdata_anomaly.rules.tone_drift import ToneDriftRule

from .base import BaseAnomalyTest


class TestCrossAnomalyService(BaseAnomalyTest):
    def test_service_execution(self):
        service = CrossAnomalyService(max_workers=2)

        # Mock bir kural
        rule1 = MagicMock()
        rule1.rule_id = "RULE1"
        rule1.evaluate.return_value = MagicMock(confidence_score=0.8)

        rule2 = MagicMock()
        rule2.rule_id = "RULE2"
        rule2.evaluate.side_effect = Exception("Crash")

        service.register_rule(rule1)
        service.register_rule(rule2)

        analysis = self.create_mock_analysis([{"text": "test", "score": 0.0}])
        results = service.evaluate(analysis, self.context)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].confidence_score, 0.8)
        service.shutdown()

    def test_real_rule_integration(self):
        service = CrossAnomalyService()
        service.register_rule(ToneDriftRule())

        # Drift içeren analiz
        sentences_data = [{"text": str(i), "score": 0.0} for i in range(10)]
        sentences_data.append({"text": "outlier", "score": 1.0})
        analysis = self.create_mock_analysis(sentences_data)

        results = service.evaluate(analysis, self.context)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].rule_id, "RULE_TONE_DRIFT")
        service.shutdown()
