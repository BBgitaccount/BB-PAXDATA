"""Build database command with duplicate protection and quality integration."""

import asyncio
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import structlog
import typer
from bb_paxdata.application.domain.services.analysis_trigger import (
    AnalysisTriggerService,
    rebuild_network_for_file,
)
from bb_paxdata.infrastructure.text.file_io_handler import (
    _parse_transcript_header_and_dialogue,
    calculate_idempotency_key,
    clean_speaker_name_helper,
    get_parser_version,
    get_speaker_map_version,
    parse_speakers_metadata,
    standardize_file_content,
    utc_now,
)
from rich.console import Console
from sqlalchemy import delete, func, select

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    AIFailAnalysis,
    AISentenceAnalysis,
    DemandRecord,
    File,
    FileDynamics,
    PatternRecord,
    Segment,
    Sentence,
    SpeakerProfile,
    Word,
)
from bb_paxdata.infrastructure.db.session import get_db_session, init_db
from bb_paxdata.interfaces.cli.dependencies import get_session
from bb_paxdata.quality.data_contract import DataContractValidator
from bb_paxdata.quality.violations import ViolationLogger

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Build database from transcript files")


async def _broadcast_progress(
    file_name: str,
    processed: int,
    total: int,
    stage: str,
    status: str = "PROCESSING",
) -> None:
    """Fire-and-forget WebSocket broadcast for build progress.

    Errors are intentionally swallowed — WS failures must never abort builds.
    """
    try:
        # Import here to avoid circular imports at module load time
        from bb_paxdata.interfaces.api.routers.ws.queue_ws import manager as ws_manager

        await ws_manager.broadcast(
            {
                "type": "IngestionProgress",
                "data": {
                    "file_name": file_name,
                    "processed_files": processed,
                    "total_files": total,
                    "status": status,
                    "current_stage": stage,
                    "timestamp": __import__("time").time(),
                },
            }
        )
    except Exception:
        pass  # WS errors must never abort the build pipeline


def match_keyword_with_boundaries(kw: str, text: str) -> bool:

    pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
    return bool(re.search(pattern, text))


def classify_pattern_subtype(pattern_type: str, matched_kw: str) -> str:
    _pattern_subtypes = {
        "if": "hypothesis",
        "eğer": "hypothesis",
        "şayet": "hypothesis",
        "provided that": "precondition",
        "koşuluyla": "precondition",
        "we will": "promise",
        "biz yapacağız": "promise",
        "commit": "official_pledge",
        "taahhüt": "official_pledge",
        "pledge": "official_pledge",
        "otherwise": "consequence_clause",
        "aksi halde": "consequence_clause",
        "consequences": "warning_clause",
        "sonuçları olur": "warning_clause",
        "however": "contrast",
        "ancak": "contrast",
        "bununla birlikte": "contrast",
        "although": "concession",
        "rağmen": "concession",
        "we call upon": "exhortation",
        "çağrıda bulunuyoruz": "exhortation",
        "international community": "audience_appeal",
        "uluslararası toplum": "audience_appeal",
    }
    return _pattern_subtypes.get(matched_kw, "unknown")


