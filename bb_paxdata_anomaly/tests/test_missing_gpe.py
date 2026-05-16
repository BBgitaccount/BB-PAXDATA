from bb_paxdata_anomaly.rules.missing_gpe import MissingGPERule

from .base import BaseAnomalyTest


class TestMissingGPERule(BaseAnomalyTest):
    def test_missing_gpe_detected(self):
        sentence = "Dün şehri bombaladılar."
        analysis = self.create_mock_analysis([{"text": sentence, "score": -0.8}])

        # Dependency: "bombala" (head) -> "şehir" (obj)
        self.mock_dependency.extract_dependencies.return_value = [
            {"head": "bombala", "dep": "şehir", "rel": "obj"}
        ]
        # NER: GPE yok
        self.mock_ner.extract_entities.return_value = []

        rule = MissingGPERule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata["verb"], "bombala")

    def test_no_anomaly_when_gpe_present(self):
        sentence = "Kiev'i bombaladılar."
        analysis = self.create_mock_analysis([{"text": sentence, "score": -0.8}])
        self.mock_dependency.extract_dependencies.return_value = [
            {"head": "bombala", "dep": "kiev", "rel": "obj"}
        ]
        self.mock_ner.extract_entities.return_value = [{"type": "GPE", "text": "Kiev"}]

        rule = MissingGPERule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
