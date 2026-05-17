from bb_paxdata.anomaly.rules.modal_collapse import ModalCollapseRule

from .base import BaseAnomalyTest


class TestModalCollapseRule(BaseAnomalyTest):
    def test_collapse_detected(self):
        sentence_text = "Nükleer saldırı başlatmalıyız."
        analysis = self.create_mock_analysis([{"text": sentence_text, "score": -0.5}])

        self.mock_risk.calculate_risk.return_value = 0.95
        self.mock_hedging.detect_hedging.return_value = 0.0

        rule = ModalCollapseRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "RULE_MODAL_COLLAPSE")
        self.assertEqual(result.severity.name, "CRITICAL")

    def test_no_anomaly_with_hedging(self):
        sentence_text = "Belki nükleer saldırı düşünebiliriz."
        analysis = self.create_mock_analysis([{"text": sentence_text, "score": -0.5}])

        self.mock_risk.calculate_risk.return_value = 0.95
        self.mock_hedging.detect_hedging.return_value = 0.4

        rule = ModalCollapseRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
