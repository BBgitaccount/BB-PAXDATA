from bb_paxdata_anomaly.rules.translation_artifact import TranslationArtifactRule

from .base import BaseAnomalyTest


class TestTranslationArtifactRule(BaseAnomalyTest):
    def test_artifact_detected(self):
        analysis = self.create_mock_analysis(
            [{"text": "Bu bir test cümlesidir ve çok uzundur.", "score": 0.0}]
        )

        # Doğal dilden sapan POS dağılımı mock'la
        # Referans: NOUN: 0.25, VERB: 0.20...
        # Biz NOUN: 0.8, VERB: 0.05 gibi sapan bir şey döndürelim
        self.mock_spacy.get_pos_distribution.return_value = {"NOUN": 20, "VERB": 2}
        self.mock_spacy.get_pos_ngrams.side_effect = [
            ["NOUN", "NOUN", "VERB"],  # 1-gram: N=0.66, V=0.33
            [("NOUN", "NOUN"), ("NOUN", "VERB")],  # 2-gram
            [("NOUN", "NOUN", "NOUN"), ("NOUN", "NOUN", "VERB")],  # 3-gram
        ]

        rule = TranslationArtifactRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)

    def test_too_short_text_ignored(self):
        analysis = self.create_mock_analysis([{"text": "Kısa.", "score": 0.0}])
        self.mock_spacy.get_pos_distribution.return_value = {"NOUN": 1}
        rule = TranslationArtifactRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