async def _process_single_file(
    session: Any,
    file_path: Path,
    force_rebuild: bool,
    dry_run: bool,
    validator: Any,
    violation_logger: Any,
    container: Any,
    pipeline: Any,
) -> str:
    """Processes, standardizes, and ingests a single transcript file into the database."""
    # 1. Read raw content
    with open(file_path, encoding="utf-8") as f:
        raw_content = f.read()

    # 2. Automatically standardize content (pre-ingestion formatting)
    standardized_content = standardize_file_content(file_path, raw_content)

    # 3. Overwrite the file on disk if changes are made
    if raw_content != standardized_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(standardized_content)
            file_content = standardized_content
        except Exception as e:
            console.print(
                f"[yellow][WARN] Failed to write standardized content back to {file_path.name}: {e}"
            )
            file_content = raw_content
    else:
        file_content = raw_content

    # Calculate idempotency key based on standardized content
    idempotency_key = calculate_idempotency_key(
        file_content,
        file_path.name,
        get_parser_version(),
        get_speaker_map_version(),
    )

    # Check if already processed
    stmt = select(File).where(File.idempotency_key == idempotency_key)
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing and not force_rebuild and existing.force_rebuild == 0:
        return "skipped"

    # Validate input
    validation_result = validator.validate_transcript_input(file_content, file_path)
    if not validation_result.passed:
        console.print(f"[red][ERROR] Input validation failed for {file_path.name}")
        violation_logger.log_input_violation(
            str(file_path),
            validation_result.details.get("failed_checks", []),
        )
        return "error"

    if dry_run:
        console.print(f"[cyan]🔍 Would process: {file_path.name}")
        console.print(f"   Idempotency key: {idempotency_key[:16]}...")
        return "processed"

    # Process file
    console.print(f"[green]📝 Processing: {file_path.name}")

    # File ID from file stem
    file_id = file_path.stem.lower().replace(" ", "_")

    # Clean existing data for this panel to support clean re-runs
    from bb_paxdata.infrastructure.db.country_models import (
        BilateralSentimentTable,
        CountryReferenceTable,
        DiscourseFlowTable,
        TopicMatrixTable,
    )
    from bb_paxdata.infrastructure.db.discourse_network_table import (
        DiscourseNetworkEdgeTable,
    )
    from bb_paxdata.infrastructure.db.models import TopicMatrix as TopicMatrixORM
    from bb_paxdata.infrastructure.db.topic_models import TopicAssignmentORM

    await session.execute(
        delete(AIFailAnalysis).where(AIFailAnalysis.file_id == file_id)
    )
    await session.execute(
        delete(HumanReviewQueue).where(HumanReviewQueue.file_id == file_id)
    )
    await session.execute(delete(DemandRecord).where(DemandRecord.file_id == file_id))
    await session.execute(delete(PatternRecord).where(PatternRecord.file_id == file_id))
    await session.execute(delete(FileDynamics).where(FileDynamics.file_id == file_id))
    await session.execute(
        delete(AISentenceAnalysis).where(AISentenceAnalysis.file_id == file_id)
    )
    await session.execute(delete(Word).where(Word.file_id == file_id))
    await session.execute(delete(Sentence).where(Sentence.file_id == file_id))
    await session.execute(delete(Segment).where(Segment.file_id == file_id))
    await session.execute(
        delete(TopicAssignmentORM).where(
            TopicAssignmentORM.segment_id.like(f"seg_{file_id}_%")
        )
    )
    from bb_paxdata.infrastructure.db.models import SegmentAnalyzedEvent

    await session.execute(
        delete(SegmentAnalyzedEvent).where(SegmentAnalyzedEvent.file_id == file_id)
    )
    await session.execute(
        delete(TopicMatrixTable).where(TopicMatrixTable.file_id == file_id)
    )
    await session.execute(
        delete(TopicMatrixORM).where(TopicMatrixORM.file_id == file_id)
    )
    await session.execute(
        delete(CountryReferenceTable).where(CountryReferenceTable.file_id == file_id)
    )
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

    # Parse metadata headers
    metadata_lines, dialogue_lines = _parse_transcript_header_and_dialogue(file_content)

    file_title = metadata_lines.get("title") or file_path.stem
    file_date = metadata_lines.get("date") or "April 2026"
    file_theme = metadata_lines.get("theme") or "Diplomacy"

    try:
        file_number = int(metadata_lines.get("panel_number", ""))
    except ValueError:
        file_number = None

    file_speakers_metadata = {}
    if "speakers" in metadata_lines:
        file_speakers_metadata = parse_speakers_metadata(metadata_lines["speakers"])

    # Parse lines and group dialogue turns into segments
    segments_data: list[dict[str, Any]] = []
    current_speaker = None
    current_country = "unknown"
    current_sentences = []

    for line in dialogue_lines:
        line = line.strip()
        if not line:
            continue
        if " : " in line:
            parts = line.split(" : ", 1)
            speaker = parts[0].strip()
            text = parts[1].strip()
        elif ":" in line:
            parts = line.split(":", 1)
            speaker = parts[0].strip()
            text = parts[1].strip()
        elif current_speaker:
            speaker = current_speaker
            text = line
        else:
            speaker = "Interviewer"
            text = line

        # Parse speaker name and country code from text
        clean_name, country = clean_speaker_name_helper(speaker)

        if current_speaker is not None and clean_name != current_speaker:
            if current_sentences:
                segments_data.append(
                    {
                        "speaker": current_speaker,
                        "country": current_country,
                        "sentences": current_sentences,
                    }
                )
            current_sentences = []

        current_speaker = clean_name
        current_country = country
        tok_res = await container.tokenizer_service.tokenize(text)
        sents = tok_res.get("sentences", [text])
        current_sentences.extend(sents)

    if current_speaker and current_sentences:
        segments_data.append(
            {
                "speaker": current_speaker,
                "country": current_country,
                "sentences": current_sentences,
            }
        )

    # Ingest into DB
    # Create or update File early to avoid ForeignKey violations in child tables (e.g., PostgreSQL)
    file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    if existing:
        db_file = existing
        db_file.file_name = file_path.name
        db_file.title = file_title
        db_file.panel_number = file_number
        db_file.inferred_theme = file_theme
        db_file.date_str = file_date
        db_file.file_format = "new"
        db_file.file_hash = file_hash
        db_file.file_size_bytes = len(file_content.encode("utf-8"))
        db_file.last_processed_at = utc_now()
        db_file.reprocess_count += 1
        if force_rebuild:
            db_file.force_rebuild = 0
    else:
        db_file = File(
            file_id=file_id,
            file_name=file_path.name,
            title=file_title,
            panel_number=file_number,
            inferred_theme=file_theme,
            date_str=file_date,
            file_format="new",
            file_hash=file_hash,
            file_size_bytes=len(file_content.encode("utf-8")),
            idempotency_key=idempotency_key,
            parser_version=get_parser_version(),
            speaker_map_version=get_speaker_map_version(),
            first_processed_at=utc_now(),
            last_processed_at=utc_now(),
            reprocess_count=0,
            force_rebuild=0,
            n_segments=0,
            n_sentences=0,
            n_speakers=0,
            n_countries=0,
            total_words=0,
            imported_at=utc_now(),
        )
        session.add(db_file)
    await session.flush()

    trigger_service = AnalysisTriggerService(session, container, pipeline)
    res = await trigger_service.run_analysis(
        file_id=file_id,
        segments_data=segments_data,
        file_speakers_metadata=file_speakers_metadata,
    )
    if res not in ("skipped", "error"):
        db_file.record_event(
            event_type="FileIngested",
            payload={
                "file_name": db_file.file_name,
                "title": db_file.title,
                "panel_number": db_file.panel_number,
                "inferred_theme": db_file.inferred_theme,
                "file_hash": db_file.file_hash,
                "file_size_bytes": db_file.file_size_bytes,
                "idempotency_key": db_file.idempotency_key,
            },
            actor_id="system",
            aggregate_id=file_id,
        )
    return res


