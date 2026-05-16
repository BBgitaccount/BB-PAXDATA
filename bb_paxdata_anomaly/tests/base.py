import unittest
from unittest.mock import MagicMock

from bb_paxdata_anomaly.core.context import AnalysisContext
from bb_paxdata_anomaly.core.models import Analysis, Segment, Sentence, Transcript


class BaseAnomalyTest(unittest.TestCase):
    def setUp(self):
        self.mock_ner = MagicMock()
        self.mock_risk = MagicMock()
        self.mock_hedging = MagicMock()
        self.mock_framing = MagicMock()
        self.mock_speaker = MagicMock()
        self.mock_dependency = MagicMock()
        self.mock_recovery = MagicMock()
        self.mock_spacy = MagicMock()
        self.mock_svo = MagicMock()

        self.context = AnalysisContext(
            ner_service=self.mock_ner,
            risk_service=self.mock_risk,
            hedging_service=self.mock_hedging,
            framing_service=self.mock_framing,
            speaker_service=self.mock_speaker,
            dependency_service=self.mock_dependency,
            recovery_engine=self.mock_recovery,
            spacy_pipeline=self.mock_spacy,
            svo_extractor=self.mock_svo,
        )

    def create_mock_analysis(self, sentences_data, gaps=None):
        sentences = [
            Sentence(
                text=s["text"],
                sentiment_score=s["score"],
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                speaker_id=s.get("speaker", "spk1"),
            )
            for i, s in enumerate(sentences_data)
        ]

        segment = Segment(
            segment_id="seg1",
            sentences=tuple(sentences),
            start_time=0.0,
            end_time=len(sentences) * 10.0,
            speaker_id=sentences[0].speaker_id if sentences else None,
        )

        transcript = Transcript(
            segments=(segment,),
            total_duration=len(sentences) * 10.0,
            silence_gaps=gaps or [],
        )

        return Analysis(
            analysis_id="ana1",
            transcript=transcript,
            raw_text=" ".join(s["text"] for s in sentences_data),
        )
