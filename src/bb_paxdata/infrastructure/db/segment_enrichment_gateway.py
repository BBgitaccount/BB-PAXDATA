from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from bb_paxdata.infrastructure.db.models import Segment, Sentence


@dataclass
class EnrichedSegmentData:
    """Segment ORM nesnesine yazılacak zenginleştirilmiş alanlar."""

    bloc: Optional[str]
    role: Optional[str]
    key_phrases: Optional[str]
    tfidf_keywords: Optional[str]
    entities_gpe: List[str]
    entities_org: List[str]
    entities_person: List[str]
    risk_signals: List[Dict[str, Any]]
    demand_concentration: Dict[str, int]
    inconsistency_score: float
    dominant_frame: Optional[str]


class SegmentEnrichmentGateway:
    def __init__(self, segment_service: Any = None, lodp_service: Any = None):
        self._segment_svc = segment_service
        self._lodp_svc = lodp_service

    def enrich(
        self,
        db_segment: Segment,
        db_sentences: List[Sentence],
        pipeline_res: Any = None,
        topic_result: Any = None,
    ) -> EnrichedSegmentData:
        """Tüm segment zenginleştirme mantığını tek bir kapıdan (gateway) koordine eder."""

        # 1. Konuşmacı Bilgileri Rollup (bloc, role)
        speaker_bloc = db_segment.speaker.bloc if db_segment.speaker else None
        speaker_role = db_segment.speaker.role if db_segment.speaker else None

        # 2. LODP / key_phrases Çıkarımı
        key_phrases = None
        if self._lodp_svc and hasattr(self._lodp_svc, "extract_for_sentences"):
            key_phrases = self._lodp_svc.extract_for_sentences(db_sentences)

        # 3. c-TF-IDF Konu Modelleme Kelimeleri
        tfidf_keywords = None
        if topic_result and hasattr(topic_result, "top_terms"):
            tfidf_keywords = ",".join(topic_result.top_terms)
        elif (
            pipeline_res and hasattr(pipeline_res, "analysis") and pipeline_res.analysis
        ):
            ts = getattr(pipeline_res.analysis, "topic_synthesis", None)
            if ts and getattr(ts, "topic_keywords", None):
                if isinstance(ts.topic_keywords, dict):
                    tfidf_keywords = ",".join(list(ts.topic_keywords.keys())[:5])
                elif isinstance(ts.topic_keywords, list):
                    tfidf_keywords = ",".join(ts.topic_keywords[:5])

        # 4. NER Varlık Aggregation (GPE, ORG, PERSON)
        entities = self._aggregate_entities(db_sentences)

        # 5. Cümle Seviyesinden Risk Sinyalleri Birleştirmesi
        risk_signals = []
        for sent in db_sentences:
            if sent.risk_signals:
                if isinstance(sent.risk_signals, list):
                    risk_signals.extend(sent.risk_signals)
                elif isinstance(sent.risk_signals, dict):
                    risk_signals.append(sent.risk_signals)

        # 6. Demand Concentration
        demand_conc = self._calculate_demand_concentration(db_sentences)

        # 7. Inconsistency Score Ortalama Hesaplama
        inconsistency = self._calculate_inconsistency(db_sentences)

        # 8. Dominant Frame Belirleme
        dominant_frame = self._resolve_dominant_frame(db_sentences, pipeline_res)

        return EnrichedSegmentData(
            bloc=speaker_bloc,
            role=speaker_role,
            key_phrases=key_phrases,
            tfidf_keywords=tfidf_keywords,
            entities_gpe=entities["GPE"],
            entities_org=entities["ORG"],
            entities_person=entities["PERSON"],
            risk_signals=risk_signals,
            demand_concentration=demand_conc,
            inconsistency_score=inconsistency,
            dominant_frame=dominant_frame,
        )

    def _aggregate_entities(self, sentences: List[Sentence]) -> Dict[str, List[str]]:
        gpe, org, person = set(), set(), set()
        for sent in sentences:
            if sent.entities_gpe:
                if isinstance(sent.entities_gpe, list):
                    gpe.update(sent.entities_gpe)
                else:
                    gpe.add(str(sent.entities_gpe))
            if hasattr(sent, "entities_org") and sent.entities_org:
                if isinstance(sent.entities_org, list):
                    org.update(sent.entities_org)
                else:
                    org.add(str(sent.entities_org))
            if sent.entities_person:
                if isinstance(sent.entities_person, list):
                    person.update(sent.entities_person)
                else:
                    person.add(str(sent.entities_person))
        return {
            "GPE": sorted(list(gpe)),
            "ORG": sorted(list(org)),
            "PERSON": sorted(list(person)),
        }

    def _resolve_dominant_frame(
        self, sentences: List[Sentence], pipeline_res: Any
    ) -> Optional[str]:
        # Öncelik: AI Sonucu (frame_salience)
        if pipeline_res and hasattr(pipeline_res, "analysis") and pipeline_res.analysis:
            fs = getattr(pipeline_res.analysis, "frame_salience", None)
            if fs and getattr(fs, "dominant_frame", None) and fs.dominant_frame:
                if hasattr(fs.dominant_frame, "value"):
                    return fs.dominant_frame.value
                return str(fs.dominant_frame)

        # Fallback: Cümlelerin kural bazlı mod değeri
        frames = [s.dominant_frame for s in sentences if s.dominant_frame]
        if frames:
            return max(set(frames), key=frames.count)
        return None

    def _calculate_inconsistency(self, sentences: List[Sentence]) -> float:
        scores = []
        for s in sentences:
            val = getattr(s, "discrepancy_score", None) or getattr(
                s, "formula_inconsistency_score", 0.0
            )
            scores.append(float(val))
        return sum(scores) / len(scores) if scores else 0.0

    def _calculate_demand_concentration(
        self, sentences: List[Sentence]
    ) -> Dict[str, int]:
        n = len(sentences)
        if n == 0:
            return {"intro": 0, "develop": 0, "concl": 0}

        intro_end = max(1, n // 5)
        concl_start = max(n - intro_end, intro_end + 1)

        intro_demands = sum(
            1 for s in sentences[:intro_end] if s.demand_type is not None
        )
        concl_demands = sum(
            1 for s in sentences[concl_start:] if s.demand_type is not None
        )
        develop_demands = sum(
            1 for s in sentences[intro_end:concl_start] if s.demand_type is not None
        )

        return {
            "intro": intro_demands,
            "develop": develop_demands,
            "concl": concl_demands,
        }