async def update_speaker_profiles(session: Any) -> None:
    # Fetch all speaker profiles
    speakers_res = await session.execute(select(SpeakerProfile))
    speakers = speakers_res.scalars().all()

    for sp in speakers:
        # Get all segments spoken by this speaker
        seg_stmt = select(Segment).where(Segment.speaker_id == sp.speaker_id)
        seg_res = await session.execute(seg_stmt)
        segments = seg_res.scalars().all()
        seg_ids = [s.seg_id for s in segments]

        # Get all sentences spoken by this speaker
        sent_stmt = select(Sentence).where(Sentence.speaker_id == sp.speaker_id)
        sent_res = await session.execute(sent_stmt)
        sentences = sent_res.scalars().all()

        # Get all words spoken by this speaker
        word_stmt = select(Word).where(Word.speaker_id == sp.speaker_id)
        word_res = await session.execute(word_stmt)
        words = [w.word_norm for w in word_res.scalars().all()]

        # Calculate basic counts
        sp.n_panels = len(set(s.file_id for s in sentences))
        sp.n_segments = len(segments)
        sp.n_sentences = len(sentences)
        sp.total_words = len(words)

        # Total duration
        sp.total_duration_sec = sum(s.duration_sec for s in segments if s.duration_sec)

        if sentences:
            # Average sentiment
            sentiments = [
                s.vader_compound for s in sentences if s.vader_compound is not None
            ]
            sp.avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            # Dominant emotion
            emotions = [s.emotion_category for s in sentences if s.emotion_category]
            sp.dominant_emotion = (
                Counter(emotions).most_common(1)[0][0] if emotions else None
            )

            # Dominant topic
            topics = [s.dominant_topic for s in sentences if s.dominant_topic]
            sp.dominant_topic = Counter(topics).most_common(1)[0][0] if topics else None

            # Behavioral percentages
            cooperative_cnt = sum(
                1 for s in sentences if s.emotion_category == "cooperative"
            )
            constructive_cnt = sum(
                1 for s in sentences if s.emotion_category == "constructive"
            )
            neutral_cnt = sum(
                1 for s in sentences if s.emotion_category == "neutral_cautious"
            )
            concerned_cnt = sum(
                1 for s in sentences if s.emotion_category == "concerned"
            )
            confrontational_cnt = sum(
                1 for s in sentences if s.emotion_category == "confrontational"
            )

            total_sents = len(sentences)
            sp.cooperative_pct = cooperative_cnt / total_sents if total_sents else 0.0
            sp.constructive_pct = constructive_cnt / total_sents if total_sents else 0.0
            sp.neutral_pct = neutral_cnt / total_sents if total_sents else 0.0
            sp.concerned_pct = concerned_cnt / total_sents if total_sents else 0.0
            sp.confrontational_pct = (
                confrontational_cnt / total_sents if total_sents else 0.0
            )

            # Risk event count
            sp.risk_event_count = sum(
                1 for s in sentences if s.risk_score and s.risk_score >= 7
            )

            # Top topics
            top_topics_list = [t[0] for t in Counter(topics).most_common(3)]
            sp.top_topics = ", ".join(top_topics_list) if top_topics_list else None

            # Average sentence length
            word_counts = [s.word_count for s in sentences if s.word_count]
            sp.avg_sentence_length = (
                sum(word_counts) / len(word_counts) if word_counts else 0.0
            )

            # Demand count
            sp.demand_count = sum(1 for s in sentences if s.demand_type is not None)

            # Rhetoric/pattern diversity
            rhetoric_types = {s.rhetoric_type for s in sentences if s.rhetoric_type}
            sp.pattern_diversity = len(rhetoric_types) / 5.0

            # Average hedging and politeness
            hedgings = [
                s.hedging_score for s in sentences if s.hedging_score is not None
            ]
            sp.avg_hedging_score = sum(hedgings) / len(hedgings) if hedgings else 0.0

            politeness_vals = [
                s.politeness_ratio for s in sentences if s.politeness_ratio is not None
            ]
            sp.avg_politeness_ratio = (
                sum(politeness_vals) / len(politeness_vals) if politeness_vals else 0.0
            )

            # Dominant frame and audience
            frames = [s.dominant_frame for s in sentences if s.dominant_frame]
            sp.dominant_frame = Counter(frames).most_common(1)[0][0] if frames else None

            audiences = [s.audience_type for s in sentences if s.audience_type]
            sp.dominant_audience = (
                Counter(audiences).most_common(1)[0][0] if audiences else None
            )

        # Average DKI score from segments
        if segments:
            dki_scores = [s.dki_score for s in segments if s.dki_score is not None]
            sp.avg_dki_score = sum(dki_scores) / len(dki_scores) if dki_scores else 0.0

        # Lexical diversity and diplo vocab score
        if words:
            sp.lexical_diversity = len(set(words)) / len(words)

            from bb_paxdata.application.domain.services.sentiment_service import (
                SentimentService,
            )

            diplo_words_cnt = sum(
                1 for w in words if w in SentimentService.DIPLO_LEXICON
            )
            sp.diplo_vocab_score = diplo_words_cnt / len(words)

        # Country references
        if seg_ids:
            from bb_paxdata.infrastructure.db.country_models import (
                CountryReferenceTable,
            )

            ref_stmt = (
                select(
                    CountryReferenceTable.referenced_country,
                    func.count(CountryReferenceTable.id),
                    func.avg(CountryReferenceTable.raw_sentiment_score),
                )
                .where(
                    CountryReferenceTable.file_id.in_(
                        list(set(s.file_id for s in segments))
                    ),
                    CountryReferenceTable.speaker_id == sp.speaker_id,
                )
                .group_by(CountryReferenceTable.referenced_country)
            )
            ref_res = await session.execute(ref_stmt)
            ref_rows = ref_res.all()

            top_countries = {}
            allies = {}
            adversaries = {}

            for to_country, mention_sum, avg_sent in ref_rows:
                if to_country and mention_sum:
                    top_countries[to_country] = int(mention_sum)
                    if avg_sent is not None:
                        if avg_sent >= 0.10:
                            allies[to_country] = int(mention_sum)
                        elif avg_sent <= -0.10:
                            adversaries[to_country] = int(mention_sum)

            sp.top_countries_mentioned = top_countries if top_countries else None
            sp.ally_countries = allies if allies else None
            sp.adversary_countries = adversaries if adversaries else None

        if not sp.first_seen_panel and sentences:
            sp.first_seen_panel = sentences[0].file_id


