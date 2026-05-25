"""Build database command with duplicate protection and quality integration."""

import asyncio
import hashlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
import typer
from rich.console import Console
from sqlalchemy import delete, func, select

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from bb_paxdata.domain.services.risk_service import RiskService
from bb_paxdata.infrastructure.ai.fail_check import (
    AIFailCheck,
    ValidationStatus,
)
from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    AIFailAnalysis,
    AISentenceAnalysis,
    DemandRecord,
    Panel,
    PanelDynamics,
    PatternRecord,
    Segment,
    Sentence,
    Speaker,
    Word,
)
from bb_paxdata.infrastructure.db.processed_files import ProcessedFile
from bb_paxdata.infrastructure.db.repositories.analysis import AnalysisRepository
from bb_paxdata.infrastructure.db.session import get_db_session
from bb_paxdata.interfaces.cli.dependencies import get_session
from bb_paxdata.quality.data_contract import DataContractValidator
from bb_paxdata.quality.violations import ViolationLogger

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(help="Build database from transcript files")


# Mapping of speakers to country codes
SPEAKER_COUNTRY_MAP = {
    "Abdul Hamid": "PS",
    "Abdul Hamid Siyam": "PS",
    "Ahmed Al-Sharaa": "SY",
    "Andrii Sybiha": "UA",
    "André Corrêa do Lago": "BR",
    "Azali Assoumani": "KM",
    "Babatunde Ahonsi": "NG",
    "Baiba Braže": "LV",
    "Carl Skau": "SE",
    "Cevdet Yılmaz": "TR",
    "Daniel Levy": "UK",
    "David Moinina Sengeh": "SL",
    "Deniz Kilislioğlu": "TR",
    "Eda Özdemir": "TR",
    "Emile Hokayem": "LB",
    "Faisal Dawjee": "ZA",
    "Félix Antoine Tshisekedi": "CD",
    "Félix Ulloa": "SV",
    "Gordana Siljanovska-Davkova": "MK",
    "Gökhan Çeliker": "TR",
    "Hakan Fidan": "TR",
    "Hassan Sheikh Mohamud": "SO",
    "Hikmet Hajiyev": "AZ",
    "Irakli Kobakhidze": "GE",
    "Kassym-Jomart Tokayev": "KZ",
    "Keir Simmons": "UK",
    "Kemal Cebe": "TR",
    "Kęstutis Budrys": "LT",
    "Laurent Fabius": "FR",
    "Levent Gümrükçü": "TR",
    "Lizzie Porter": "UK",
    "Manolis Kostidis": "GR",
    "Marabski [Soyisim]": "PL",
    "Maria Fantappiè": "IT",
    "Mercy Bamola": "NG",
    "Mevlüt Çavuşoğlu": "TR",
    "Miloš Vučević": "RS",
    "Mukhtar Babayev": "AZ",
    "Murat Kurum": "TR",
    "Olga Osacheva": "BY",
    "Radmila Šekerinska": "MK",
    "Recep Tayyip Erdoğan": "TR",
    "Selwin Hart": "BB",
    "Sergei Lavrov": "RU",
    "Shayea Mohsin Al-Zindani": "YE",
    "Thomas Greminger": "CH",
    "Tom Barrack": "US",
    "Varsen Aghabekian": "PS",
    "Xəyalə Rəis": "AZ",
    "İsmail": "TR",
    "Əli Vəliyev": "AZ",
}

