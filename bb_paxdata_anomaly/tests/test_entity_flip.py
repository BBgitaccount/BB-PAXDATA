from bb_paxdata_anomaly.rules.entity_flip import EntityFlipRule

from .base import BaseAnomalyTest


class TestEntityFlipRule(BaseAnomalyTest):
    def test_entity_flip_detected(self):
        sentences_data = [
            {"text": "Türkiye harika bir ülke.", "score": 0.8},
            {"text": "Ekonomi konuşuluyor.", "score": 0.0},
            {"text": "Türkiye çok kötü durumda.", "score": -0.6},
        ]

        # NER mock: "Türkiye" (GPE) her iki cümlede de var
        self.mock_ner.extract_entities.side_effect = [
            [{"type": "GPE", "text": "Türkiye"}],
            [],
            [{"type": "GPE", "text": "Türkiye"}],
        ]

        analysis = self.create_mock_analysis(sentences_data)
        rule = EntityFlipRule()

        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "RULE_ENTITY_FLIP")
        self.assertIn("türkiye", result.metadata["entity"])

    def test_no_flip_for_different_entities(self):
        sentences_data = [
            {"text": "Ahmet iyi biri.", "score": 0.8},
            {"text": "Mehmet kötü biri.", "score": -0.8},
        ]
        self.mock_ner.extract_entities.side_effect = [
            [{"type": "PERSON", "text": "Ahmet"}],
            [{"type": "PERSON", "text": "Mehmet"}],
        ]
        analysis = self.create_mock_analysis(sentences_data)
        rule = EntityFlipRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