async def backfill_segment_events(session: Any) -> None:
    from bb_paxdata.application.domain.services.linguistic_helpers import (
        classify_speech_act,
        get_frame_distribution,
        get_vad_vector,
    )
    from bb_paxdata.infrastructure.db.models import Segment as SegmentORM
    from bb_paxdata.infrastructure.db.models import SegmentAnalyzedEvent
    from sqlalchemy import func, select

    # Check if segment_events is empty
    cnt_res = await session.execute(select(func.count(SegmentAnalyzedEvent.event_id)))
    cnt = cnt_res.scalar()
    if cnt > 0:
        return

    # Fetch all segments
    console.print(
        "Running migration backfill: converting legacy segments to event log..."
    )
    res = await session.execute(select(SegmentORM))
    segments = res.scalars().all()
    if not segments:
        return

    import uuid

    run_id = f"backfill_{uuid.uuid4().hex}"
    for s in segments:
        vad = get_vad_vector(s.diplo_compound or 0.0, s.emotion_category)
        act = classify_speech_act(s.text or "", s.demand_count or 0)
        frames = get_frame_distribution(s.text or "", s.dominant_frame)

        event = SegmentAnalyzedEvent(
            event_id=str(uuid.uuid4()),
            event_timestamp=utc_now(),
            file_id=s.file_id,
            segment_id=s.seg_id,
            country=s.country or "unknown",
            text_snippet=s.text,
            vader_compound=s.vader_compound or 0.0,
            diplo_compound=s.diplo_compound or 0.0,
            vad_vector=vad,
            emotion_category=s.emotion_category,
            risk_score=s.risk_score or 0.0,
            demand_count=s.demand_count or 0,
            speech_act=act,
            hedging_score=(
                s.avg_hedging_score if hasattr(s, "avg_hedging_score") else 0.0
            ),
            politeness_ratio=(
                s.avg_politeness_ratio if hasattr(s, "avg_politeness_ratio") else 0.0
            ),
            topic_scores=s.topic_scores or {},
            topic_model_version="bertopic_v1",
            frame_distribution=frames,
            pipeline_run_id=run_id,
        )
        session.add(event)
    await session.flush()
    console.print(
        f"[green][OK] Backfilled {len(segments)} segment events successfully.[/green]"
    )


