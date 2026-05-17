from bb_paxdata.anomaly.core.models import Analysis, Segment, Sentence, Transcript
from bb_paxdata.anomaly.rules.overlapping_claim import OverlappingClaimRule

from .base import BaseAnomalyTest


class TestOverlappingClaimRule(BaseAnomalyTest):
    def test_conflict_detected(self):
        # İki farklı konuşmacı
        s1 = Sentence(
            text="A planı krize neden oldu.",
            sentiment_score=0.0,
            start_time=0.0,
            end_time=10.0,
            speaker_id="spk1",
        )
        s2 = Sentence(
            text="A planı krizi engelledi.",
            sentiment_score=0.0,
            start_time=10.0,
            end_time=20.0,
            speaker_id="spk2",
        )

        seg1 = Segment(
            segment_id="seg1",
            sentences=(s1,),
            start_time=0.0,
            end_time=10.0,
            speaker_id="spk1",
        )
        seg2 = Segment(
            segment_id="seg2",
            sentences=(s2,),
            start_time=10.0,
            end_time=20.0,
            speaker_id="spk2",
        )

        transcript = Transcript(
            segments=(seg1, seg2), total_duration=20.0, silence_gaps=[]
        )
        analysis = Analysis(analysis_id="ana1", transcript=transcript, raw_text="...")

        self.mock_svo.extract_svo_triples.side_effect = [
            [{"subject": "a planı", "verb": "neden ol", "object": "kriz"}],
            [{"subject": "a planı", "verb": "engelle", "object": "kriz"}],
        ]

        rule = OverlappingClaimRule()
        result = rule.evaluate(analysis, self.context)

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata["conflict_count"], 1)

    def test_no_conflict_with_same_claims(self):
        sentences = [
            {"text": "A neden oldu.", "score": 0.0, "speaker": "spk1"},
            {"text": "Evet A neden oldu.", "score": 0.0, "speaker": "spk2"},
        ]
        analysis = self.create_mock_analysis(sentences)
        self.mock_svo.extract_svo_triples.return_value = [
            {"subject": "a", "verb": "neden ol", "object": "kriz"}
        ]
        rule = OverlappingClaimRule()
        result = rule.evaluate(analysis, self.context)
        self.assertIsNone(result)
