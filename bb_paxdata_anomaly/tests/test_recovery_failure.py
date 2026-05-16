from bb_paxdata_anomaly.rules.recovery_failure import RecoveryFailureRule

from .base import BaseAnomalyTest


class TestRecoveryFailureRule(BaseAnomalyTest):
    def test_failure_detected(self):
        analysis = self.create_mock_analysis([{"text": "corrupted data", "score": 0.0}])
        # Metadata'ya data_id ekle
        analysis.metadata["data_id"] = "data123"

        self.mock_recovery.get_recovery_log.return_value = {
            "levels_attempted": 6,
            "final_valid": False,
            "schema_compliant": False,
            "error_trace": ["Structural error in JSON"],
        }

        rule = RecoveryFailureRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.severity.name, "CRITICAL")
        self.assertGreater(result.confidence_score, 0.9)

    def test_no_anomaly_if_valid(self):
        analysis = self.create_mock_analysis([{"text": "good data", "score": 0.0}])
        analysis.metadata["data_id"] = "data124"

        self.mock_recovery.get_recovery_log.return_value = {
            "levels_attempted": 6,
            "final_valid": True,
            "schema_compliant": True,
        }

        rule = RecoveryFailureRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