# Metadata mapping for the 12 files
PANELS_METADATA = {
    "01_Ahmed Al-Sharaa.txt": {
        "title": "Ahmed Al-Sharaa Interview",
        "date": "April 2026",
        "theme": "Syrian Reconstruction & Middle East Relations",
        "panel_number": 1,
    },
    "02_Cevdet Yılmaz.txt": {
        "title": "Cevdet Yılmaz Keynote Address",
        "date": "April 2026",
        "theme": "Turkish Economic Outlook & Regional Trade",
        "panel_number": 2,
    },
    "03_Erdoğan.txt": {
        "title": "Recep Tayyip Erdoğan Address",
        "date": "April 2026",
        "theme": "Global Diplomacy & Multipolar World Order",
        "panel_number": 3,
    },
    "04_Avrupa Başkanları.txt": {
        "title": "European Leaders Panel",
        "date": "April 2026",
        "theme": "Eurasian Security Architecture & Cooperation",
        "panel_number": 4,
    },
    "05_Gazze Konuşması.txt": {
        "title": "Gaza Crisis & Middle East Peace Panel",
        "date": "April 2026",
        "theme": "Conflict Resolution & Palestine Crisis",
        "panel_number": 5,
    },
    "06_Mevlüt Çavuşoğlu ve Cumhurbaşkanları.txt": {
        "title": "Regional Presidents Dialogue",
        "date": "April 2026",
        "theme": "Presidents Panel & Regional Connectivity",
        "panel_number": 6,
    },
    "07_Sergei Lavrov.txt": {
        "title": "Sergei Lavrov Interview",
        "date": "April 2026",
        "theme": "Russian Foreign Policy & Global Order Crises",
        "panel_number": 7,
    },
    "08_Somali.txt": {
        "title": "Somalia & Horn of Africa Security Panel",
        "date": "April 2026",
        "theme": "Maritime Security & East Africa Stability",
        "panel_number": 8,
    },
    "09_Tom Barrack.txt": {
        "title": "Tom Barrack Dialogue",
        "date": "April 2026",
        "theme": "US Middle East Policy & Investment",
        "panel_number": 9,
    },
    "10_Ukrayna Dışişleri Bakanı.txt": {
        "title": "Andrii Sybiha Interview",
        "date": "April 2026",
        "theme": "Ukraine Conflict & Security Guarantees",
        "panel_number": 10,
    },
    "11_Hakan Fidan.txt": {
        "title": "Hakan Fidan Foreign Policy Q&A",
        "date": "April 2026",
        "theme": "Turkish Mediation & Strategic Autonomy",
        "panel_number": 11,
    },
    "12_Climate.txt": {
        "title": "Climate Finance & Future COPs Panel",
        "date": "April 2026",
        "theme": "Climate Change, Energy Transition & Cooperation",
        "panel_number": 12,
    },
}


def clean_speaker_name_helper(speaker: str) -> tuple[str, str]:
    """Extract clean speaker name and existing country code if present, otherwise map it."""
    match = re.search(r"\(([^)]+)\)$|\[([^\]]+)\]$", speaker)
    if match:
        country = (match.group(1) or match.group(2)).strip().upper()
        clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker).strip()
        return clean_name, country

    clean_name = speaker.strip()
    country = SPEAKER_COUNTRY_MAP.get(clean_name, "unknown")
    return clean_name, country


def standardize_file_content(file_path: Path, file_content: str) -> str:
    """
    Standardize the raw transcript file content:
    - Adds metadata headers at the top if missing or incomplete.
    - Appends country code suffix to speakers.
    """
    lines = file_content.splitlines()
    metadata = {}
    line_idx = 0
    has_metadata = False

    while line_idx < len(lines):
        line = lines[line_idx].strip()
        if not line:
            line_idx += 1
            continue
        if line == "---":
            has_metadata = True
            line_idx += 1
            break
        if ":" in line and not any(
            line.startswith(x) for x in ["TITLE:", "DATE:", "THEME:", "PANEL_NUMBER:"]
        ):
            break

        if line.startswith("TITLE:"):
            metadata["title"] = line.split("TITLE:", 1)[1].strip()
        elif line.startswith("DATE:"):
            metadata["date"] = line.split("DATE:", 1)[1].strip()
        elif line.startswith("THEME:"):
            metadata["theme"] = line.split("THEME:", 1)[1].strip()
        elif line.startswith("PANEL_NUMBER:"):
            metadata["panel_number"] = line.split("PANEL_NUMBER:", 1)[1].strip()
        else:
            break
        line_idx += 1

    dialogue_lines = lines[line_idx:] if has_metadata else lines

    title = (
        metadata.get("title")
        or PANELS_METADATA.get(file_path.name, {}).get("title")
        or file_path.stem
    )
    date = (
        metadata.get("date")
        or PANELS_METADATA.get(file_path.name, {}).get("date")
        or "April 2026"
    )
    theme = (
        metadata.get("theme")
        or PANELS_METADATA.get(file_path.name, {}).get("theme")
        or "Diplomacy"
    )
    panel_number = (
        metadata.get("panel_number")
        or PANELS_METADATA.get(file_path.name, {}).get("panel_number")
        or ""
    )

    new_dialogue_lines = []
    for line in dialogue_lines:
        line_str = line.strip()
        if not line_str:
            new_dialogue_lines.append("")
            continue

        if " : " in line_str:
            parts = line_str.split(" : ", 1)
            speaker_part = parts[0].strip()
            text_part = parts[1].strip()
        elif ":" in line_str:
            parts = line_str.split(":", 1)
            speaker_part = parts[0].strip()
            text_part = parts[1].strip()
        else:
            new_dialogue_lines.append(line_str)
            continue

        clean_name, country = clean_speaker_name_helper(speaker_part)
        new_dialogue_lines.append(f"{clean_name} ({country}) : {text_part}")

    header_block = [
        f"TITLE: {title}",
        f"DATE: {date}",
        f"THEME: {theme}",
        f"PANEL_NUMBER: {panel_number}",
        "---",
    ]

    return "\n".join(header_block + new_dialogue_lines) + "\n"