async def update_country_stats(session: Any) -> None:
    from bb_paxdata.application.services.aggregation_engine import AggregationEngine
    from bb_paxdata.infrastructure.db.country_models import TopicMatrixTable
    from bb_paxdata.infrastructure.db.models import (
        ActorTopicDocument,
        ActorTopicProjection,
        CountryStat,
        SegmentAnalyzedEvent,
        TopicMatrix,
    )
    from sqlalchemy import delete, select

    # 1. Run backfill if necessary
    await backfill_segment_events(session)

    # 2. Clear existing projections, documents and stats
    await session.execute(delete(ActorTopicProjection))
    await session.execute(delete(ActorTopicDocument))
    await session.execute(delete(CountryStat))
    await session.execute(delete(TopicMatrix))
    await session.execute(delete(TopicMatrixTable))

    # 3. Load all events
    res = await session.execute(select(SegmentAnalyzedEvent))
    events = res.scalars().all()
    if not events:
        return

    # 4. Run Aggregation Engine
    engine = AggregationEngine()
    projections, documents = engine.aggregate_events(events)

    # 5. Persist Projections and Documents
    for proj in projections:
        session.add(proj)
    for doc in documents:
        session.add(doc)

    # 6. Rebuild legacy compatibility records (TopicMatrixTable, TopicMatrix, CountryStat)
    for doc in documents:
        if not doc.topic_details:
            continue

        dominant_topic = (
            max(doc.topic_details, key=lambda t: doc.topic_details[t])
            if doc.topic_details
            else None
        )
        topic_scores_compat = {t: val for t, val in doc.topic_details.items()}

        # Write to TopicMatrixTable (topic_matrices)
        tmt = TopicMatrixTable(
            file_id=doc.file_id,
            country=doc.country,
            topic_scores=topic_scores_compat,
            dominant_topic=dominant_topic,
            topic_details=doc.topic_details,
        )
        session.add(tmt)

        # Write to TopicMatrix (topic_matrix)
        for t, val in doc.topic_details.items():
            # Find the corresponding projection
            found_proj: ActorTopicProjection | None = next(
                (
                    p
                    for p in projections
                    if p.file_id == doc.file_id
                    and p.country == doc.country
                    and p.topic == t
                ),
                None,
            )
            if found_proj:
                tm = TopicMatrix(
                    file_id=doc.file_id,
                    country=doc.country,
                    topic=t,
                    score=val,
                    mention_count=found_proj.mention_count,
                    avg_sentiment=found_proj.avg_sentiment,
                    risk_score=found_proj.risk_score,
                    demand_count=int(found_proj.demand_count),
                    dominant_emotion=found_proj.dominant_emotion,
                    dominant_frame=found_proj.dominant_frame,
                )
                session.add(tm)

        # Extract stats for CountryStat
        actor_projs = [
            p
            for p in projections
            if p.file_id == doc.file_id and p.country == doc.country
        ]
        sents_s = [p.avg_sentiment for p in actor_projs]
        avg_s = sum(sents_s) / len(sents_s) if sents_s else 0.0

        emos = [p.dominant_emotion for p in actor_projs if p.dominant_emotion]
        dom_emo = max(set(emos), key=emos.count) if emos else None

        seg_count = actor_projs[0].segment_count if actor_projs else 0
        word_count = actor_projs[0].total_word_count if actor_projs else 0

        cs = CountryStat(
            country=doc.country,
            file_id=doc.file_id,
            n_segments=seg_count,
            total_words=word_count,
            avg_sentiment=avg_s,
            dominant_emotion=dom_emo,
            dominant_topic=dominant_topic,
            topic_scores=dict(
                sorted(
                    topic_scores_compat.items(), key=lambda item: item[1], reverse=True
                )[:5]
            ),
        )
        session.add(cs)

    await session.flush()


