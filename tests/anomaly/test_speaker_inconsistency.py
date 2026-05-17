from bb_paxdata.anomaly.rules.speaker_inconsistency import SpeakerInconsistencyRule

from .base import BaseAnomalyTest


class TestSpeakerInconsistencyRule(BaseAnomalyTest):
    def test_inconsistency_detected(self):
        analysis = self.create_mock_analysis(
            [{"text": "konuşma", "score": 0.0, "speaker": "spk1"}]
        )
        analysis.metadata["sbi_score"] = 0.9

        # Geçmişte hep düşük riskli (ortalama 0.1)
        self.mock_speaker.get_historical_sbi.return_value = [
            0.1,
            0.12,
            0.08,
            0.11,
            0.09,
        ]

        rule = SpeakerInconsistencyRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata["speaker_id"], "spk1")

    def test_no_anomaly_when_consistent(self):
        analysis = self.create_mock_analysis(
            [{"text": "konuşma", "score": 0.0, "speaker": "spk1"}]
        )
        analysis.metadata["sbi_score"] = 0.1
        self.mock_speaker.get_historical_sbi.return_value = [
            0.1,
            0.12,
            0.08,
            0.11,
            0.09,
        ]

        rule = SpeakerInconsistencyRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