def calculate_idempotency_key(
    file_content: str,
    file_name: str,
    parser_version: str = "5.8",
    speaker_map_version: str = "1.0",
) -> str:
    """Calculate idempotency key for file processing."""
    content_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    key_string = f"{content_hash}{file_name}{parser_version}{speaker_map_version}"
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


def get_parser_version() -> str:
    """Get current parser version."""
    return "5.8"  # Should match AIanalyst_v5_8 version


def get_speaker_map_version() -> str:
    """Get speaker map version hash."""
    return "1.0"


def resolve_country(speaker_name: str) -> str:
    # First check SPEAKER_COUNTRY_MAP
    clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker_name).strip()
    if clean_name in SPEAKER_COUNTRY_MAP:
        return SPEAKER_COUNTRY_MAP[clean_name]

    # Try exact match case-insensitive
    for name, code in SPEAKER_COUNTRY_MAP.items():
        if name.lower() == clean_name.lower():
            return code

    name_lower = clean_name.lower()
    if any(
        k in name_lower
        for k in [
            "erdoğan",
            "erdogan",
            "yılmaz",
            "yilmaz",
            "çavuşoğlu",
            "cavusoglu",
            "fidan",
            "türkiye",
            "turkey",
            "cevdet",
            "hakan",
            "mevlüt",
            "mevlut",
        ]
    ):
        return "TR"
    if any(k in name_lower for k in ["lavrov", "sergei", "russia", "rusya"]):
        return "RU"
    if any(k in name_lower for k in ["al-sharaa", "ahmed", "syria", "suriye"]):
        return "SY"
    if any(k in name_lower for k in ["ukrayna", "ukraine", "kiev", "kyiv", "sybiha"]):
        return "UA"
    if any(k in name_lower for k in ["somali", "somalia"]):
        return "SO"
    if any(
        k in name_lower
        for k in ["barrack", "tom", "usa", "america", "abd", "united states", "trump"]
    ):
        return "US"
    if any(k in name_lower for k in ["gazze", "palestine", "gaza", "filistin"]):
        return "PS"
    return "unknown"


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
                f"[yellow]⚠️ Failed to write standardized content back to {file_path.name}: {e}"
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
    stmt = select(ProcessedFile).where(ProcessedFile.idempotency_key == idempotency_key)
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing and not force_rebuild and existing.force_rebuild == 0:
        return "skipped"

    # Validate input
    validation_result = validator.validate_transcript_input(file_content, file_path)
    if not validation_result.passed:
        console.print(f"[red]❌ Input validation failed for {file_path.name}")
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

    # Panel ID from file stem
    panel_id = file_path.stem.lower().replace(" ", "_")

    # Clean existing data for this panel to support clean re-runs
    await session.execute(
        delete(AIFailAnalysis).where(AIFailAnalysis.panel_id == panel_id)
    )
    await session.execute(
        delete(HumanReviewQueue).where(HumanReviewQueue.panel_id == panel_id)
    )
    await session.execute(delete(DemandRecord).where(DemandRecord.panel_id == panel_id))
    await session.execute(
        delete(PatternRecord).where(PatternRecord.panel_id == panel_id)
    )
    await session.execute(
        delete(PanelDynamics).where(PanelDynamics.panel_id == panel_id)
    )
    await session.execute(
        delete(AISentenceAnalysis).where(AISentenceAnalysis.panel_id == panel_id)
    )
    await session.execute(delete(Word).where(Word.panel_id == panel_id))
    await session.execute(delete(Sentence).where(Sentence.panel_id == panel_id))
    await session.execute(delete(Segment).where(Segment.panel_id == panel_id))
    await session.execute(delete(Panel).where(Panel.panel_id == panel_id))

    # Parse metadata headers
    panel_title = file_path.stem
    panel_date = "April 2026"
    panel_theme = "Diplomacy"
    panel_number = None

    lines = file_content.splitlines()
    line_idx = 0
    has_metadata = False
    metadata_lines: dict[str, Any] = {}

    while line_idx < len(lines):
        line = lines[line_idx].strip()
        if not line:
            line_idx += 1
            continue
        if line == "---":
            has_metadata = True
            line_idx += 1
            break
        if ":" in line and not any(
            line.startswith(x) for x in ["TITLE:", "DATE:", "THEME:", "PANEL_NUMBER:"]
        ):
            break

        if line.startswith("TITLE:"):
            metadata_lines["title"] = line.split("TITLE:", 1)[1].strip()
        elif line.startswith("DATE:"):
            metadata_lines["date"] = line.split("DATE:", 1)[1].strip()
        elif line.startswith("THEME:"):
            metadata_lines["theme"] = line.split("THEME:", 1)[1].strip()
        elif line.startswith("PANEL_NUMBER:"):
            try:
                metadata_lines["panel_number"] = int(
                    line.split("PANEL_NUMBER:", 1)[1].strip()
                )
            except ValueError:
                pass
        else:
            break
        line_idx += 1

    if has_metadata:
        panel_title = metadata_lines.get("title", panel_title)
        panel_date = metadata_lines.get("date", panel_date)
        panel_theme = metadata_lines.get("theme", panel_theme)
        panel_number = metadata_lines.get("panel_number", panel_number)
        dialogue_lines = lines[line_idx:]
    else:
        dialogue_lines = lines

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
    total_sentences_count = 0
    total_words_in_file = 0
    unique_speakers_in_file = set()
    unique_countries_in_file = set()
    all_processed_sentences: list[Sentence] = []

    last_risk = 0
    last_sentiment = 0.0
    last_topic = None
    last_kgi = 0.0

    for seg_idx, seg in enumerate(segments_data, 1):
        speaker_name = seg["speaker"]
        speaker_id = speaker_name.lower().replace(" ", "_")
        unique_speakers_in_file.add(speaker_id)

        # Get or create speaker
        speaker_stmt = select(Speaker).where(Speaker.speaker_id == speaker_id)
        res = await session.execute(speaker_stmt)
        db_speaker = res.scalar_one_or_none()
        country = seg["country"]
        unique_countries_in_file.add(country)

        if not db_speaker:
            db_speaker = Speaker(
                speaker_id=speaker_id,
                full_name=speaker_name,
                country=country,
            )
            session.add(db_speaker)
            await session.flush()
        elif db_speaker.country == "unknown" and country != "unknown":
            db_speaker.country = country
            await session.flush()

        db_segment = Segment(
            seg_id=f"seg_{panel_id}_{seg_idx}",
            panel_id=panel_id,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            country=country,
            seq_order=seg_idx,
            text=" ".join(seg["sentences"]),
        )
        session.add(db_segment)
        await session.flush()

        db_sentences_in_seg = []

        for sent_idx, sentence_text in enumerate(seg["sentences"], 1):
            total_sentences_count += 1
            sent_id = f"sent_{panel_id}_{total_sentences_count}"

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
                panel_id=panel_id,
                speaker_country=country,
                speaker_power_level=0.5,
                metadata={
                    "panel_id": panel_id,
                    "speaker_id": speaker_id,
                    "speaker_country": country,
                },
                session=session,
            )

            words_count = (
                len(pipeline_res.analysis.tokens) if pipeline_res.analysis.tokens else 0
            )
            total_words_in_file += words_count

            # ── NLP Metrikleri: negation_aware_diplo, hedging_score, politeness_ratio ──
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
                for rs in _risk_sigs
                if hasattr(rs, "keyword")
                and rs.keyword
                in (
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
            )
            _hedging_score = (
                min(1.0, _hedging_keywords * 0.25) if _hedging_keywords else 0.0
            )

            # politeness_ratio: face_save / (face_save + face_threat + 1)
            _face_save = 0
            _face_threat = 0
            for rs in _risk_sigs:
                sig_name = getattr(rs, "keyword", "") or ""
                if any(
                    k in sig_name.lower()
                    for k in [
                        "please",
                        "lütfen",
                        "thank",
                        "teşekkür",
                        "respectfully",
                        "saygıyla",
                    ]
                ):
                    _face_save += 1
                if any(
                    k in sig_name.lower()
                    for k in [
                        "demand",
                        "threat",
                        "ultimatum",
                        "warn",
                        "tehdit",
                        "talep",
                    ]
                ):
                    _face_threat += 1
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

            db_sentence = Sentence(
                sent_id=sent_id,
                seg_id=db_segment.seg_id,
                panel_id=panel_id,
                speaker_id=speaker_id,
                speaker_name=speaker_name,
                country=country,
                sent_order=sent_idx,
                global_sent_order=total_sentences_count,
                text=sentence_text,
                word_count=words_count,
                char_count=len(sentence_text),
                vader_compound=_ai_sent,
                emotion_category=pipeline_res.analysis.ai_sentiment_label,
                dominant_topic=(
                    pipeline_res.analysis.topic_synthesis.topic_label
                    if (
                        pipeline_res.analysis.topic_synthesis
                        and pipeline_res.analysis.topic_synthesis.topic_label
                    )
                    else None
                ),
                risk_score=_normalized_risk,
                dominant_frame=(
                    str(pipeline_res.analysis.framing)
                    if pipeline_res.analysis.framing
                    else None
                ),
                negation_aware_diplo=_negation_aware_diplo,
                hedging_score=_hedging_score,
                politeness_ratio=_politeness_ratio,
                face_threat_count=_face_threat,
                face_save_count=_face_save,
                ai_analyzed=1,
                logic_result=_logic_result,
            )
            session.add(db_sentence)
            db_sentences_in_seg.append(db_sentence)
            all_processed_sentences.append(db_sentence)

            # Save AISentenceAnalysis
            ai_analysis = AISentenceAnalysis.from_domain(
                pipeline_res.analysis, sent_id=sent_id
            )
            ai_analysis.panel_id = panel_id
            ai_analysis.speaker_name = speaker_name
            ai_analysis.country = country
            ai_analysis.power_level = 0
            ai_analysis.global_sent_order = total_sentences_count
            ai_analysis.sentiment_score = _ai_sent
            ai_analysis.sentiment_category = pipeline_res.analysis.ai_sentiment_label
            ai_analysis.risk_score = _normalized_risk
            ai_analysis.ai_sentiment = pipeline_res.analysis.ai_sentiment_label
            ai_analysis.ai_risk_score = _normalized_risk
            ai_analysis.ai_frame_type = (
                str(pipeline_res.analysis.framing)
                if pipeline_res.analysis.framing
                else None
            )
            ai_analysis.hedging_score = _hedging_score
            ai_analysis.politeness_score = _politeness_ratio
            ai_analysis.logic_result = _logic_result
            session.add(ai_analysis)

            # ── AI Fail Check & Human Review Flagging Entegrasyonu ──
            # Calculate temporal values BEFORE updating last variables
            risk_d = _normalized_risk - last_risk
            emotion_s = _ai_sent - last_sentiment
            topic_c = (
                1
                if (
                    pipeline_res.analysis.topic_synthesis
                    and pipeline_res.analysis.topic_synthesis.topic_label != last_topic
                )
                else 0
            )
            kgi_score_sent = round(
                min(10.0, max(0.0, last_kgi * 0.85 + _normalized_risk * 0.15)), 4
            )
            formula_incons = round(abs(emotion_s) * 0.6 + topic_c * 0.4, 4)

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
                fail_checker = AIFailCheck()
                fail_check_res = fail_checker.validate_ai_response(
                    ai_resp_dict, formula_resp_dict
                )

                analysis_repo = AnalysisRepository(session)
                for val_res in fail_check_res.validation_results:
                    if val_res.status == ValidationStatus.FAIL:
                        # Build row data for LLM linguistic analysis
                        row_data = {
                            "speaker_name": speaker_name,
                            "country": country,
                            "power_level": 0,
                            "panel_id": panel_id,
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
                                formula_resp_dict.get(val_res.check_type.name.lower())
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
                                    str(x) for x in pipeline_res.analysis.anomaly_flags
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
                            ling_res = await fail_checker.analyze_fail_linguistically(
                                row_data
                            )

                        # Build AIFailAnalysis database model
                        db_fail = AIFailAnalysis(
                            sent_id=sent_id,
                            seg_id=db_segment.seg_id,
                            panel_id=panel_id,
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
                            processed_at=datetime.now(timezone.utc),
                        )

                        if ling_res:
                            db_fail.fail_reason = ling_res.get("AI_Neden_Fail")
                            db_fail.fail_category = ling_res.get("AI_Fail_Kategorisi")
                            db_fail.negation_type = ling_res.get("AI_Negasyon_Tipi")
                            db_fail.negation_scope = ling_res.get("AI_Negasyon_Kapsami")
                            db_fail.contextual_factor = ling_res.get(
                                "AI_Baglamsal_Faktor"
                            )
                            db_fail.temporal_factor = ling_res.get("AI_Temporal_Faktor")
                            db_fail.formula_gap = ling_res.get("AI_Formul_Eksigi")
                            db_fail.ai_misperception = ling_res.get("AI_AI_Yanilgisi")
                            db_fail.correction_suggestion = ling_res.get(
                                "AI_Duzeltme_Onerisi"
                            )
                            db_fail.comparative_correction = ling_res.get(
                                "AI_Karsilastirmali_Duzeltme"
                            )
                            db_fail.anomaly_link = ling_res.get("AI_Anomali_Baglantisi")
                            db_fail.linguistic_marker = ling_res.get(
                                "AI_Dilbilimsel_Marka"
                            )
                            db_fail.confidence_score = ling_res.get("AI_Guven_Skoru")
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
                    panel_id=panel_id,
                    speaker_name=speaker_name,
                    country=country,
                    trigger_type=trigger_type,
                    ai_risk_score=_normalized_risk,
                    anomaly_types=db_sentence.rhetoric_type,
                    uncertainty_score=0.0,
                    status="PENDING",
                    original_ai_json=_ai_json,
                    flagged_at=datetime.now(timezone.utc),
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
            _sentence_lower = sentence_text.lower()
            _detected_demand_verb = next(
                (v for v in _demand_verbs if v in _sentence_lower), None
            )
            if _detected_demand_verb:
                db_demand = DemandRecord(
                    sent_id=sent_id,
                    seg_id=db_segment.seg_id,
                    panel_id=panel_id,
                    speaker_name=speaker_name,
                    country=country,
                    power_level=0,
                    demand_verb=_detected_demand_verb,
                    demand_type=(
                        "explicit"
                        if _detected_demand_verb
                        in ("demand", "insist", "talep", "ısrar")
                        else "implicit"
                    ),
                    demand_weight=max(0.3, min(1.0, _normalized_risk / 10.0)),
                    target_entity=None,
                    demand_topic=(
                        pipeline_res.analysis.topic_synthesis.topic_label
                        if pipeline_res.analysis.topic_synthesis
                        else None
                    ),
                    full_sentence=sentence_text,
                    diplo_compound=_negation_aware_diplo,
                )
                session.add(db_demand)
                db_sentence.demand_type = db_demand.demand_type
                db_sentence.demand_weight = db_demand.demand_weight

            # ── Pattern Records: retorik kalıplar ──
            _rhetoric_patterns = {
                "conditional": ["if", "provided that", "eğer", "şayet", "koşuluyla"],
                "commitment": [
                    "we will",
                    "biz yapacağız",
                    "commit",
                    "taahhüt",
                    "pledge",
                ],
                "threat": ["otherwise", "consequences", "aksi halde", "sonuçları olur"],
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
                if any(kw in _sentence_lower for kw in _pkeywords):
                    db_pattern = PatternRecord(
                        sent_id=sent_id,
                        seg_id=db_segment.seg_id,
                        panel_id=panel_id,
                        speaker_name=speaker_name,
                        country=country,
                        power_level=0,
                        pattern_type=_ptype,
                        pattern_text=next(
                            (kw for kw in _pkeywords if kw in _sentence_lower), ""
                        ),
                        full_sentence=sentence_text,
                        dominant_topic=(
                            pipeline_res.analysis.topic_synthesis.topic_label
                            if pipeline_res.analysis.topic_synthesis
                            else None
                        ),
                        diplo_compound=_negation_aware_diplo,
                    )
                    session.add(db_pattern)
                    if not db_sentence.rhetoric_type:
                        db_sentence.rhetoric_type = _ptype
                    break  # İlk eşleşen kalıp yeterli

            # Populate words table
            if pipeline_res.analysis.tokens:
                STOP_WORDS = {
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
                for w_idx, token in enumerate(pipeline_res.analysis.tokens):
                    db_word = Word(
                        sent_id=sent_id,
                        seg_id=db_segment.seg_id,
                        panel_id=panel_id,
                        speaker_id=speaker_id,
                        speaker_name=speaker_name,
                        country=country,
                        word_raw=token,
                        word_norm=token.lower(),
                        word_position=w_idx,
                        is_stopword=token.lower() in STOP_WORDS,
                        diplo_score=0.0,
                        is_named_entity=False,
                    )
                    session.add(db_word)

        # Aggregate Segment fields in memory
        vaders = [
            s.vader_compound
            for s in db_sentences_in_seg
            if s.vader_compound is not None
        ]
        db_segment.vader_compound = sum(vaders) / len(vaders) if vaders else 0.0

        risks = [s.risk_score for s in db_sentences_in_seg if s.risk_score is not None]
        db_segment.risk_score = max(risks) if risks else 0
        db_segment.sbi_score = db_segment.vader_compound or 0.0
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
        db_segment.dominant_topic = (
            Counter(topics).most_common(1)[0][0] if topics else None
        )

        db_segment.word_count = sum(s.word_count for s in db_sentences_in_seg)
        db_segment.sentence_count = len(db_sentences_in_seg)

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

    # Save Panel ORM
    file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
    db_panel = Panel(
        panel_id=panel_id,
        file_name=file_path.name,
        title=panel_title,
        panel_number=panel_number,
        inferred_theme=panel_theme,
        date_str=panel_date,
        file_format="new",
        file_hash=file_hash,
        n_segments=len(segments_data),
        n_sentences=total_sentences_count,
        n_speakers=len(unique_speakers_in_file),
        n_countries=len(unique_countries_in_file),
        total_words=total_words_in_file,
        imported_at=datetime.now(timezone.utc),
    )
    session.add(db_panel)

    # ── Panel Dynamics: cümle bazlı temporal değişim kayıtları ──
    # Tüm segment döngülerinden toplanan cümleleri sıralı şekilde işle
    _all_built_sentences = all_processed_sentences

    _prev_risk_dyn: int = 0
    _prev_sentiment_dyn: float = 0.0
    _prev_topic_dyn: str | None = None
    for dyn_pos, dyn_sent in enumerate(_all_built_sentences, 1):
        _risk_d = (dyn_sent.risk_score or 0) - _prev_risk_dyn
        _sent_d = (dyn_sent.vader_compound or 0.0) - _prev_sentiment_dyn
        _topic_changed = (
            1
            if (dyn_sent.dominant_topic and dyn_sent.dominant_topic != _prev_topic_dyn)
            else 0
        )
        # KGI = abs(risk_delta) * 0.4 + abs(emotion_shift) * 0.3 + topic_shift * 0.3
        _kgi = abs(_risk_d / 10.0) * 0.4 + abs(_sent_d) * 0.3 + _topic_changed * 0.3

        db_dyn = PanelDynamics(
            panel_id=panel_id,
            position=dyn_pos,
            speaker_name=dyn_sent.speaker_name,
            country=dyn_sent.country,
            kgi_score=round(_kgi, 4),
            risk_delta=round(_risk_d, 2),
            emotion_shift=round(_sent_d, 4),
            topic_shift=_topic_changed,
            inconsistency_score=0.0,
            sent_id=dyn_sent.sent_id,
        )
        session.add(db_dyn)

        _prev_risk_dyn = dyn_sent.risk_score or 0
        _prev_sentiment_dyn = dyn_sent.vader_compound or 0.0
        _prev_topic_dyn = dyn_sent.dominant_topic

    # Update processed files tracking
    if existing:
        existing.reprocess_count += 1
        existing.last_processed_at = datetime.now(timezone.utc)
        if force_rebuild:
            existing.force_rebuild = 0
    else:
        processed_file = ProcessedFile(
            file_hash=file_hash,
            file_name=file_path.name,
            file_size_bytes=len(file_content.encode("utf-8")),
            idempotency_key=idempotency_key,
            parser_version=get_parser_version(),
            speaker_map_version=get_speaker_map_version(),
            first_processed_at=datetime.now(timezone.utc),
            last_processed_at=datetime.now(timezone.utc),
            reprocess_count=0,
            force_rebuild=0,
        )
        session.add(processed_file)

    await session.flush()
    return "processed"


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
                        f"[yellow]⏭️  Skipping {file_path.name} (already processed)"
                    )
                    skipped_count += 1
                elif status == "error":
                    error_count += 1
            except Exception as e:
                console.print(f"[red]❌ Error processing {file_path.name}: {e}")
                logger.error(f"Error processing file {file_path.name}", error=str(e))
                error_count += 1
                continue

        # Post-processing: Update Speaker stats
        console.print("Updating speaker statistics...")
        speakers_res = await session.execute(select(Speaker))
        speakers = speakers_res.scalars().all()
        for sp in speakers:
            # count panels
            panels_count = (
                await session.execute(
                    select(func.count(func.distinct(Sentence.panel_id))).where(
                        Sentence.speaker_id == sp.speaker_id
                    )
                )
            ).scalar()
            sp.n_panels = panels_count or 0

            # count segments
            segs_count = (
                await session.execute(
                    select(func.count(Segment.seg_id)).where(
                        Segment.speaker_id == sp.speaker_id
                    )
                )
            ).scalar()
            sp.n_segments = segs_count or 0

            # count sentences
            sents_count = (
                await session.execute(
                    select(func.count(Sentence.sent_id)).where(
                        Sentence.speaker_id == sp.speaker_id
                    )
                )
            ).scalar()
            sp.n_sentences = sents_count or 0

            # total words
            words_count = (
                await session.execute(
                    select(func.sum(Sentence.word_count)).where(
                        Sentence.speaker_id == sp.speaker_id
                    )
                )
            ).scalar()
            sp.total_words = words_count or 0

            # avg sentiment
            avg_sent = (
                await session.execute(
                    select(func.avg(Sentence.vader_compound)).where(
                        Sentence.speaker_id == sp.speaker_id
                    )
                )
            ).scalar()
            sp.avg_sentiment = float(avg_sent) if avg_sent is not None else 0.0

        # Summary
        console.print("\n[green]✅ Build completed!")
        console.print(f"Processed: {processed_count}")
        console.print(f"Skipped: {skipped_count}")
        console.print(f"Errors: {error_count}")

        # AI kullanım raporu (LimitedAIAnalyst aktifse)
        if hasattr(container.ai_analyst, "get_usage_summary"):
            usage = container.ai_analyst.get_usage_summary()
            console.print("\n[bold cyan]📊 AI Kullanım Raporu:[/bold cyan]")
            console.print(f"  AI çağrısı yapılan cümle: {usage['ai_calls_made']}")
            console.print(f"  AI limiti:               {usage['ai_limit']}")
            console.print(f"  Kalan hak:               {usage['remaining']}")
            if usage["is_exhausted"]:
                console.print(
                    "  [yellow]⚠️  Limit doldu — sonraki cümleler logic-only ile analiz edildi.[/yellow]"
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
                console.print(f"[yellow]🗑️ File removed from directory: {f.name}")
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
                                f"[green]✅ Successfully processed and ingested: {file_path.name}"
                            )
                        elif status == "skipped":
                            console.print(
                                f"[yellow]⏭️ Skipped (already in DB): {file_path.name}"
                            )
                        elif status == "error":
                            console.print(
                                f"[red]❌ Processing failed: {file_path.name}"
                            )

                        # Update memory cache
                        known_files[file_path] = current_files[file_path]
                    except Exception as e:
                        console.print(f"[red]❌ Error processing {file_path.name}: {e}")
                        known_files[file_path] = current_files[file_path]

                # Update speaker stats after changes
                console.print("Updating speaker statistics...")
                speakers_res = await session.execute(select(Speaker))
                speakers = speakers_res.scalars().all()
                for sp in speakers:
                    panels_count = (
                        await session.execute(
                            select(func.count(func.distinct(Sentence.panel_id))).where(
                                Sentence.speaker_id == sp.speaker_id
                            )
                        )
                    ).scalar()
                    sp.n_panels = panels_count or 0

                    segs_count = (
                        await session.execute(
                            select(func.count(Segment.seg_id)).where(
                                Segment.speaker_id == sp.speaker_id
                            )
                        )
                    ).scalar()
                    sp.n_segments = segs_count or 0

                    sents_count = (
                        await session.execute(
                            select(func.count(Sentence.sent_id)).where(
                                Sentence.speaker_id == sp.speaker_id
                            )
                        )
                    ).scalar()
                    sp.n_sentences = sents_count or 0

                    words_count = (
                        await session.execute(
                            select(func.sum(Sentence.word_count)).where(
                                Sentence.speaker_id == sp.speaker_id
                            )
                        )
                    ).scalar()
                    sp.total_words = words_count or 0

                    avg_sent = (
                        await session.execute(
                            select(func.avg(Sentence.vader_compound)).where(
                                Sentence.speaker_id == sp.speaker_id
                            )
                        )
                    ).scalar()
                    sp.avg_sentiment = float(avg_sent) if avg_sent is not None else 0.0

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
                session.query(ProcessedFile)
                .filter(ProcessedFile.idempotency_key == idempotency_key)
                .first()
            )

            # Check panels
            file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
            panels = session.query(Panel).filter(Panel.file_hash == file_hash).all()

            console.print(f"File: {path.name}")
            console.print(f"Size: {len(file_content)} characters")
            console.print(f"Idempotency key: {idempotency_key}")
            console.print(f"File hash: {file_hash}")

            if processed:
                console.print(f"[green]✅ Processed: {processed.first_processed_at}")
                console.print(f"Reprocess count: {processed.reprocess_count}")
                console.print(f"Last processed: {processed.last_processed_at}")
                console.print(f"Parser version: {processed.parser_version}")
                console.print(f"Speaker map version: {processed.speaker_map_version}")
            else:
                console.print("[yellow]⏳ Not processed yet")

            if panels:
                console.print(f"Associated panels: {len(panels)}")
                for panel in panels:
                    status = "Active" if getattr(panel, "is_active", 1) else "Inactive"
                    console.print(f"  - {panel.panel_id} ({status})")
            else:
                console.print("No associated panels found")

    except Exception as e:
        console.print(f"[red]Status check failed: {e}")
        logger.error("Status command failed", error=str(e))
        raise typer.Exit(1) from e


@app.command("clean")
def clean(
    panel_id: str | None = typer.Option(
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
            if panel_id:
                # Clean specific panel
                panels = (
                    session.query(Panel)
                    .filter(Panel.panel_id.like(f"%{panel_id}%"))
                    .all()
                )

                if not panels:
                    console.print(f"[yellow]No panels found matching: {panel_id}")
                    return

                if not force:
                    if not typer.confirm(
                        f"Delete {len(panels)} panels matching '{panel_id}'?"
                    ):
                        console.print("Cleanup cancelled")
                        return

                for panel in panels:
                    session.delete(panel)

                console.print(f"[green]✅ Deleted {len(panels)} panels")

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