async def update_country_pair_sentiments(session: Any) -> None:
    from bb_paxdata.infrastructure.db.repositories.country_repository import (
        BilateralSentimentRepository,
    )

    repo = BilateralSentimentRepository(session)
    await repo.rebuild_global_country_pair_sentiments()


async def _async_build(
    data_dir: str,
    force_rebuild: bool,
    panel_filter: str | None,
    dry_run: bool,
    logic_only: bool = False,
    ai_limit: int | None = None,
) -> None:
    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]Data directory not found: {data_dir}")
        raise typer.Exit(1)

    validator = DataContractValidator()
    violation_logger = ViolationLogger()

    # Reset singleton so logic_mode / ai_limit change takes effect
    from bb_paxdata.infrastructure.container.service_container import (
        ServiceContainer as _SC,
    )

    _SC.reset_instance()
    container = _SC.get_instance(logic_mode=logic_only, ai_limit=ai_limit)
    pipeline = container.pipeline

    # Ensure tables are created
    await init_db()

    if logic_only:
        console.print(
            "[bold yellow]⚡ LOGIC-ONLY mod aktif — LLM/AI çağrısı yapılmayacak.[/bold yellow]"
        )
    elif ai_limit and ai_limit > 0:
        console.print(
            f"[bold cyan]⚡ AI LIMIT aktif — ilk {ai_limit} cümle AI'a gönderilecek, sonrası logic-only.[/bold cyan]"
        )

    async with get_session() as session:
        processed_count = 0
        skipped_count = 0
        error_count = 0

        # Find transcript files recursively in subfolders
        transcript_files = list(data_path.rglob("*.txt"))
        if panel_filter:
            transcript_files = [f for f in transcript_files if panel_filter in f.name]

        console.print(f"Found {len(transcript_files)} transcript files")

        for file_path in transcript_files:
            try:
                status = await _process_single_file(
                    session=session,
                    file_path=file_path,
                    force_rebuild=force_rebuild,
                    dry_run=dry_run,
                    validator=validator,
                    violation_logger=violation_logger,
                    container=container,
                    pipeline=pipeline,
                )
                if status == "processed":
                    processed_count += 1
                elif status == "skipped":
                    console.print(
                        f"[yellow][SKIP] Skipping {file_path.name} (already processed)"
                    )
                    skipped_count += 1
                elif status == "error":
                    error_count += 1
            except Exception as e:
                console.print(f"[red][ERROR] Error processing {file_path.name}: {e}")
                logger.error(f"Error processing file {file_path.name}", error=str(e))
                error_count += 1
                try:
                    await session.rollback()
                except Exception:
                    pass
                continue

        # Post-processing: Update Speaker stats
        console.print("Updating speaker statistics...")
        await update_speaker_profiles(session)
        console.print("Updating country statistics and topic matrices...")
        await update_country_stats(session)
        console.print("Rebuilding discourse network and flows for all files...")
        file_ids_res = await session.execute(select(File.file_id))
        file_ids = file_ids_res.scalars().all()
        for fid in file_ids:
            await rebuild_network_for_file(session, fid)
        console.print("Updating country pair sentiments...")
        await update_country_pair_sentiments(session)
        await session.commit()

        # Summary
        from bb_paxdata.infrastructure.observability.reporter import BuildReporter

        BuildReporter.print_summary(
            processed_count, skipped_count, error_count, container
        )


