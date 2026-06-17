"""Service for triggering analysis on parsed segments."""

import re
from collections import Counter
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, select

from bb_paxdata.application.domain.services.risk_service import RiskService
from bb_paxdata.application.domain.utils.hash import generate_sentence_code

if TYPE_CHECKING:
    from bb_paxdata.infrastructure.ai.fail_check import ValidationStatus
    from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
    from bb_paxdata.infrastructure.db.models import (
        AIFailAnalysis,
        AISentenceAnalysis,
        DemandRecord,
        File,
        FileDynamics,
        FormulaValidationLog,
        PatternRecord,
        Segment,
        Sentence,
        SpeakerProfile,
        Word,
    )
    from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
    from bb_paxdata.infrastructure.db.segment_enrichment_gateway import (
        SegmentEnrichmentGateway,
    )
    from bb_paxdata.infrastructure.logic.formula_auditor import FormulaAuditor


def _infra_import(module: str, name: str) -> Any:
    """Dynamically import a class/function/object from infrastructure to decouple domain."""
    import importlib

    mod = importlib.import_module(module)
    return getattr(mod, name)


ValidationStatus = _infra_import(
    "bb_paxdata.infrastructure.ai.fail_check", "ValidationStatus"
)
HumanReviewQueue = _infra_import(
    "bb_paxdata.infrastructure.db.human_review_queue", "HumanReviewQueue"
)
AnalysisRepository = _infra_import(
    "bb_paxdata.infrastructure.db.repositories.analysis", "AnalysisRepository"
)
SegmentEnrichmentGateway = _infra_import(
    "bb_paxdata.infrastructure.db.segment_enrichment_gateway",
    "SegmentEnrichmentGateway",
)
FormulaAuditor = _infra_import(
    "bb_paxdata.infrastructure.logic.formula_auditor", "FormulaAuditor"
)

AIFailAnalysis = _infra_import("bb_paxdata.infrastructure.db.models", "AIFailAnalysis")
AISentenceAnalysis = _infra_import(
    "bb_paxdata.infrastructure.db.models", "AISentenceAnalysis"
)
DemandRecord = _infra_import("bb_paxdata.infrastructure.db.models", "DemandRecord")
File = _infra_import("bb_paxdata.infrastructure.db.models", "File")
FileDynamics = _infra_import("bb_paxdata.infrastructure.db.models", "FileDynamics")
FormulaValidationLog = _infra_import(
    "bb_paxdata.infrastructure.db.models", "FormulaValidationLog"
)
PatternRecord = _infra_import("bb_paxdata.infrastructure.db.models", "PatternRecord")
Segment = _infra_import("bb_paxdata.infrastructure.db.models", "Segment")
Sentence = _infra_import("bb_paxdata.infrastructure.db.models", "Sentence")
SpeakerProfile = _infra_import("bb_paxdata.infrastructure.db.models", "SpeakerProfile")
Word = _infra_import("bb_paxdata.infrastructure.db.models", "Word")

BLOC_MAP = _infra_import("bb_paxdata.infrastructure.text.file_io_handler", "BLOC_MAP")
POWER_LEVELS = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "POWER_LEVELS"
)
SPEAKER_MAP = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "SPEAKER_MAP"
)
_classify_demand_category = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "_classify_demand_category"
)
_extract_target_entity = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "_extract_target_entity"
)
classify_pattern_subtype = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "classify_pattern_subtype"
)
match_keyword_with_boundaries = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "match_keyword_with_boundaries"
)
power_to_tier = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "power_to_tier"
)
turkish_lower = _infra_import(
    "bb_paxdata.infrastructure.text.file_io_handler", "turkish_lower"
)
utc_now = _infra_import("bb_paxdata.infrastructure.text.file_io_handler", "utc_now")

logger = structlog.get_logger(__name__)