async def _async_watch(
    data_dir: str,
    poll_interval: int,
    logic_only: bool = False,
    ai_limit: int | None = None,
) -> None:
    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]Data directory not found: {data_dir}")
        raise typer.Exit(1)

    validator = DataContractValidator()
    violation_logger = ViolationLogger()

    # Reset singleton so logic_mode / ai_limit change takes effect
    from bb_paxdata.infrastructure.container.service_container import (
        ServiceContainer as _SC,
    )

    _SC.reset_instance()
    container = _SC.get_instance(logic_mode=logic_only, ai_limit=ai_limit)
    pipeline = container.pipeline

    if logic_only:
        console.print(
            "[bold yellow]⚡ LOGIC-ONLY mod aktif — LLM/AI çağrısı yapılmayacak.[/bold yellow]"
        )
    elif ai_limit and ai_limit > 0:
        console.print(
            f"[bold cyan]⚡ AI LIMIT aktif — ilk {ai_limit} cümle AI'a gönderilecek, sonrası logic-only.[/bold cyan]"
        )

    console.print(
        f"[bold green]👀 Monitoring directory for changes: [white]{data_path}[/white][/bold green]"
    )
    console.print(f"Polling interval: {poll_interval} seconds. Press Ctrl+C to stop.")

    known_files = {}

    # Pre-populate known files
    for file_path in data_path.rglob("*.txt"):
        try:
            known_files[file_path] = file_path.stat().st_mtime
        except Exception:
            pass

    console.print(f"Initial scan completed. Tracking {len(known_files)} files.")

    try:
        while True:
            await asyncio.sleep(poll_interval)

            current_files = {}
            for file_path in data_path.rglob("*.txt"):
                try:
                    current_files[file_path] = file_path.stat().st_mtime
                except Exception:
                    continue

            # Identify changes
            files_to_process = []
            for file_path, mtime in current_files.items():
                if file_path not in known_files or mtime > known_files[file_path]:
                    files_to_process.append(file_path)

            deleted_files = [f for f in known_files if f not in current_files]
            for f in deleted_files:
                console.print(f"[yellow][REMOVE] File removed from directory: {f.name}")
                del known_files[f]

            if not files_to_process:
                continue

            console.print(
                f"[bold blue]⚡ Detected {len(files_to_process)} changes. Processing...[/bold blue]"
            )

            async with get_session() as session:
                for file_path in files_to_process:
                    try:
                        status = await _process_single_file(
                            session=session,
                            file_path=file_path,
                            force_rebuild=False,
                            dry_run=False,
                            validator=validator,
                            violation_logger=violation_logger,
                            container=container,
                            pipeline=pipeline,
                        )
                        if status == "processed":
                            console.print(
                                f"[green][OK] Successfully processed and ingested: {file_path.name}"
                            )
                        elif status == "skipped":
                            console.print(
                                f"[yellow][SKIP] Skipped (already in DB): {file_path.name}"
                            )
                        elif status == "error":
                            console.print(
                                f"[red][ERROR] Processing failed: {file_path.name}"
                            )

                        # Update memory cache
                        known_files[file_path] = current_files[file_path]
                    except Exception as e:
                        console.print(
                            f"[red][ERROR] Error processing {file_path.name}: {e}"
                        )
                        known_files[file_path] = current_files[file_path]

                # Update speaker stats after changes
                console.print("Updating speaker statistics...")
                await update_speaker_profiles(session)
                console.print("Updating country statistics and topic matrices...")
                await update_country_stats(session)
                console.print("Rebuilding discourse network and flows for all files...")
                file_ids_res = await session.execute(select(File.file_id))
                file_ids = file_ids_res.scalars().all()
                for fid in file_ids:
                    await rebuild_network_for_file(session, fid)
                console.print("Updating country pair sentiments...")
                await update_country_pair_sentiments(session)
                await session.commit()

            console.print("[bold green]👀 Monitoring...[/bold green]")

    except asyncio.CancelledError:
        console.print("[yellow]Watcher stopped.[/yellow]")


@app.command()
def build(
    data_dir: str = typer.Argument(..., help="Directory containing transcript files"),
    force_rebuild: bool = typer.Option(
        False, "--force-rebuild", "-f", help="Force rebuild even if already processed"
    ),
    panel_filter: str | None = typer.Option(
        None, "--panel", "-p", help="Process only specific panel"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Show what would be processed without doing it"
    ),
    logic_only: bool = typer.Option(
        False,
        "--logic-only",
        "-L",
        help="LLM/AI çağrısı yapmadan kural tabanlı analiz yap (AI-free mod)",
    ),
    ai_limit: int | None = typer.Option(
        None,
        "--ai-limit",
        "-n",
        help="AI'a gönderilecek maksimum cümle sayısı (maliyet kontrolü). Örn: --ai-limit 50",
    ),
) -> None:
    """Build database from transcript files with duplicate protection."""
    try:
        asyncio.run(
            _async_build(
                data_dir=data_dir,
                force_rebuild=force_rebuild,
                panel_filter=panel_filter,
                dry_run=dry_run,
                logic_only=logic_only,
                ai_limit=ai_limit,
            )
        )
    except Exception as e:
        console.print(f"[red]Build failed: {e}")
        logger.error("Build command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("watch")
def watch(
    data_dir: str = typer.Argument(
        ..., help="Directory to monitor for transcript files"
    ),
    poll_interval: int = typer.Option(
        5, "--interval", "-i", help="Polling interval in seconds"
    ),
    logic_only: bool = typer.Option(
        False,
        "--logic-only",
        "-L",
        help="LLM/AI çağrısı yapmadan kural tabanlı analiz yap (AI-free mod)",
    ),
    ai_limit: int | None = typer.Option(
        None,
        "--ai-limit",
        "-n",
        help="AI'a gönderilecek maksimum cümle sayısı (maliyet kontrolü). Örn: --ai-limit 50",
    ),
) -> None:
    """Monitor a directory for new or modified transcript files and automatically ingest them."""
    try:
        asyncio.run(
            _async_watch(
                data_dir=data_dir,
                poll_interval=poll_interval,
                logic_only=logic_only,
                ai_limit=ai_limit,
            )
        )
    except Exception as e:
        console.print(f"[red]Watcher failed: {e}")
        logger.error("Watch command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("status")
def status(
    file_path: str = typer.Argument(..., help="Path to transcript file")
) -> None:
    """Check processing status of a specific file."""
    try:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]File not found: {file_path}")
            raise typer.Exit(1)

        # Read file content
        with open(path, encoding="utf-8") as f:
            file_content = f.read()

        # Calculate idempotency key
        idempotency_key = calculate_idempotency_key(
            file_content, path.name, get_parser_version(), get_speaker_map_version()
        )

        with get_db_session() as session:
            # Check processed files
            processed = (
                session.query(File)
                .filter(File.idempotency_key == idempotency_key)
                .first()
            )

            # Check panels
            file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
            panels = session.query(File).filter(File.file_hash == file_hash).all()

            console.print(f"File: {path.name}")
            console.print(f"Size: {len(file_content)} characters")
            console.print(f"Idempotency key: {idempotency_key}")
            console.print(f"File hash: {file_hash}")

            if processed:
                console.print(f"[green][OK] Processed: {processed.first_processed_at}")
                console.print(f"Reprocess count: {processed.reprocess_count}")
                console.print(f"Last processed: {processed.last_processed_at}")
                console.print(f"Parser version: {processed.parser_version}")
                console.print(f"Speaker map version: {processed.speaker_map_version}")
            else:
                console.print("[yellow][WAIT] Not processed yet")

            if panels:
                console.print(f"Associated panels: {len(panels)}")
                for panel in panels:
                    status = "Active" if getattr(panel, "is_active", 1) else "Inactive"
                    console.print(f"  - {panel.file_id} ({status})")
            else:
                console.print("No associated panels found")

    except Exception as e:
        console.print(f"[red]Status check failed: {e}")
        logger.error("Status command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("clean")
def clean(
    file_id: str | None = typer.Option(
        None, "--panel", "-p", help="Clean specific panel"
    ),
    older_than: int | None = typer.Option(
        None, "--older-than", "-o", help="Clean entries older than N days"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force cleanup without confirmation"
    ),
) -> None:
    """Clean processed files and panels."""
    try:
        with get_db_session() as session:
            if file_id:
                # Clean specific panel
                panels = (
                    session.query(File).filter(File.file_id.like(f"%{file_id}%")).all()
                )

                if not panels:
                    console.print(f"[yellow]No panels found matching: {file_id}")
                    return

                if not force:
                    if not typer.confirm(
                        f"Delete {len(panels)} panels matching '{file_id}'?"
                    ):
                        console.print("Cleanup cancelled")
                        return

                for panel in panels:
                    session.delete(panel)

                console.print(f"[green][OK] Deleted {len(panels)} panels")

            elif older_than:
                # Clean old processed files
                # This would require adding timestamp columns to processed_files
                console.print("[yellow]Age-based cleanup not yet implemented")

            else:
                console.print("[red]Must specify either --panel or --older-than")
                raise typer.Exit(1)

            session.commit()

    except Exception as e:
        console.print(f"[red]Cleanup failed: {e}")
        logger.error("Clean command failed", error=str(e))
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