class AnalysisTriggerService:
    def __init__(self, session: Any, container: Any, pipeline: Any):
        self.session = session
        self.container = container
        self.pipeline = pipeline

    async def run_analysis(
        self,
        file_id: str,
        segments_data: list[Any],
        file_speakers_metadata: dict[str, Any],
    ) -> str:
        session = self.session
        container = self.container
        pipeline = self.pipeline

        # Fetch File from database to update aggregate stats at the end
        db_file_stmt = select(File).where(File.file_id == file_id)
        db_file_res = await session.execute(db_file_stmt)
        db_file = db_file_res.scalar_one_or_none()

        total_sentences_count = 0
        total_words_in_file = 0
        unique_speakers_in_file = set()
        unique_countries_in_file = set()
        all_processed_sentences: list[Sentence] = []
        all_processed_segments: list[Segment] = []

        last_risk = 0
        last_sentiment = 0.0
        last_topic = None
        last_kgi = 0.0

        from bb_paxdata.application.domain.services.sentiment_service import (
            SentimentService,
        )

        sentiment_svc = SentimentService()

        for seg_idx, seg in enumerate(segments_data, 1):
            speaker_name = seg["speaker"]
            speaker_id = speaker_name.lower().replace(" ", "_")
            unique_speakers_in_file.add(speaker_id)

            # Get or create speaker profile
            speaker_stmt = select(SpeakerProfile).where(
                SpeakerProfile.speaker_id == speaker_id
            )
            res = await session.execute(speaker_stmt)
            db_speaker = res.scalar_one_or_none()
            country = seg["country"]
            unique_countries_in_file.add(country)

            file_speaker_info = file_speakers_metadata.get(speaker_name.lower())

            if not db_speaker:
                if file_speaker_info:
                    sp_country = file_speaker_info["country"]
                    sp_power = file_speaker_info["power_level"]
                    sp_info = SPEAKER_MAP.get(speaker_name)
                    if not sp_info:
                        for name, info in SPEAKER_MAP.items():
                            if name.lower() == speaker_name.lower():
                                sp_info = info
                                break
                    if sp_info:
                        _, sp_title, sp_role = sp_info
                    else:
                        sp_title = "Participant"
                        sp_role = "panelist"
                        for r, p in POWER_LEVELS.items():
                            if p == sp_power:
                                sp_role = r
                                sp_title = r.replace("_", " ").title()
                                break
                    sp_bloc = BLOC_MAP.get(sp_country, "unknown")
                    sp_tier = power_to_tier(sp_power)
                else:
                    sp_info = SPEAKER_MAP.get(speaker_name)
                    if not sp_info:
                        for name, info in SPEAKER_MAP.items():
                            if name.lower() == speaker_name.lower():
                                sp_info = info
                                break

                    if sp_info:
                        sp_country, sp_title, sp_role = sp_info
                        sp_bloc = BLOC_MAP.get(sp_country, "unknown")
                        sp_power = POWER_LEVELS.get(sp_role, 3)
                        sp_tier = power_to_tier(sp_power)
                    else:
                        sp_country = country
                        sp_title = "Participant"
                        sp_role = "panelist"
                        sp_bloc = (
                            BLOC_MAP.get(sp_country, "unknown")
                            if sp_country != "unknown"
                            else "unknown"
                        )
                        sp_power = 3
                        sp_tier = "TIER4_EXPERT"

                db_speaker = SpeakerProfile(
                    speaker_id=speaker_id,
                    full_name=speaker_name,
                    country=sp_country,
                    title=sp_title,
                    role=sp_role,
                    bloc=sp_bloc,
                    power_level=sp_power,
                    influence_tier=sp_tier,
                )
                session.add(db_speaker)
                await session.flush()
            else:
                changed = False
                if file_speaker_info:
                    file_power = file_speaker_info["power_level"]
                    file_country = file_speaker_info["country"]
                    if db_speaker.power_level != file_power:
                        db_speaker.power_level = file_power
                        db_speaker.influence_tier = power_to_tier(file_power)
                        changed = True
                    if file_country not in {db_speaker.country, "unknown"}:
                        db_speaker.country = file_country
                        db_speaker.bloc = BLOC_MAP.get(file_country, "unknown")
                        changed = True
                elif db_speaker.country == "unknown" and country != "unknown":
                    db_speaker.country = country
                    db_speaker.bloc = BLOC_MAP.get(country, "unknown")
                    changed = True
                if changed:
                    await session.flush()

            db_segment = Segment(
                seg_id=f"seg_{file_id}_{seg_idx}",
                file_id=file_id,
                speaker_id=speaker_id,
                speaker=db_speaker,
                speaker_name=speaker_name,
                country=country,
                power_level=db_speaker.power_level if db_speaker else 5,
                seq_order=seg_idx,
                text=" ".join(seg["sentences"]),
            )
            session.add(db_segment)
            await session.flush()
            all_processed_segments.append(db_segment)

            pipeline_res = None
            db_sentences_in_seg = []
            db_patterns_in_seg = []

            for sent_idx, sentence_text in enumerate(seg["sentences"], 1):
                total_sentences_count += 1
                sent_id = f"sent_{file_id}_{total_sentences_count}"
                sent_code = generate_sentence_code()

                # Cümle bazlı AI limit takibi (LimitedAIAnalyst aktifse)
                ai_analyst = getattr(pipeline, "ai_analyst", None) or getattr(
                    getattr(pipeline, "collect_stage", None), "_ai_analyst", None
                )
                if ai_analyst is not None:
                    begin_fn = getattr(ai_analyst, "begin_sentence", None)
                    if begin_fn is not None:
                        begin_fn()

                # Run Pipeline
                pipeline_res = await pipeline.run(
                    text=sentence_text,
                    file_id=file_id,
                    speaker_country=country,
                    speaker_power_level=float(
                        db_speaker.power_level if db_speaker else 5
                    )
                    / 10.0,
                    metadata={
                        "file_id": file_id,
                        "speaker_id": speaker_id,
                        "speaker_country": country,
                        "id": sent_id,
                        "sentence_code": sent_code,
                    },
                    session=session,
                    speaker_id=speaker_id,
                    sentence_index=total_sentences_count,
                )

                words_count = (
                    len(pipeline_res.analysis.tokens)
                    if pipeline_res.analysis.tokens
                    else 0
                )
                total_words_in_file += words_count

                # ── NLP Metrikleri: negation_aware_diplo, hedging_score, politeness_ratio ──
                _diplo_compound = sentiment_svc.diplo_sentiment(sentence_text)
                _negation_cues = pipeline_res.analysis.negation_cues or ()
                _neg_count = len(list(_negation_cues))
                _ai_sent = pipeline_res.analysis.ai_sentiment_score or 0.0
                # negation_aware_diplo: negasyon cue sayısına göre duygu skorunu atenüe et
                if _neg_count > 0:
                    _negation_aware_diplo = _ai_sent * (0.8**_neg_count)
                else:
                    _negation_aware_diplo = _ai_sent

                # hedging_score: AI hedging yoksa risk_signals'dan tahmin et
                _risk_sigs = pipeline_res.analysis.risk_signals or ()
                _hedging_keywords = sum(
                    1
                    for kw in (
                        "perhaps",
                        "maybe",
                        "might",
                        "could",
                        "possibly",
                        "belki",
                        "muhtemelen",
                        "olabilir",
                        "sanırım",
                    )
                    if kw in sentence_text.lower()
                )
                _hedging_score = (
                    min(1.0, _hedging_keywords * 0.25) if _hedging_keywords else 0.0
                )

                # politeness_ratio: face_save / (face_save + face_threat + 1)
                _face_save = sum(
                    1
                    for k in [
                        "please",
                        "lütfen",
                        "thank",
                        "teşekkür",
                        "respectfully",
                        "saygıyla",
                    ]
                    if k in sentence_text.lower()
                )
                _face_threat = sum(
                    1
                    for k in [
                        "demand",
                        "threat",
                        "ultimatum",
                        "warn",
                        "tehdit",
                        "talep",
                    ]
                    if k in sentence_text.lower()
                )
                _politeness_ratio = _face_save / (_face_save + _face_threat + 1)

                # ── Risk score normalizasyonu: float 0-1 -> int 0-10 ──
                _raw_risk = pipeline_res.analysis.ai_risk_score or 0.0
                _normalized_risk = round(_raw_risk * 10)
                _normalized_risk = max(0, min(10, _normalized_risk))

                # ── Logic result ──
                _logic_result = (
                    "FAIL"
                    if (
                        pipeline_res.analysis.anomaly_flags
                        and len(pipeline_res.analysis.anomaly_flags) > 0
                    )
                    else "PASS"
                )

                # ── Extract entities (GPE + Person + Org) from NER results ──
                _entities_gpe = []
                _entities_person = []
                _entities_org = []
                for _ent in pipeline_res.analysis.entities or []:
                    _ent_label = (
                        _ent.get("label") or _ent.get("entity_group") or ""
                    ).upper()
                    _ent_text = _ent.get("text", "").strip()
                    if _ent_text:
                        if _ent_label in ("GPE", "LOC", "LOCATION"):
                            _entities_gpe.append(_ent_text)
                        elif _ent_label in ("PER", "PERSON"):
                            _entities_person.append(_ent_text)
                        elif _ent_label in ("ORG", "ORGANIZATION"):
                            _entities_org.append(_ent_text)

                # ── Serialize risk signals to JSON-friendly list ──
                _risk_signals_json = []
                for _rs in _risk_sigs:
                    _risk_signals_json.append(
                        {
                            "signal_text": _rs.signal_text,
                            "signal_start": _rs.signal_start,
                            "signal_end": _rs.signal_end,
                            "signal_type": (
                                _rs.signal_type.value
                                if hasattr(_rs.signal_type, "value")
                                else str(_rs.signal_type)
                            ),
                            "escalation_multiplier": _rs.escalation_multiplier,
                            "credibility_score": _rs.credibility_score,
                            "sentence_id": _rs.sentence_id,
                        }
                    )

                # ── Evidence types, Appraisal attitude, Audience type ──
                # FramingService: Martin & White (2005) Appraisal, Entman (1993) Evidence
                from bb_paxdata.application.domain.models.sentence import (
                    Sentence as SentenceDomainModel,
                )
                from bb_paxdata.application.domain.services.framing_service import (
                    FramingService,
                )

                _framing_svc = FramingService()
                _framing_sentence = SentenceDomainModel(id=sent_id, text=sentence_text)
                _frame_result = _framing_svc.detect_frame(_framing_sentence)

                _evidence_types = [
                    (et.value if hasattr(et, "value") else str(et))
                    for et in _frame_result.evidence_types
                    if str(et) != "none"
                ] or None

                _appraisal_attitude = (
                    _frame_result.appraisal_attitude.value
                    if hasattr(_frame_result.appraisal_attitude, "value")
                    else str(_frame_result.appraisal_attitude)
                )
                _audience_type = (
                    _frame_result.audience_type.value
                    if hasattr(_frame_result.audience_type, "value")
                    else str(_frame_result.audience_type)
                )

                db_sentence = Sentence(
                    sent_id=sent_id,
                    sentence_code=sent_code,
                    seg_id=db_segment.seg_id,
                    file_id=file_id,
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    country=country,
                    bloc=db_speaker.bloc,
                    role=db_speaker.role,
                    power_level=db_speaker.power_level,
                    sent_order=sent_idx,
                    global_sent_order=total_sentences_count,
                    text=sentence_text,
                    word_count=words_count,
                    char_count=len(sentence_text),
                    vader_compound=_ai_sent,
                    diplo_compound=_diplo_compound,
                    emotion_category=pipeline_res.analysis.ai_sentiment_label,
                    dominant_topic=(
                        pipeline_res.analysis.topic_synthesis.topic_label
                        if (
                            pipeline_res.analysis.topic_synthesis
                            and pipeline_res.analysis.topic_synthesis.topic_label
                        )
                        else None
                    ),
                    topic_scores=(
                        pipeline_res.analysis.topic_synthesis.topic_scores
                        if (
                            pipeline_res.analysis.topic_synthesis
                            and pipeline_res.analysis.topic_synthesis.topic_scores
                        )
                        else None
                    ),
                    risk_score=_normalized_risk,
                    risk_signals=_risk_signals_json if _risk_signals_json else None,
                    entities_gpe=_entities_gpe if _entities_gpe else None,
                    entities_person=_entities_person if _entities_person else None,
                    entities_org=_entities_org if _entities_org else None,
                    dominant_frame=(
                        _frame_result.frame_type.value
                        if (_frame_result and _frame_result.frame_type)
                        else (
                            pipeline_res.analysis.frame_salience.dominant_frame.value
                            if (
                                pipeline_res.analysis.frame_salience
                                and pipeline_res.analysis.frame_salience.dominant_frame
                            )
                            else None
                        )
                    ),
                    influence_tier=db_speaker.influence_tier,
                    evidence_types=_evidence_types,
                    appraisal_attitude=_appraisal_attitude,
                    audience_type=_audience_type,
                    negation_aware_diplo=_negation_aware_diplo,
                    hedging_score=_hedging_score,
                    politeness_ratio=_politeness_ratio,
                    face_threat_count=_face_threat,
                    face_save_count=_face_save,
                    ai_analyzed=1,
                    logic_result=_logic_result,
                )
                session.add(db_sentence)
                await session.flush()

                if pipeline_res.analysis.topic_synthesis:
                    ts = pipeline_res.analysis.topic_synthesis
                    TopicAssignmentRepository = _infra_import(
                        "bb_paxdata.infrastructure.db.repositories.topic_assignment_repository",
                        "TopicAssignmentRepository",
                    )

                    _topic_repo = TopicAssignmentRepository(session)
                    await _topic_repo.upsert(
                        segment_id=db_segment.seg_id,
                        analysis_id=sent_id,
                        synthesis=ts,
                        model_metadata={},
                    )

                db_sentences_in_seg.append(db_sentence)
                all_processed_sentences.append(db_sentence)

                # Save AISentenceAnalysis via repository to decouple domain layer
                analysis_repo = AnalysisRepository(session)

                pipeline_res.analysis.record_event(
                    event_type="AnalysisCompleted",
                    payload={
                        "sentiment_score": (_ai_sent if _ai_sent is not None else 0.0),
                        "sentiment_category": pipeline_res.analysis.ai_sentiment_label
                        or "",
                        "risk_score": _normalized_risk,
                        "hedging_score": _hedging_score,
                        "politeness_score": _politeness_ratio,
                        "logic_result": _logic_result,
                    },
                    actor_id="system",
                    aggregate_id=sent_id,
                )

                ai_analysis = await analysis_repo.save_sentence_analysis_with_metadata(
                    pipeline_res.analysis,
                    sent_id=sent_id,
                    file_id=file_id,
                    sentence_code=sent_code,
                    speaker_name=speaker_name,
                    country=country,
                    power_level=0,
                    global_sent_order=total_sentences_count,
                    sentiment_score=_ai_sent,
                    sentiment_category=pipeline_res.analysis.ai_sentiment_label,
                    risk_score=_normalized_risk,
                    ai_sentiment=pipeline_res.analysis.ai_sentiment_label,
                    ai_risk_score=_normalized_risk,
                    ai_frame_type=(
                        str(pipeline_res.analysis.framing)
                        if pipeline_res.analysis.framing
                        else None
                    ),
                    hedging_score=_hedging_score,
                    politeness_score=_politeness_ratio,
                    logic_result=_logic_result,
                )
                db_sentence.ai_analysis = ai_analysis

                # ── AI Fail Check & Human Review Flagging Entegrasyonu ──
                # Calculate temporal values BEFORE updating last variables
                risk_d = _normalized_risk - last_risk
                emotion_s = _ai_sent - last_sentiment
                topic_c = (
                    1
                    if (
                        pipeline_res.analysis.topic_synthesis
                        and pipeline_res.analysis.topic_synthesis.topic_label
                        != last_topic
                    )
                    else 0
                )
                kgi_score_sent = round(
                    min(10.0, max(0.0, last_kgi * 0.85 + _normalized_risk * 0.15)), 4
                )
                formula_incons = round(abs(emotion_s) * 0.6 + topic_c * 0.4, 4)
                db_sentence.formula_inconsistency_score = formula_incons
                db_sentence.discrepancy_score = 0.0

                # Update temporal state for next sentence
                last_risk = _normalized_risk
                last_sentiment = _ai_sent
                last_topic = (
                    pipeline_res.analysis.topic_synthesis.topic_label
                    if (
                        pipeline_res.analysis.topic_synthesis
                        and pipeline_res.analysis.topic_synthesis.topic_label
                    )
                    else None
                )
                last_kgi = kgi_score_sent

                if _logic_result == "FAIL":
                    # Compute formula risk score
                    detected_signals = [
                        sig
                        for sig in RiskService.RISK_SIGNALS
                        if sig in sentence_text.lower()
                    ]
                    formula_risk_score = min(
                        10.0,
                        sum(
                            RiskService.RISK_SIGNAL_WEIGHTS.get(sig, 1)
                            for sig in detected_signals
                        ),
                    )

                    # AI response dictionary for fail check
                    ai_resp_dict = {
                        "sentiment_score": float(
                            pipeline_res.analysis.ai_sentiment_score or 0.0
                        ),
                        "risk_score": float(pipeline_res.analysis.ai_risk_score or 0.0)
                        * 10.0,
                        "hedging_score": _hedging_score,
                        "manipulation_score": float(
                            pipeline_res.analysis.manipulation_score or 0.0
                        ),
                        "politeness_score": _politeness_ratio,
                        "dominant_topic": (
                            pipeline_res.analysis.topic_synthesis.topic_label
                            if (
                                pipeline_res.analysis.topic_synthesis
                                and pipeline_res.analysis.topic_synthesis.topic_label
                            )
                            else ""
                        ),
                        "frame_type": (
                            str(pipeline_res.analysis.framing)
                            if pipeline_res.analysis.framing
                            else ""
                        ),
                        "appraisal_attitude": getattr(
                            pipeline_res.analysis, "ai_appraisal_attitude", None
                        )
                        or "",
                        "audience_type": getattr(
                            pipeline_res.analysis, "ai_audience_type", None
                        )
                        or "",
                    }

                    # Formula response dictionary for fail check
                    formula_resp_dict = {
                        "sentiment_score": float(
                            pipeline_res.analysis.sentiment_score or 0.0
                        ),
                        "risk_score": formula_risk_score,
                        "hedging_score": _hedging_score,
                        "manipulation_score": _negation_aware_diplo,
                        "politeness_score": _politeness_ratio,
                        "dominant_topic": (
                            pipeline_res.analysis.topic_synthesis.topic_label
                            if (
                                pipeline_res.analysis.topic_synthesis
                                and pipeline_res.analysis.topic_synthesis.topic_label
                            )
                            else ""
                        ),
                        "frame_type": (
                            str(pipeline_res.analysis.framing)
                            if pipeline_res.analysis.framing
                            else ""
                        ),
                        "appraisal_attitude": "",
                        "audience_type": "",
                    }

                    # Run fail check validation
                    fail_checker = container.fail_check
                    fail_check_res = fail_checker.validate_ai_response(
                        ai_resp_dict, formula_resp_dict
                    )

                    failed_checks = [
                        r
                        for r in fail_check_res.validation_results
                        if r.status == ValidationStatus.FAIL
                    ]
                    if failed_checks:
                        db_sentence.discrepancy_score = max(
                            r.discrepancy or 0.0 for r in failed_checks
                        )

                    analysis_repo = AnalysisRepository(session)
                    for val_res in fail_check_res.validation_results:
                        if val_res.status == ValidationStatus.FAIL:
                            # Build row data for LLM linguistic analysis
                            row_data = {
                                "speaker_name": speaker_name,
                                "country": country,
                                "power_level": 0,
                                "file_id": file_id,
                                "check_type": (
                                    val_res.check_type.value
                                    if hasattr(val_res.check_type, "value")
                                    else str(val_res.check_type)
                                ),
                                "original_sentence": sentence_text,
                                "prev_sentence": (
                                    seg["sentences"][sent_idx - 2]
                                    if sent_idx >= 2
                                    else "[START]"
                                ),
                                "next_sentence": (
                                    seg["sentences"][sent_idx]
                                    if sent_idx < len(seg["sentences"])
                                    else "[END]"
                                ),
                                "formula_value": str(
                                    formula_resp_dict.get(
                                        val_res.check_type.name.lower()
                                    )
                                    if hasattr(val_res.check_type, "name")
                                    else ""
                                ),
                                "ai_value": str(
                                    ai_resp_dict.get(val_res.check_type.name.lower())
                                    if hasattr(val_res.check_type, "name")
                                    else ""
                                ),
                                "discrepancy_score": val_res.discrepancy or 0.0,
                                "kgi_score": kgi_score_sent,
                                "risk_delta": risk_d,
                                "emotion_shift": emotion_s,
                                "topic_shift": topic_c,
                                "formula_inconsistency": formula_incons,
                                "ai_risk_score": _normalized_risk,
                                "ai_manipulation_score": pipeline_res.analysis.manipulation_score
                                or 0.0,
                                "ai_hedging_score": _hedging_score,
                                "ai_tone": pipeline_res.analysis.ai_sentiment_label
                                or "neutral",
                                "ai_frame": (
                                    str(pipeline_res.analysis.framing)
                                    if pipeline_res.analysis.framing
                                    else "neutral"
                                ),
                                "anomaly_types": (
                                    ",".join(
                                        str(x)
                                        for x in pipeline_res.analysis.anomaly_flags
                                    )
                                    if pipeline_res.analysis.anomaly_flags
                                    else "none"
                                ),
                                "validation_explanation": val_res.explanation,
                                "context_note": "",
                            }

                            # Call LLM linguistic analysis
                            if container._logic_mode:
                                ling_res = None
                            else:
                                ling_res = (
                                    await fail_checker.analyze_fail_linguistically(
                                        row_data
                                    )
                                )

                            # Build AIFailAnalysis database model
                            db_fail = AIFailAnalysis(
                                sent_id=sent_id,
                                sentence_code=sent_code,
                                seg_id=db_segment.seg_id,
                                file_id=file_id,
                                speaker_name=speaker_name,
                                country=country,
                                power_level=0,
                                global_sent_order=total_sentences_count,
                                check_type=(
                                    val_res.check_type.value
                                    if hasattr(val_res.check_type, "value")
                                    else str(val_res.check_type)
                                ),
                                formula_value=row_data["formula_value"],
                                ai_value=row_data["ai_value"],
                                discrepancy_score=val_res.discrepancy,
                                original_sentence=sentence_text,
                                triplet_text=f"PREV: {row_data['prev_sentence']}\nCURR: {sentence_text}\nNEXT: {row_data['next_sentence']}",
                                prev_sentence=row_data["prev_sentence"],
                                next_sentence=row_data["next_sentence"],
                                kgi_score=kgi_score_sent,
                                risk_delta=risk_d,
                                emotion_shift=emotion_s,
                                topic_shift=topic_c,
                                formula_inconsistency_score=formula_incons,
                                ai_manipulation_score=row_data["ai_manipulation_score"],
                                ai_hedging_score=row_data["ai_hedging_score"],
                                ai_risk_score=_normalized_risk,
                                ai_sentiment_score=_ai_sent,
                                ai_tone=row_data["ai_tone"],
                                ai_frame=row_data["ai_frame"],
                                anomaly_types=row_data["anomaly_types"],
                                anomaly_count=(
                                    len(pipeline_res.analysis.anomaly_flags)
                                    if pipeline_res.analysis.anomaly_flags
                                    else 0
                                ),
                                processed_at=utc_now(),
                            )

                            if ling_res:
                                db_fail.fail_reason = ling_res.get("AI_Neden_Fail")
                                db_fail.fail_category = ling_res.get(
                                    "AI_Fail_Kategorisi"
                                )
                                db_fail.negation_type = ling_res.get("AI_Negasyon_Tipi")
                                db_fail.negation_scope = ling_res.get(
                                    "AI_Negasyon_Kapsami"
                                )
                                db_fail.contextual_factor = ling_res.get(
                                    "AI_Baglamsal_Faktor"
                                )
                                db_fail.temporal_factor = ling_res.get(
                                    "AI_Temporal_Faktor"
                                )
                                db_fail.formula_gap = ling_res.get("AI_Formul_Eksigi")
                                db_fail.ai_misperception = ling_res.get(
                                    "AI_AI_Yanilgisi"
                                )
                                db_fail.correction_suggestion = ling_res.get(
                                    "AI_Duzeltme_Onerisi"
                                )
                                db_fail.comparative_correction = ling_res.get(
                                    "AI_Karsilastirmali_Duzeltme"
                                )
                                db_fail.anomaly_link = ling_res.get(
                                    "AI_Anomali_Baglantisi"
                                )
                                db_fail.linguistic_marker = ling_res.get(
                                    "AI_Dilbilimsel_Marka"
                                )
                                db_fail.confidence_score = ling_res.get(
                                    "AI_Guven_Skoru"
                                )
                            else:
                                db_fail.fail_reason = val_res.explanation
                                db_fail.fail_category = "diger"

                            await analysis_repo.save_fail_analysis(db_fail)

                # ── Human Review Queue Flagging ──
                should_flag = False
                trigger_type = ""

                if _normalized_risk >= 7:
                    should_flag = True
                    trigger_type = "HIGH_RISK"
                elif _logic_result == "FAIL":
                    should_flag = True
                    trigger_type = "CRITICAL_ANOMALY"

                if should_flag:
                    _ai_json = "{}"
                    if pipeline_res.raw_ai:
                        try:
                            if hasattr(pipeline_res.raw_ai, "model_dump_json"):
                                _ai_json = pipeline_res.raw_ai.model_dump_json()
                            elif hasattr(pipeline_res.raw_ai, "json"):
                                _ai_json = pipeline_res.raw_ai.json()
                            else:
                                import json

                                _ai_json = json.dumps(pipeline_res.raw_ai)
                        except Exception:
                            _ai_json = "{}"
                    review_entry = HumanReviewQueue(
                        sent_id=sent_id,
                        seg_id=db_segment.seg_id,
                        file_id=file_id,
                        speaker_name=speaker_name,
                        country=country,
                        trigger_type=trigger_type,
                        ai_risk_score=_normalized_risk,
                        anomaly_types=db_sentence.rhetoric_type,
                        uncertainty_score=0.0,
                        status="PENDING",
                        original_ai_json=_ai_json,
                        flagged_at=utc_now().isoformat(),
                    )
                    session.add(review_entry)

                # ── Demand Records: talep içeren cümleler ──
                _demand_verbs = [
                    "demand",
                    "request",
                    "require",
                    "insist",
                    "urge",
                    "call for",
                    "talep",
                    "istemek",
                    "çağrı",
                    "gerekli",
                    "zorunlu",
                    "ısrar",
                    "must",
                    "should",
                    "need to",
                    "have to",
                    "shall",
                ]
                _sentence_lower = turkish_lower(sentence_text)
                _detected_demand_verb = next(
                    (v for v in _demand_verbs if v in _sentence_lower), None
                )
                if _detected_demand_verb:
                    _demand_cat = _classify_demand_category(_sentence_lower)
                    _target_ent = _extract_target_entity(
                        sentence_text,
                        pipeline_res.analysis.entities,
                        speaker_name,
                        country,
                    )
                    db_demand = DemandRecord(
                        sent_id=sent_id,
                        seg_id=db_segment.seg_id,
                        file_id=file_id,
                        speaker_name=speaker_name,
                        country=country,
                        power_level=db_speaker.power_level,
                        demand_verb=_detected_demand_verb,
                        demand_type=(
                            "explicit"
                            if _detected_demand_verb
                            in ("demand", "insist", "talep", "ısrar")
                            else "implicit"
                        ),
                        demand_weight=max(0.3, min(1.0, _normalized_risk / 10.0)),
                        demand_category=_demand_cat,
                        target_entity=_target_ent,
                        demand_topic=(
                            pipeline_res.analysis.topic_synthesis.topic_label
                            if pipeline_res.analysis.topic_synthesis
                            else None
                        ),
                        full_sentence=sentence_text,
                        diplo_compound=_negation_aware_diplo,
                    )
                    session.add(db_demand)
                    db_sentence.demand_category = _demand_cat
                    db_sentence.demand_type = db_demand.demand_type
                    db_sentence.demand_weight = db_demand.demand_weight

                # ── Pattern Records: retorik kalıplar ──
                _rhetoric_patterns = {
                    "conditional": [
                        "if",
                        "provided that",
                        "eğer",
                        "şayet",
                        "koşuluyla",
                    ],
                    "commitment": [
                        "we will",
                        "biz yapacağız",
                        "commit",
                        "taahhüt",
                        "pledge",
                    ],
                    "threat": [
                        "otherwise",
                        "consequences",
                        "aksi halde",
                        "sonuçları olur",
                    ],
                    "concession": [
                        "however",
                        "although",
                        "ancak",
                        "bununla birlikte",
                        "rağmen",
                    ],
                    "appeal": [
                        "we call upon",
                        "çağrıda bulunuyoruz",
                        "international community",
                        "uluslararası toplum",
                    ],
                }
                for _ptype, _pkeywords in _rhetoric_patterns.items():
                    _matched_kw = next(
                        (
                            kw
                            for kw in _pkeywords
                            if match_keyword_with_boundaries(kw, _sentence_lower)
                        ),
                        None,
                    )
                    if _matched_kw is not None:
                        _subtype = classify_pattern_subtype(_ptype, _matched_kw)
                        _prev_sent = (
                            seg["sentences"][sent_idx - 2]
                            if sent_idx >= 2
                            else "[START]"
                        )
                        _next_sent = (
                            seg["sentences"][sent_idx]
                            if sent_idx < len(seg["sentences"])
                            else "[END]"
                        )

                        _sent_cat = pipeline_res.analysis.ai_sentiment_label
                        if _sent_cat not in (
                            "cooperative",
                            "confrontational",
                            "concerned",
                            "neutral_cautious",
                            "constructive",
                            "neutral",
                        ):
                            _sent_cat = "unknown"

                        db_pattern = PatternRecord(
                            sent_id=sent_id,
                            seg_id=db_segment.seg_id,
                            file_id=file_id,
                            speaker_name=speaker_name,
                            country=country,
                            power_level=db_speaker.power_level,
                            pattern_type=_ptype,
                            pattern_subtype=_subtype,
                            pattern_text=_matched_kw,
                            matched_keyword=_matched_kw,
                            full_sentence=sentence_text,
                            prev_sentence=_prev_sent,
                            next_sentence=_next_sent,
                            dominant_topic=(
                                pipeline_res.analysis.topic_synthesis.topic_label
                                if pipeline_res.analysis.topic_synthesis
                                else None
                            ),
                            diplo_compound=_negation_aware_diplo,
                            risk_score=_normalized_risk,
                            sentiment_category=_sent_cat,
                        )
                        session.add(db_pattern)
                        db_patterns_in_seg.append(_ptype)
                        if not db_sentence.rhetoric_type:
                            db_sentence.rhetoric_type = _ptype
                        break  # İlk eşleşen kalıp yeterli

                # Populate words table
                if pipeline_res.analysis.tokens:
                    STOP_WORDS = frozenset(
                        {
                            "the",
                            "a",
                            "an",
                            "and",
                            "or",
                            "but",
                            "in",
                            "on",
                            "at",
                            "to",
                            "for",
                            "with",
                            "by",
                            "of",
                            "ve",
                            "veya",
                            "ama",
                            "fakat",
                            "lakin",
                            "ile",
                            "için",
                            "ise",
                            "da",
                            "de",
                            "ki",
                            "en",
                            "daha",
                            "bir",
                            "bu",
                            "şu",
                            "o",
                            "ne",
                            "her",
                            "hep",
                            "hiç",
                        }
                    )
                    # Determine language and lexicons/stopwords
                    lang = (pipeline_res.analysis.language or "en").lower()
                    if lang == "tr":
                        from bb_paxdata.application.domain.lexicon.tr_diplo_lexicon import (
                            DIPLO_LEXICON_TR,
                        )
                        from bb_paxdata.application.domain.lexicon.tr_stopwords import (
                            STOPWORDS_TR,
                        )

                        lexicon = DIPLO_LEXICON_TR
                        stop_words = STOPWORDS_TR
                    else:
                        from bb_paxdata.application.domain.services.sentiment_service import (
                            SentimentService,
                        )

                        lexicon = SentimentService.DIPLO_LEXICON
                        stop_words = STOP_WORDS

                    named_entity_words = set()
                    for ent in getattr(pipeline_res.analysis, "entities", []):
                        ent_text = ent.get("text", "")
                        for word in ent_text.split():
                            named_entity_words.add(word.lower().strip(",.!?;:()\"'"))

                    for w_idx, token in enumerate(pipeline_res.analysis.tokens):
                        # Clean trailing/leading punctuation
                        token_clean = token.strip(",.!?;:()\"'")
                        token_lower = token_clean.lower()

                        # Skip if token is purely composed of punctuation
                        if not token_lower:
                            continue

                        # Diplo skoru hesapla
                        w_score = lexicon.get(token_lower, 0.0)
                        if w_score == 0.0:
                            # Fallback: check other lexicon if primary is 0.0
                            if lang == "tr":
                                from bb_paxdata.application.domain.services.sentiment_service import (
                                    SentimentService,
                                )

                                w_score = SentimentService.DIPLO_LEXICON.get(
                                    token_lower, 0.0
                                )
                            else:
                                from bb_paxdata.application.domain.lexicon.tr_diplo_lexicon import (
                                    DIPLO_LEXICON_TR,
                                )

                                w_score = DIPLO_LEXICON_TR.get(token_lower, 0.0)

                        is_ne = token_lower in named_entity_words

                        db_word = Word(
                            sent_id=sent_id,
                            seg_id=db_segment.seg_id,
                            file_id=file_id,
                            speaker_id=speaker_id,
                            speaker_name=speaker_name,
                            country=country,
                            bloc=db_speaker.bloc,
                            power_level=db_speaker.power_level,
                            word_raw=token_clean,
                            word_norm=token_lower,
                            word_position=w_idx,
                            is_stopword=token_lower in stop_words,
                            diplo_score=w_score,
                            is_named_entity=is_ne,
                        )
                        session.add(db_word)

            # Aggregate Segment fields in memory
            vaders = [
                s.vader_compound
                for s in db_sentences_in_seg
                if s.vader_compound is not None
            ]
            db_segment.vader_compound = sum(vaders) / len(vaders) if vaders else 0.0

            diplos = [
                s.diplo_compound
                for s in db_sentences_in_seg
                if s.diplo_compound is not None
            ]
            db_segment.diplo_compound = sum(diplos) / len(diplos) if diplos else 0.0

            risks = [
                s.risk_score for s in db_sentences_in_seg if s.risk_score is not None
            ]
            db_segment.risk_score = max(risks) if risks else 0

            # Calculate VADER pos, neg, neu components on segment text
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

                _vader_analyzer = SentimentIntensityAnalyzer()
                _vader_res = _vader_analyzer.polarity_scores(db_segment.text or "")
                db_segment.vader_pos = _vader_res.get("pos", 0.0)
                db_segment.vader_neg = _vader_res.get("neg", 0.0)
                db_segment.vader_neu = _vader_res.get("neu", 0.0)
            except Exception as e:
                logger.warning(
                    f"VADER parsing failed for segment {db_segment.seg_id}: {e}"
                )
                db_segment.vader_pos = 0.0
                db_segment.vader_neg = 0.0
                db_segment.vader_neu = 0.0

            # Recalculate SBI and DKI using auditor's formula so they are correct in DB
            RISK_SIGNAL_WEIGHTS = _infra_import(
                "bb_paxdata.infrastructure.logic.formula_auditor", "RISK_SIGNAL_WEIGHTS"
            )
            RISK_SIGNALS = _infra_import(
                "bb_paxdata.infrastructure.logic.formula_auditor", "RISK_SIGNALS"
            )

            _power_levels = []
            _demand_weights = []
            _risk_scores = []
            _sp_power = float(db_speaker.power_level) if db_speaker else 5.0

            for s in db_sentences_in_seg:
                stxt_lower = (s.text or "").lower()
                _d_w = 0.5
                if any(
                    w in stxt_lower for w in ["must", "require", "demand", "insist"]
                ):
                    _d_w = 0.9
                elif any(w in stxt_lower for w in ["should", "ought", "recommend"]):
                    _d_w = 0.7
                elif any(w in stxt_lower for w in ["suggest", "propose", "consider"]):
                    _d_w = 0.5
                _demand_weights.append(_d_w)

                _det_sigs = [sig for sig in RISK_SIGNALS if sig in stxt_lower]
                _r_val = min(
                    10.0, sum(RISK_SIGNAL_WEIGHTS.get(sig, 1) for sig in _det_sigs)
                )
                _risk_scores.append(_r_val)
                _power_levels.append(_sp_power)

            if _risk_scores:
                _avg_power = sum(_power_levels) / len(_power_levels)
                _avg_demand = sum(_demand_weights) / len(_demand_weights)
                _avg_risk = sum(_risk_scores) / len(_risk_scores)

                db_segment.sbi_score = (_avg_power * _avg_demand) / 2.0 + _avg_risk

                def norm_val(
                    val: float, min_v: float = 0.0, max_v: float = 10.0
                ) -> float:
                    if max_v <= min_v:
                        return 0.0
                    return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))

                _norm_diplo = norm_val(5.0 - _avg_risk)
                _norm_risk = norm_val(_avg_risk)
                _norm_demand = min(_avg_demand, 1.0)
                _norm_manip = min(1.0, max(0.0, (_avg_demand - 0.5) * 2.0))

                _base_dki = (
                    _norm_diplo * 0.4
                    + (1.0 - _norm_risk) * 0.3
                    + _norm_demand * 0.2
                    + (1.0 - _norm_manip) * 0.1
                )
                db_segment.dki_score = (_base_dki * 2.0) - 1.0
            else:
                db_segment.sbi_score = 0.0
                db_segment.dki_score = 0.0

            frames = [s.dominant_frame for s in db_sentences_in_seg if s.dominant_frame]
            db_segment.dominant_frame = (
                Counter(frames).most_common(1)[0][0] if frames else None
            )

            emotions = [
                s.emotion_category for s in db_sentences_in_seg if s.emotion_category
            ]
            db_segment.emotion_category = (
                Counter(emotions).most_common(1)[0][0] if emotions else None
            )

            topics = [s.dominant_topic for s in db_sentences_in_seg if s.dominant_topic]
            valid_topics = [t for t in topics if t != "-1"]
            db_segment.dominant_topic = (
                Counter(valid_topics).most_common(1)[0][0]
                if valid_topics
                else "General"
            )

            db_segment.word_count = sum(s.word_count for s in db_sentences_in_seg)
            db_segment.sentence_count = len(db_sentences_in_seg)

            # avg_word_len
            _seg_words = re.findall(r"\w+", db_segment.text or "")
            db_segment.avg_word_len = (
                sum(len(w) for w in _seg_words) / len(_seg_words) if _seg_words else 0.0
            )

            # rhetoric_patterns JSON
            db_segment.rhetoric_patterns = dict(Counter(db_patterns_in_seg))

            # risk_trajectory
            if len(db_sentences_in_seg) >= 3:
                _n = len(db_sentences_in_seg)
                _idx_25 = max(1, _n // 4)
                _start_risk = (
                    sum(s.risk_score or 0.0 for s in db_sentences_in_seg[:_idx_25])
                    / _idx_25
                )
                _end_risk = (
                    sum(s.risk_score or 0.0 for s in db_sentences_in_seg[-_idx_25:])
                    / _idx_25
                )
                _diff = _end_risk - _start_risk
                if _diff > 1.5:
                    db_segment.risk_trajectory = "ESCALATING"
                elif _diff < -1.5:
                    db_segment.risk_trajectory = "DE-ESCALATING"
                else:
                    db_segment.risk_trajectory = "STABLE"
            else:
                db_segment.risk_trajectory = "STABLE"

            # risk_trend
            if len(db_sentences_in_seg) >= 2:
                _first_half = db_sentences_in_seg[: len(db_sentences_in_seg) // 2]
                _second_half = db_sentences_in_seg[len(db_sentences_in_seg) // 2 :]
                _avg_first = sum(s.risk_score or 0.0 for s in _first_half) / len(
                    _first_half
                )
                _avg_second = sum(s.risk_score or 0.0 for s in _second_half) / len(
                    _second_half
                )
                _trend_diff = _avg_second - _avg_first
                if _trend_diff > 0.5:
                    db_segment.risk_trend = "UPWARD"
                elif _trend_diff < -0.5:
                    db_segment.risk_trend = "DOWNWARD"
                else:
                    db_segment.risk_trend = "FLAT"
            else:
                db_segment.risk_trend = "FLAT"

            # intro_sentiment, develop_sentiment, concl_sentiment
            _n_sents = len(db_sentences_in_seg)
            if _n_sents > 0:
                _intro_end = max(1, _n_sents // 5)
                _concl_start = max(_n_sents - _intro_end, _intro_end + 1)

                _intro_sents = db_sentences_in_seg[:_intro_end]
                _concl_sents = db_sentences_in_seg[_concl_start:]
                _develop_sents = db_sentences_in_seg[_intro_end:_concl_start]

                db_segment.intro_sentiment = (
                    sum(s.vader_compound or 0.0 for s in _intro_sents)
                    / len(_intro_sents)
                    if _intro_sents
                    else 0.0
                )
                db_segment.develop_sentiment = (
                    sum(s.vader_compound or 0.0 for s in _develop_sents)
                    / len(_develop_sents)
                    if _develop_sents
                    else 0.0
                )
                db_segment.concl_sentiment = (
                    sum(s.vader_compound or 0.0 for s in _concl_sents)
                    / len(_concl_sents)
                    if _concl_sents
                    else 0.0
                )
            else:
                db_segment.intro_sentiment = 0.0
                db_segment.develop_sentiment = 0.0
                db_segment.concl_sentiment = 0.0

            # dominant_audience, dominant_evidence, formula_manip_score
            audiences = [
                s.audience_type for s in db_sentences_in_seg if s.audience_type
            ]
            db_segment.dominant_audience = (
                Counter(audiences).most_common(1)[0][0] if audiences else None
            )

            evidences = []
            for s in db_sentences_in_seg:
                if s.evidence_types:
                    if isinstance(s.evidence_types, list):
                        evidences.extend(s.evidence_types)
                    elif isinstance(s.evidence_types, str):
                        try:
                            import json

                            evidences.extend(json.loads(s.evidence_types))
                        except Exception:
                            pass
            db_segment.dominant_evidence = (
                Counter(evidences).most_common(1)[0][0] if evidences else None
            )

            db_segment.formula_manip_score = (
                sum(s.negation_aware_diplo or 0.0 for s in db_sentences_in_seg)
                / len(db_sentences_in_seg)
                if db_sentences_in_seg
                else 0.0
            )

            # ── Segment-level NLP aggregation ──
            hedgings = [s.hedging_score for s in db_sentences_in_seg if s.hedging_score]
            db_segment.avg_hedging_score = (
                sum(hedgings) / len(hedgings) if hedgings else 0.0
            )
            politeness_vals = [
                s.politeness_ratio
                for s in db_sentences_in_seg
                if s.politeness_ratio is not None
            ]
            db_segment.avg_politeness_ratio = (
                sum(politeness_vals) / len(politeness_vals) if politeness_vals else 0.0
            )
            demands_in_seg = [s for s in db_sentences_in_seg if s.demand_type]
            db_segment.demand_count = len(demands_in_seg)

            # ── Segment-level enrichment via Gateway ──
            enrichment_gateway = SegmentEnrichmentGateway(
                segment_service=getattr(pipeline, "segment", None),
                lodp_service=getattr(pipeline, "assembler", None),
            )
            enriched_data = enrichment_gateway.enrich(
                db_segment=db_segment,
                db_sentences=db_sentences_in_seg,
                pipeline_res=pipeline_res,
                topic_result=None,
                db_speaker=db_speaker,
            )

            db_segment.bloc = enriched_data.bloc
            db_segment.role = enriched_data.role
            db_segment.key_phrases = enriched_data.key_phrases
            db_segment.tfidf_keywords = enriched_data.tfidf_keywords
            db_segment.entities_gpe = enriched_data.entities_gpe
            db_segment.entities_org = enriched_data.entities_org
            db_segment.entities_person = enriched_data.entities_person
            db_segment.risk_signals = enriched_data.risk_signals
            db_segment.demand_concentration = enriched_data.demand_concentration
            db_segment.inconsistency_score = enriched_data.inconsistency_score
            db_segment.dominant_frame = enriched_data.dominant_frame

        # Update File aggregate stats at the end
        if db_file:
            db_file.n_segments = len(segments_data)
            db_file.n_sentences = total_sentences_count
            db_file.n_speakers = len(unique_speakers_in_file)
            db_file.n_countries = len(unique_countries_in_file)
            db_file.total_words = total_words_in_file

        # (File Dynamics block was moved below to run after Phase 5 Topic Modeling)

        # Processed files tracking updated above

        # ── Topic Modeling Post-Processing (Faz 5) ──
        try:
            from bb_paxdata.application.domain.models.segment import (
                Segment as SegmentDomain,
            )
            from bb_paxdata.application.domain.models.sentence import (
                Sentence as SentenceDomain,
            )

            TopicAssignmentORM = _infra_import(
                "bb_paxdata.infrastructure.db.topic_models", "TopicAssignmentORM"
            )

            # Group sentences by segment ID
            sentences_by_seg_id: dict[str, list[Any]] = {}
            for sent in all_processed_sentences:
                sentences_by_seg_id.setdefault(sent.seg_id, []).append(sent)

            # Construct SegmentDomain and SentenceDomain objects
            domain_segments = []
            for seg_id, seg_sents in sentences_by_seg_id.items():
                domain_sents = [
                    SentenceDomain(id=s.sent_id, text=s.text) for s in seg_sents
                ]

                # Extract speaker, GPE, and tokens for Phase 4 Discourse Network build
                primary_speaker = None
                concepts = []
                segment_tokens = []
                for s in seg_sents:
                    if not primary_speaker:
                        primary_speaker = s.speaker_id
                    segment_tokens.extend(s.text.lower().split())
                    if s.entities_gpe:
                        for gpe in s.entities_gpe:
                            gpe_clean = gpe.strip().title()
                            if gpe_clean and gpe_clean not in concepts:
                                concepts.append(gpe_clean)
                    if (
                        s.dominant_topic
                        and s.dominant_topic != "-1"
                        and s.dominant_topic not in concepts
                    ):
                        concepts.append(s.dominant_topic)

                domain_segments.append(
                    SegmentDomain(
                        id=seg_id,
                        file_id=file_id,
                        primary_speaker_id=primary_speaker,
                        tokens=segment_tokens,
                        key_concepts=concepts,
                        sentences=domain_sents,
                    )
                )

            if len(domain_segments) >= 2:
                logger.info(
                    "Running panel-level topic modeling",
                    segment_count=len(domain_segments),
                )
                lang = "en"
                if (
                    all_processed_sentences
                    and "pipeline_res" in locals()
                    and pipeline_res is not None
                    and getattr(pipeline_res, "analysis", None) is not None
                ):
                    lang = (pipeline_res.analysis.language or "en").lower()

                topic_result = await container.topic_modeling_service.extract_topics(
                    segments=domain_segments,
                    language=lang,
                    min_topic_size=2,
                )

                # Map the assignments by segment ID
                assignments_by_seg = {a.segment_id: a for a in topic_result.assignments}

                for seg_id, seg_sents in sentences_by_seg_id.items():
                    assign = assignments_by_seg.get(seg_id)
                    if assign:
                        primary_topic = assign.primary_topic or "-1"
                        topic_scores = assign.topic_scores or {}

                        # Get topic keywords for this topic
                        keywords = topic_result.topic_keywords.get(primary_topic, {})
                        if keywords:
                            topic_label = ", ".join(list(keywords.keys())[:3])
                        else:
                            topic_label = primary_topic

                        # Update Segment ORM
                        seg_stmt = select(Segment).where(Segment.seg_id == seg_id)
                        res_seg = await session.execute(seg_stmt)
                        db_seg = res_seg.scalar_one_or_none()
                        if db_seg:
                            db_seg.dominant_topic = topic_label
                            db_seg.topic_scores = topic_scores

                        # Update Sentence ORM & TopicAssignmentORM
                        for s in seg_sents:
                            s.dominant_topic = topic_label
                            s.topic_scores = topic_scores

                            # ── Calculate topic_specificity (Shannon entropy) ──
                            import math

                            _non_zero = [v for v in topic_scores.values() if v > 0]
                            if not _non_zero:
                                s.topic_specificity = 0.0
                            elif len(_non_zero) == 1:
                                s.topic_specificity = 1.0
                            else:
                                _tot = sum(_non_zero)
                                _probs = [v / _tot for v in _non_zero]
                                _ent = -sum(p * math.log2(p) for p in _probs if p > 0)
                                _max_ent = math.log2(len(_non_zero))
                                s.topic_specificity = round(
                                    1.0 - (_ent / _max_ent) if _max_ent > 0 else 1.0, 4
                                )

                            stmt_assign = select(TopicAssignmentORM).where(
                                TopicAssignmentORM.analysis_id == s.sent_id
                            )
                            res_assign = await session.execute(stmt_assign)
                            db_assign = res_assign.scalar_one_or_none()
                            if db_assign:
                                db_assign.primary_topic = primary_topic
                                db_assign.topic_scores = topic_scores
                                db_assign.topic_label = topic_label
                                db_assign.ctfidf_keywords = keywords
                logger.info("Topic modeling post-processing completed successfully")
        except Exception as exc:
            logger.warning(
                "build.topic_modeling_post_processing_failed", error=str(exc)
            )

        # ── File Dynamics: cümle bazlı temporal değişim kayıtları ──
        # Tüm segment döngülerinden toplanan cümleleri sıralı şekilde işle
        _all_built_sentences = all_processed_sentences

        _prev_risk_dyn = None
        _prev_sentiment_dyn = None
        _prev_topic_dyn = None
        for dyn_pos, dyn_sent in enumerate(_all_built_sentences, 1):
            if dyn_pos == 1:
                _risk_d = 0.0
                _sent_d = 0.0
                _topic_changed = 0
                _kgi = 0.0
            else:
                prev_risk = _prev_risk_dyn if _prev_risk_dyn is not None else 0
                prev_sent = (
                    _prev_sentiment_dyn if _prev_sentiment_dyn is not None else 0.0
                )
                _risk_d = (dyn_sent.risk_score or 0) - prev_risk
                _sent_d = (dyn_sent.vader_compound or 0.0) - prev_sent
                _topic_changed = (
                    1
                    if (
                        dyn_sent.dominant_topic
                        and dyn_sent.dominant_topic != _prev_topic_dyn
                    )
                    else 0
                )
                # KGI = abs(risk_delta) * 0.4 + abs(emotion_shift) * 0.3 + topic_shift * 0.3
                _kgi = (
                    abs(_risk_d / 10.0) * 0.4
                    + abs(_sent_d) * 0.3
                    + _topic_changed * 0.3
                )

            db_dyn = FileDynamics(
                file_id=file_id,
                position=dyn_pos,
                speaker_name=dyn_sent.speaker_name,
                country=dyn_sent.country,
                kgi_score=round(_kgi, 4),
                risk_delta=round(_risk_d, 2),
                emotion_shift=round(_sent_d, 4),
                topic_shift=_topic_changed,
                inconsistency_score=getattr(
                    dyn_sent, "formula_inconsistency_score", 0.0
                ),
                sent_id=dyn_sent.sent_id,
            )
            session.add(db_dyn)

            _prev_risk_dyn = dyn_sent.risk_score or 0
            _prev_sentiment_dyn = dyn_sent.vader_compound or 0.0
            _prev_topic_dyn = dyn_sent.dominant_topic

        # ── Formula Logic Audit (YENİ) ──
        try:
            import json
            import uuid

            run_id = f"run_{uuid.uuid4().hex}"
            auditor = FormulaAuditor()

            # Group sentences by segment id for segment audit
            sents_by_seg: dict[str, list[Any]] = {}
            logic_fail_sents_added = set()
            # v2: Track per-sentence fail counts for FORMULA_FAILURE trigger
            sent_fail_counts: dict[str, int] = {}

            for sent in all_processed_sentences:
                sents_by_seg.setdefault(sent.seg_id, []).append(sent)

                # Audit sentence
                sent_logs = auditor.audit_sentence(run_id, sent)
                for log_data in sent_logs:
                    # v2: Calculate triage priority
                    _fail_count = sent_fail_counts.get(sent.sent_id, 0)
                    if log_data["status"] == "FAIL":
                        _fail_count += 1
                        sent_fail_counts[sent.sent_id] = _fail_count

                    _triage_priority, _triage_reason = (
                        auditor.calculate_triage_priority(
                            fail_count=_fail_count,
                            speaker_power_level=getattr(sent, "power_level", 0) or 0,
                            formula_name=log_data["formula_name"],
                            ai_risk_score=float(getattr(sent, "risk_score", 0) or 0),
                        )
                    )

                    db_log = FormulaValidationLog(
                        run_id=log_data["run_id"],
                        entity_type=log_data["entity_type"],
                        entity_id=log_data["entity_id"],
                        sentence_code=getattr(sent, "sentence_code", None),
                        formula_name=log_data["formula_name"],
                        expected_constraint=log_data["expected_constraint"],
                        actual_value=log_data["actual_value"],
                        status=log_data["status"],
                        details=log_data["details"],
                        # v2: Triage & versioning fields
                        auto_triage_reason=(
                            _triage_reason if log_data["status"] == "FAIL" else None
                        ),
                        confidence_at_review=(
                            _triage_priority if log_data["status"] == "FAIL" else None
                        ),
                        log_version=1,
                        is_current=True,
                    )
                    session.add(db_log)

                    db_log.record_event(
                        event_type="FormulaValidated",
                        payload={
                            "run_id": db_log.run_id,
                            "entity_type": db_log.entity_type,
                            "entity_id": db_log.entity_id,
                            "formula_name": db_log.formula_name,
                            "expected_constraint": db_log.expected_constraint,
                            "actual_value": (
                                db_log.actual_value
                                if db_log.actual_value is not None
                                else 0.0
                            ),
                            "status": db_log.status,
                        },
                        actor_id="system",
                        aggregate_id=f"{db_log.run_id}_{db_log.formula_name}_{db_log.entity_id}",
                    )

                    # v2: Flag to Human Review Queue with FORMULA_FAILURE trigger
                    # Only when fail_count >= 3 for this sentence
                    if (
                        log_data["status"] == "FAIL"
                        and _fail_count >= 3
                        and sent.sent_id not in logic_fail_sents_added
                    ):
                        logic_fail_sents_added.add(sent.sent_id)
                        _ai_json = json.dumps(
                            {
                                "formula_name": log_data["formula_name"],
                                "expected_constraint": log_data["expected_constraint"],
                                "actual_value": log_data["actual_value"],
                                "details": log_data["details"],
                                "text": getattr(sent, "text", ""),
                                "fail_count": _fail_count,
                                "triage_priority": _triage_priority,
                                "triage_reason": _triage_reason,
                            },
                            ensure_ascii=False,
                        )
                        review_entry = HumanReviewQueue(
                            sent_id=sent.sent_id,
                            sentence_code=getattr(sent, "sentence_code", None),
                            seg_id=sent.seg_id,
                            file_id=sent.file_id,
                            speaker_name=sent.speaker_name,
                            country=sent.country,
                            trigger_type="FORMULA_FAILURE",
                            ai_risk_score=sent.risk_score,
                            anomaly_types=f"FORMULA_FAIL(x{_fail_count}): {log_data['formula_name']}",
                            uncertainty_score=0.0,
                            status="PENDING",
                            original_ai_json=_ai_json,
                            flagged_at=utc_now().isoformat(),
                        )
                        session.add(review_entry)

            for db_seg in all_processed_segments:
                seg_sents = sents_by_seg.get(db_seg.seg_id, [])
                seg_logs = auditor.audit_segment(run_id, db_seg, seg_sents)
                for log_data in seg_logs:
                    db_log = FormulaValidationLog(
                        run_id=log_data["run_id"],
                        entity_type=log_data["entity_type"],
                        entity_id=log_data["entity_id"],
                        sentence_code=seg_sents[0].sentence_code if seg_sents else None,
                        formula_name=log_data["formula_name"],
                        expected_constraint=log_data["expected_constraint"],
                        actual_value=log_data["actual_value"],
                        status=log_data["status"],
                        details=log_data["details"],
                        # v2: versioning
                        log_version=1,
                        is_current=True,
                    )
                    session.add(db_log)

                    db_log.record_event(
                        event_type="FormulaValidated",
                        payload={
                            "run_id": db_log.run_id,
                            "entity_type": db_log.entity_type,
                            "entity_id": db_log.entity_id,
                            "formula_name": db_log.formula_name,
                            "expected_constraint": db_log.expected_constraint,
                            "actual_value": (
                                db_log.actual_value
                                if db_log.actual_value is not None
                                else 0.0
                            ),
                            "status": db_log.status,
                        },
                        actor_id="system",
                        aggregate_id=f"{db_log.run_id}_{db_log.formula_name}_{db_log.entity_id}",
                    )

                    # Flag to Human Review Queue if FAIL
                    if log_data["status"] == "FAIL" and seg_sents:
                        first_sent = seg_sents[0]
                        if first_sent.sent_id not in logic_fail_sents_added:
                            logic_fail_sents_added.add(first_sent.sent_id)
                            _ai_json = json.dumps(
                                {
                                    "formula_name": log_data["formula_name"],
                                    "expected_constraint": log_data[
                                        "expected_constraint"
                                    ],
                                    "actual_value": log_data["actual_value"],
                                    "details": log_data["details"],
                                    "segment_text": getattr(db_seg, "text", ""),
                                },
                                ensure_ascii=False,
                            )
                            review_entry = HumanReviewQueue(
                                sent_id=first_sent.sent_id,
                                sentence_code=getattr(
                                    first_sent, "sentence_code", None
                                ),
                                seg_id=db_seg.seg_id,
                                file_id=db_seg.file_id,
                                speaker_name=db_seg.speaker_name,
                                country=db_seg.country,
                                trigger_type="FORMULA_FAILURE",
                                ai_risk_score=db_seg.risk_score,
                                anomaly_types=f"FORMULA_FAIL: {log_data['formula_name']}",
                                uncertainty_score=0.0,
                                status="PENDING",
                                original_ai_json=_ai_json,
                                flagged_at=utc_now().isoformat(),
                            )
                            session.add(review_entry)
            logger.info("Formula logic audit completed and logged to database")
        except Exception as exc:
            logger.warning("build.formula_logic_audit_failed", error=str(exc))

        # ── Temporal Drift Event Analysis ──
        try:
            from bb_paxdata.application.domain.models.speech_act import (
                SPEECH_ACT_MODIFIER,
                SPEECH_ACT_PRIMARY,
            )
            from bb_paxdata.application.domain.services.temporal import TemporalAnalyzer

            DriftEventORM = _infra_import(
                "bb_paxdata.infrastructure.db.drift_events", "DriftEvent"
            )

            # Group sentences by speaker
            speaker_data = {}
            sentence_data = []
            for s in all_processed_sentences:
                sp_id = s.speaker_id or s.speaker_name or "unknown"
                if sp_id not in speaker_data:
                    speaker_data[sp_id] = {
                        "speaker_id": sp_id,
                        "speaker_name": s.speaker_name,
                        "country": s.country,
                    }

                sa_primary = "ASSERTIVE"
                sa_mod = None
                if getattr(s, "ai_analysis", None) and s.ai_analysis.speech_act_domain:
                    sa_primary = s.ai_analysis.speech_act_domain.primary_type.value
                    sa_mod = s.ai_analysis.speech_act_domain.force_modifier

                sentence_data.append(
                    {
                        "speaker_id": sp_id,
                        "global_sent_order": s.global_sent_order or 0,
                        "text": s.text or "",
                        "AI_Duygu_Skoru": s.vader_compound,
                        "AI_Risk_Skoru": s.risk_score,
                        "AI_Birincil_Konu": s.dominant_topic,
                        "AI_Diplomatik_Ton": s.dominant_frame,
                        SPEECH_ACT_PRIMARY: sa_primary,
                        SPEECH_ACT_MODIFIER: sa_mod,
                        "AI_Speech_Act": sa_primary,
                        "AI_Speech_Act_Modifier": sa_mod,
                    }
                )

            panel_data = {"panel_id": file_id}
            analyzer = TemporalAnalyzer()
            drift_events = analyzer.analyze_panel_drift(
                panel_data, speaker_data, sentence_data
            )

            # Delete old drift events for this panel first (idempotency)
            await session.execute(
                delete(DriftEventORM).where(DriftEventORM.panel_id == file_id)
            )

            for drift in drift_events:
                db_drift = DriftEventORM(
                    speaker_id=drift.speaker_id,
                    panel_id=drift.panel_id,
                    drift_type=drift.drift_type,
                    start_position=drift.start_position,
                    end_position=drift.end_position,
                    severity=drift.severity,
                    before_state=drift.before_state,
                    after_state=drift.after_state,
                    confidence=drift.confidence,
                    algorithm=drift.algorithm,
                )
                session.add(db_drift)

            if drift_events:
                logger.info(
                    "Detected and logged temporal drift events",
                    count=len(drift_events),
                )
            else:
                logger.info(
                    "Temporal drift analysis completed (no drift events detected)"
                )

        except Exception as exc:
            logger.warning("build.temporal_drift_analysis_failed", error=str(exc))

        # ── Phase 4 Discourse Network and Flows Integration ──
        try:
            await rebuild_network_for_file(session, file_id)
        except Exception as exc:
            logger.warning(
                "build.rebuild_network_failed", file_id=file_id, error=str(exc)
            )

        # ── Topic Matrix 2.0: Event Logging ──
        try:
            import uuid

            from bb_paxdata.application.domain.services.linguistic_helpers import (
                classify_speech_act,
                get_frame_distribution,
                get_vad_vector,
            )

            SegmentAnalyzedEvent = _infra_import(
                "bb_paxdata.infrastructure.db.models", "SegmentAnalyzedEvent"
            )

            run_id_event = f"run_{uuid.uuid4().hex}"

            for db_seg in all_processed_segments:
                vad = get_vad_vector(
                    db_seg.diplo_compound or 0.0, db_seg.emotion_category
                )
                act = classify_speech_act(db_seg.text or "", db_seg.demand_count or 0)
                frames_dist = get_frame_distribution(
                    db_seg.text or "", db_seg.dominant_frame
                )

                event = SegmentAnalyzedEvent(
                    event_id=str(uuid.uuid4()),
                    event_timestamp=utc_now(),
                    file_id=file_id,
                    segment_id=db_seg.seg_id,
                    country=db_seg.country or "unknown",
                    text_snippet=db_seg.text,
                    vader_compound=db_seg.vader_compound or 0.0,
                    diplo_compound=db_seg.diplo_compound or 0.0,
                    vad_vector=vad,
                    emotion_category=db_seg.emotion_category,
                    risk_score=db_seg.risk_score or 0.0,
                    demand_count=db_seg.demand_count or 0,
                    speech_act=act,
                    hedging_score=(
                        db_seg.avg_hedging_score
                        if hasattr(db_seg, "avg_hedging_score")
                        else 0.0
                    ),
                    politeness_ratio=(
                        db_seg.avg_politeness_ratio
                        if hasattr(db_seg, "avg_politeness_ratio")
                        else 0.0
                    ),
                    topic_scores=db_seg.topic_scores or {},
                    topic_model_version="bertopic_v1",
                    frame_distribution=frames_dist,
                    pipeline_run_id=run_id_event,
                )
                session.add(event)

            logger.info("Logged segment events to event store")
        except Exception as exc:
            logger.warning("build.segment_event_logging_failed", error=str(exc))

        # ── Meilisearch Indexing Hook ──
        try:
            ensure_indexes = _infra_import(
                "bb_paxdata.infrastructure.search.meilisearch_client", "ensure_indexes"
            )
            index_sentences = _infra_import(
                "bb_paxdata.infrastructure.search.meilisearch_client", "index_sentences"
            )

            # İdempotent: index yoksa oluştur, varsa dokunma.
            await ensure_indexes()

            meili_docs = [
                {
                    "sent_id": s.sent_id,
                    "sentence_text": s.text,
                    "speaker_name": s.speaker_name,
                    "country": s.country,
                    "file_id": s.file_id,
                    "AI_Risk_Skoru": s.risk_score,
                    "AI_Diplomatik_Ton": s.emotion_category,
                    "AI_Birincil_Konu": s.dominant_topic,
                    "created_at": (
                        getattr(s, "created_at", None) or utc_now()
                    ).isoformat(),
                }
                for s in all_processed_sentences
            ]
            if meili_docs:
                await index_sentences(meili_docs)
        except Exception as meili_exc:
            logger.warning("meilisearch.indexing_failed", error=str(meili_exc))

        await session.flush()
        return "processed"


async def rebuild_network_for_file(session: Any, file_id: str) -> None:
    """Rebuilds bilateral sentiments, discourse network edges, and discourse flows for a single file/panel."""
    from sqlalchemy import delete

    BilateralSentimentTable = _infra_import(
        "bb_paxdata.infrastructure.db.country_models", "BilateralSentimentTable"
    )
    DiscourseFlowTable = _infra_import(
        "bb_paxdata.infrastructure.db.country_models", "DiscourseFlowTable"
    )
    DiscourseNetworkEdgeTable = _infra_import(
        "bb_paxdata.infrastructure.db.discourse_network_table",
        "DiscourseNetworkEdgeTable",
    )
    ActorActionMatrixORM = _infra_import(
        "bb_paxdata.infrastructure.db.models", "ActorActionMatrixORM"
    )
    DependencyTripleORM = _infra_import(
        "bb_paxdata.infrastructure.db.models", "DependencyTripleORM"
    )

    # Clean existing network data for this panel to support clean re-runs
    await session.execute(
        delete(BilateralSentimentTable).where(
            BilateralSentimentTable.file_id == file_id
        )
    )
    await session.execute(
        delete(DiscourseFlowTable).where(DiscourseFlowTable.file_id == file_id)
    )
    await session.execute(
        delete(DiscourseNetworkEdgeTable).where(
            DiscourseNetworkEdgeTable.file_id == file_id
        )
    )
    await session.execute(
        delete(DependencyTripleORM).where(DependencyTripleORM.file_id == file_id)
    )
    await session.execute(
        delete(ActorActionMatrixORM).where(ActorActionMatrixORM.file_id == file_id)
    )
    await session.flush()

    # Construct SegmentDomain and SentenceDomain from database Segment and Sentence repositories
    from bb_paxdata.application.domain.models.segment import Segment as SegmentDomain
    from bb_paxdata.application.domain.models.sentence import Sentence as SentenceDomain

    SegmentRepository = _infra_import(
        "bb_paxdata.infrastructure.db.repositories.segment", "SegmentRepository"
    )
    SentenceRepository = _infra_import(
        "bb_paxdata.infrastructure.db.repositories.sentence", "SentenceRepository"
    )

    seg_repo = SegmentRepository(session)
    sent_repo = SentenceRepository(session)

    db_segs = await seg_repo.get_domain_by_panel(file_id)
    db_sents = await sent_repo.get_domain_by_panel(file_id)

    # Group sentences by segment id
    sents_by_seg: dict[str, list[Any]] = {}
    for s in db_sents:
        sents_by_seg.setdefault(s.segment_id, []).append(s)

    # Build domain segments
    domain_segments = []
    for db_seg in db_segs:
        seg_sents = sents_by_seg.get(db_seg.id, [])
        from bb_paxdata.application.domain.models.srl import ExtractionStatus

        get_srl_pipeline = _infra_import(
            "bb_paxdata.infrastructure.nlp.srl_pipeline", "get_srl_pipeline"
        )

        domain_sents = []
        for s in seg_sents:
            try:
                srl_res = get_srl_pipeline().extract_from_text(s.text)
                srl_frames = srl_res.frames
                status = (
                    ExtractionStatus.COMPLETED
                    if srl_frames
                    else ExtractionStatus.SKIPPED
                )
            except Exception as e:
                logger.warning(
                    "srl_extraction_failed_in_trigger",
                    sentence_id=s.id,
                    error=str(e),
                )
                srl_frames = []
                status = ExtractionStatus.FAILED

            domain_sents.append(
                SentenceDomain(
                    id=s.id,
                    text=s.text,
                    srl_frames=srl_frames,
                    srl_extraction_status=status,
                )
            )

        # Extract speaker, GPE, and tokens
        primary_speaker = db_seg.primary_speaker_id
        segment_tokens = db_seg.text.lower().split() if db_seg.text else []
        concepts = []
        for s in seg_sents:
            if s.entities_gpe:
                for gpe in s.entities_gpe:
                    gpe_clean = gpe.strip().title()
                    if gpe_clean and gpe_clean not in concepts:
                        concepts.append(gpe_clean)
            if s.dominant_topic:
                topic_val = (
                    s.dominant_topic.value
                    if hasattr(s.dominant_topic, "value")
                    else str(s.dominant_topic)
                )
                if topic_val != "-1" and topic_val not in concepts:
                    concepts.append(topic_val)

        domain_segments.append(
            SegmentDomain(
                id=db_seg.id,
                file_id=file_id,
                primary_speaker_id=primary_speaker,
                tokens=segment_tokens,
                key_concepts=concepts,
                sentences=domain_sents,
            )
        )

    # ── 1. Aggregate Bilateral Sentiment ──
    try:
        from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
            AggregateBilateralSentimentInput,
            AggregateBilateralSentimentUseCase,
        )
        from bb_paxdata.infrastructure.db.repositories.country_repository import (
            BilateralSentimentRepository,
            CountryReferenceRepository,
        )

        bil_agg_use_case = AggregateBilateralSentimentUseCase(
            ref_repo=CountryReferenceRepository(session),
            sentiment_repo=BilateralSentimentRepository(session),
        )
        bil_agg_output = await bil_agg_use_case.execute(
            AggregateBilateralSentimentInput(panel_id=file_id)
        )
        if bil_agg_output.succeeded:
            logger.info(
                "Bilateral sentiments aggregated successfully",
                file_id=file_id,
                created_count=bil_agg_output.created_count,
            )
        else:
            logger.warning(
                "Bilateral sentiments aggregation failed",
                file_id=file_id,
                errors=bil_agg_output.errors,
            )
    except Exception as exc:
        logger.error(
            "Bilateral sentiments aggregation exception",
            file_id=file_id,
            error=str(exc),
        )

    # ── 2. Discourse Network Analysis (Fischer DNA & Maoz Dyadic) ──
    try:
        from bb_paxdata.application.domain.models.analysis import (
            Analysis as AnalysisDomain,
        )
        from bb_paxdata.application.pipeline.stages.assemble_network import (
            NetworkAssemblyStage,
        )
        from bb_paxdata.application.pipeline.stages.finalize_network import (
            NetworkFinalizeStage,
        )
        from bb_paxdata.infrastructure.container.service_container import (
            ServiceContainer,
        )
        from bb_paxdata.infrastructure.db.country_models import (
            BilateralSentimentTable,
        )
        from bb_paxdata.infrastructure.db.repositories.country_repository import (
            BilateralSentimentRepository,
        )
        from bb_paxdata.infrastructure.db.repositories.discourse_network_repository import (
            DiscourseNetworkRepository,
        )
        from bb_paxdata.infrastructure.nlp.fischer_dna_service import (
            FischerDNAService,
        )

        # Construct AnalysisDomain
        analysis_domain = AnalysisDomain(
            id=file_id,
            segments=domain_segments,
            bilateral_metrics=[],
        )

        # Fetch domain bilateral metrics from repository instead of direct ORM querying
        BilateralSentimentRepository = _infra_import(
            "bb_paxdata.infrastructure.db.repositories.country_repository",
            "BilateralSentimentRepository",
        )
        bilateral_repo = BilateralSentimentRepository(session)
        domain_bilaterals = await bilateral_repo.get_all_for_panel(file_id)

        analysis_domain = analysis_domain.model_copy(
            update={"bilateral_metrics": domain_bilaterals}
        )

        # Instantiate services & repositories
        fischer_service = FischerDNAService()
        container = ServiceContainer.get_instance()
        maoz_service = container.maoz_dyadic_service

        network_repo = DiscourseNetworkRepository(session)

        # Assemble network
        assembly_stage = NetworkAssemblyStage(
            fischer_service=fischer_service,
            maoz_service=maoz_service,
        )
        enriched_analysis = await assembly_stage.process(analysis_domain)

        # Finalize and persist network
        finalize_stage = NetworkFinalizeStage(
            network_repo=network_repo,
            bilateral_repo=bilateral_repo,
        )
        await finalize_stage.process(session, enriched_analysis)

        logger.info(
            "Discourse network analysis completed",
            file_id=file_id,
            edge_count=(
                enriched_analysis.discourse_flow.edge_count
                if enriched_analysis.discourse_flow
                else 0
            ),
        )
    except Exception as exc:
        logger.error(
            "Discourse network analysis failed",
            file_id=file_id,
            error=str(exc),
        )

    # ── 3. Build Panel Network (Discourse Flows) ──
    try:
        from bb_paxdata.application.use_cases.build_panel_network import (
            BuildPanelNetworkInput,
            BuildPanelNetworkUseCase,
        )

        BilateralSentimentRepository = _infra_import(
            "bb_paxdata.infrastructure.db.repositories.country_repository",
            "BilateralSentimentRepository",
        )
        DiscourseFlowRepository = _infra_import(
            "bb_paxdata.infrastructure.db.repositories.country_repository",
            "DiscourseFlowRepository",
        )

        flow_use_case = BuildPanelNetworkUseCase(
            sentiment_repo=BilateralSentimentRepository(session),
            flow_repo=DiscourseFlowRepository(session),
        )
        flow_output = await flow_use_case.execute(
            BuildPanelNetworkInput(panel_id=file_id)
        )
        if flow_output.succeeded:
            logger.info(
                "Discourse flows built successfully",
                file_id=file_id,
                edges_created=flow_output.edges_created,
            )
        else:
            logger.warning(
                "Discourse flows build had errors",
                file_id=file_id,
                errors=flow_output.errors,
            )
    except Exception as exc:
        logger.error(
            "Discourse flows use case execution failed",
            file_id=file_id,
            error=str(exc),
        )

    # ── 4. Extract and Persist Grammatical Dependency Triples (SVO) ──
    try:
        from collections import defaultdict

        from bb_paxdata.application.domain.models.dependency import ActorActionMatrix
        from bb_paxdata.application.domain.services.actor_resolver import ActorResolver

        ServiceContainer = _infra_import(
            "bb_paxdata.infrastructure.container.service_container", "ServiceContainer"
        )
        DependencyRepository = _infra_import(
            "bb_paxdata.infrastructure.db.repositories.dependency",
            "DependencyRepository",
        )

        container = ServiceContainer.get_instance()
        nlp_en = container.ner_service._models.get("en")
        nlp_tr = container.ner_service._models.get("tr")
        from bb_paxdata.application.domain.services.language_detector import (
            LanguageDetector,
        )

        dep_service = container.dependency_service
        dep_repo = DependencyRepository(session)

        matrix_counts: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "sentiment_sum": 0.0,
                "passive_cnt": 0,
                "neg_cnt": 0,
            }
        )

        for s in db_sents:
            if not s.text:
                continue
            lang = LanguageDetector.detect(s.text)
            nlp = nlp_en if lang == "en" else nlp_tr
            if not nlp:
                nlp = nlp_en or nlp_tr
            if not nlp:
                continue
            doc = nlp(s.text)
            triples = dep_service.extract_triples(doc)
            for t in triples:
                subj_res = (
                    ActorResolver.resolve_actor(t.subject_raw) or t.subject_resolved
                )
                obj_res = ActorResolver.resolve_actor(t.object_raw) or t.object_resolved

                t.subject_resolved = subj_res
                t.object_resolved = obj_res
                t.sent_id = s.id
                t.seg_id = s.segment_id
                t.panel_id = file_id
                t.speaker_name = s.speaker_name
                t.country = s.country

                t.sentiment_context = s.sentiment_score
                t.risk_score = s.risk_score

                await dep_repo.insert_triple(t)

                if subj_res and obj_res:
                    key = (subj_res, obj_res, t.verb_lemma)
                    matrix_counts[key]["count"] += 1
                    matrix_counts[key]["sentiment_sum"] += s.sentiment_score or 0.0
                    matrix_counts[key]["passive_cnt"] += 1 if t.is_passive else 0
                    matrix_counts[key]["neg_cnt"] += 1 if t.is_negative else 0

        for (from_c, to_c, verb), stats in matrix_counts.items():
            cnt = stats["count"]
            avg_sent = stats["sentiment_sum"] / cnt if cnt > 0 else 0.0
            passive_pct = stats["passive_cnt"] / cnt if cnt > 0 else 0.0
            neg_pct = stats["neg_cnt"] / cnt if cnt > 0 else 0.0

            matrix_entry = ActorActionMatrix(
                panel_id=file_id,
                from_country=from_c,
                to_country=to_c,
                verb=verb,
                count=cnt,
                avg_sentiment=avg_sent,
                is_passive_pct=passive_pct,
                is_negative_pct=neg_pct,
            )
            await dep_repo.upsert_actor_action_matrix(matrix_entry)

        logger.info(
            "Dependency parsing completed successfully",
            file_id=file_id,
        )
    except Exception as exc:
        logger.error(
            "Dependency parsing failed",
            file_id=file_id,
            error=str(exc),
        )

    await session.flush()
