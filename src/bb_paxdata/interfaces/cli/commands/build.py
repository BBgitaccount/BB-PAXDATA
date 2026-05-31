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

from bb_paxdata.domain.enums.demand_category import DemandCategory
from bb_paxdata.domain.services.risk_service import RiskService
from bb_paxdata.domain.utils.hash import generate_sentence_code
from bb_paxdata.infrastructure.ai.fail_check import (
    AIFailCheck,
    ValidationStatus,
)
from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    AIFailAnalysis,
    AISentenceAnalysis,
    DemandRecord,
    DiscourseNetworkEdge,
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
from bb_paxdata.infrastructure.db.session import get_db_session, init_db
from bb_paxdata.infrastructure.logic.formula_auditor import FormulaAuditor
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

SPEAKER_MAP = {
    # ── TÜRKİYE ────────────────────────────────────────────────────────
    "Recep Tayyip Erdoğan": ("Turkey", "President", "head_of_state"),
    "Cevdet Yılmaz": ("Turkey", "Vice President", "vice_president"),
    "Hakan Fidan": ("Turkey", "Minister of Foreign Affairs", "minister"),
    "Murat Kurum": (
        "Turkey",
        "Minister of Environment, Urbanization and Climate",
        "minister",
    ),
    "Levent Gümrükçü": (
        "Turkey",
        "Deputy Minister of Foreign Affairs",
        "deputy_minister",
    ),
    "Mevlüt Çavuşoğlu": ("Turkey", "Member of Parliament for Antalya", "moderator"),
    "Deniz Kilislioğlu": ("Turkey", "Journalist", "journalist"),
    "Eda Özdemir": ("Turkey", "Journalist", "journalist"),
    "Gökhan Çeliker": ("Turkey", "Journalist", "journalist"),
    "Kemal Cebe": ("Turkey", "Participant", "panelist"),
    # ── DEVLET / HÜKÜMET BAŞKANLARI ────────────────────────────────────
    "Ahmed Al Sharaa": ("Syria", "President", "head_of_state"),
    "Azali Assoumani": ("Comoros", "President", "head_of_state"),
    "Evariste Ndayishimiye": ("Burundi", "President", "head_of_state"),
    "Felix Antoine Tshisekedi": (
        "Democratic Republic of the Congo",
        "President",
        "head_of_state",
    ),
    "Gordana Siljanovska Davkova": ("North Macedonia", "President", "head_of_state"),
    "Gordana Siljanovska-Davkova": ("North Macedonia", "President", "head_of_state"),
    "Hasan Şeyh Mahmud": ("Somalia", "President", "head_of_state"),
    "Hassan Sheikh Mohamud": ("Somalia", "President", "head_of_state"),
    "Kasım Cömert Tokayev": ("Kazakhstan", "President", "head_of_state"),
    "Kassym-Jomart Tokayev": ("Kazakhstan", "President", "head_of_state"),
    "David Moinina Sengeh": ("Sierra Leone", "Chief Minister", "head_of_government"),
    "İrakli Kobakhidze": ("Georgia", "Prime Minister", "head_of_government"),
    "Irakli Kobakhidze": ("Georgia", "Prime Minister", "head_of_government"),
    "Miloş Vuçeviç": ("Serbia", "Prime Minister", "head_of_government"),
    "Miloş Vučević": ("Serbia", "Prime Minister", "head_of_government"),
    "Şayi Muhsin ez-Zindani": ("Yemen", "Prime Minister", "head_of_government"),
    "Shayea Mohsin Al-Zindani": ("Yemen", "Prime Minister", "head_of_government"),
    "Felix Ulloa": ("El Salvador", "Vice President", "vice_president"),
    # ── BAKANLAR ───────────────────────────────────────────────────────
    "Andriy Sibiha": ("Ukraine", "Minister of Foreign Affairs", "minister"),
    "Andrii Sybiha": ("Ukraine", "Minister of Foreign Affairs", "minister"),
    "Baiba Braže": ("Latvia", "Minister of Foreign Affairs", "minister"),
    "Kestutis Budrys": ("Lithuania", "Minister of Foreign Affairs", "minister"),
    "Muhtar Babayev": (
        "Azerbaijan",
        "Minister of Ecology and Natural Resources",
        "minister",
    ),
    "Sergey Lavrov": ("Russia", "Minister of Foreign Affairs", "minister"),
    "Sergei Lavrov": ("Russia", "Minister of Foreign Affairs", "minister"),
    "Varsen Aghabekian": (
        "Palestine",
        "Minister of State for Foreign Affairs",
        "minister",
    ),
    # ── DİPLOMAT / UZMAN / DİĞER / BASIN ───────────────────────────────
    "Hikmet Hacıyev": ("Azerbaijan", "Senior Advisor to President", "advisor"),
    "Hikmet Hajiyev": ("Azerbaijan", "Senior Advisor to President", "advisor"),
    "Andre Correa do Lago": (
        "Brazil",
        "Secretary for Climate / Ambassador",
        "diplomat",
    ),
    "Babatunde Ahonsi": ("UN", "Resident Coordinator in Türkiye", "intl_official"),
    "Carl Skau": ("UN", "Deputy Exec. Dir. WFP", "intl_official"),
    "Laurent Fabius": (
        "France",
        "Former Prime Minister / President of COP21",
        "expert",
    ),
    "Radmila Šekerinska": ("NATO", "Deputy Secretary General", "intl_official"),
    "Selwin Hart": ("UN", "Special Adviser on Climate Action", "intl_official"),
    "Tom Barrack": ("United States", "US Ambassador", "diplomat"),
    "Thomas Greminger": ("Switzerland", "Director of GCSP", "moderator"),
    "Abdul Hamid": ("United States", "UN Correspondent", "journalist"),
    "Abdul Hamid Siyam": ("United States", "UN Correspondent", "journalist"),
    "Daniel Levy": ("United Kingdom", "President of USMEP", "expert"),
    "Emile Hokayem": ("Lebanon", "Director of Regional Security at IISS", "expert"),
    "Faisal Dawjee": (
        "South Africa",
        "Former Media Director for SA Government",
        "expert",
    ),
    "Keir Simmons": (
        "United Kingdom",
        "Chief International Correspondent at NBC",
        "journalist",
    ),
    "Lizzie Porter": ("United Kingdom", "Journalist", "journalist"),
    "Manolis Kostidis": ("Greece", "Journalist", "journalist"),
    "Maria Fantappiè": ("Italy", "Expert", "expert"),
    "Xəyalə Rəis": ("Azerbaijan", "Journalist", "journalist"),
    # ── GENEL / İSİMSİZ ────────────────────────────────────────────────
    "Basın Mensubu": ("Unknown", "Press Member", "journalist"),
    "Dinleyici Bir": ("Unknown", "Audience Member", "panelist"),
    "Dinleyici İki": ("Unknown", "Audience Member", "panelist"),
    "Interviewer": ("Unknown", "Interviewer", "moderator"),
    "Moderator": ("Unknown", "Moderator", "moderator"),
    "Moderatör": ("Unknown", "Moderator", "moderator"),
    "Mülakatçı": ("Unknown", "Interviewer", "moderator"),
    "Marabski [Soyisim]": ("Poland", "Participant", "panelist"),
    "Mercy Bamola": ("Nigeria", "Participant", "panelist"),
    "Olga Osacheva": ("Belarus", "Participant", "panelist"),
    "İsmail": ("Turkey", "Participant", "panelist"),
    "Əli Vəliyev": ("Azerbaijan", "Participant", "panelist"),
}

BLOC_MAP = {
    "Turkey": "Eurasian",
    "Kazakhstan": "Central Asia",
    "North Macedonia": "Balkans",
    "Georgia": "Caucasus",
    "Somalia": "Africa",
    "Syria": "MENA",
    "Russia": "Eurasian",
    "United States": "West",
    "Ukraine": "Eurasian",
    "Azerbaijan": "Caucasus",
    "Serbia": "Balkans",
    "Latvia": "Europe",
    "Lithuania": "Europe",
    "Palestine": "MENA",
    "Yemen": "MENA",
    "Burundi": "Africa",
    "Democratic Republic of the Congo": "Africa",
    "Sierra Leone": "Africa",
    "Comoros": "Africa",
    "El Salvador": "Central America",
    "NATO": "West",
    "UN": "International",
    "Switzerland": "Europe",
    "France": "Europe",
    "Brazil": "Global South",
    "Iran": "MENA",
    "Israel": "MENA",
    "China": "Asia",
    "EU": "Europe",
    "Saudi Arabia": "MENA",
    "Qatar": "MENA",
    "United Arab Emirates": "MENA",
    "United Kingdom": "West",
    "Greece": "Europe",
    "Italy": "Europe",
    "Poland": "Europe",
    "Belarus": "Eurasian",
    "Sweden": "Europe",
    "Nigeria": "Africa",
    "South Africa": "Africa",
    "Lebanon": "MENA",
    "Barbados": "Global South",
}

COUNTRY_NORM_MAP = {
    "TR": "Turkey",
    "TURKEY": "Turkey",
    "TÜRKİYE": "Turkey",
    "US": "United States",
    "USA": "United States",
    "UNITED STATES": "United States",
    "RU": "Russia",
    "RUSSIA": "Russia",
    "RUSYA": "Russia",
    "UA": "Ukraine",
    "UKRAINE": "Ukraine",
    "UKRAYNA": "Ukraine",
    "AZ": "Azerbaijan",
    "AZERBAIJAN": "Azerbaijan",
    "GR": "Greece",
    "GREECE": "Greece",
    "IT": "Italy",
    "ITALY": "Italy",
    "RS": "Serbia",
    "SERBIA": "Serbia",
    "PL": "Poland",
    "POLAND": "Poland",
    "BY": "Belarus",
    "BELARUS": "Belarus",
    "CH": "Switzerland",
    "SWITZERLAND": "Switzerland",
    "YE": "Yemen",
    "YEMEN": "Yemen",
    "CD": "Democratic Republic of the Congo",
    "DRC": "Democratic Republic of the Congo",
    "CONGO": "Democratic Republic of the Congo",
    "KM": "Comoros",
    "COMOROS": "Comoros",
    "SO": "Somalia",
    "SOMALIA": "Somalia",
    "GE": "Georgia",
    "GEORGIA": "Georgia",
    "KZ": "Kazakhstan",
    "KAZAKHSTAN": "Kazakhstan",
    "LT": "Lithuania",
    "LITHUANIA": "Lithuania",
    "FR": "France",
    "FRANCE": "France",
    "ZA": "South Africa",
    "SOUTH AFRICA": "South Africa",
    "SL": "Sierra Leone",
    "SIERRA LEONE": "Sierra Leone",
    "SV": "El Salvador",
    "EL SALVADOR": "El Salvador",
    "LB": "Lebanon",
    "LEBANON": "Lebanon",
    "BB": "Barbados",
    "BARBADOS": "Barbados",
    "PS": "Palestine",
    "PALESTINE": "Palestine",
    "SY": "Syria",
    "SYRIA": "Syria",
    "BR": "Brazil",
    "BRAZIL": "Brazil",
    "NG": "Nigeria",
    "NIGERIA": "Nigeria",
    "LV": "Latvia",
    "LATVIA": "Latvia",
    "SE": "Sweden",
    "SWEDEN": "Sweden",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "UNITED KINGDOM": "United Kingdom",
    "AE": "United Arab Emirates",
    "UAE": "United Arab Emirates",
    "UNITED ARAB EMIRATES": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "SAUDI ARABIA": "Saudi Arabia",
    "QA": "Qatar",
    "QATAR": "Qatar",
    "IR": "Iran",
    "IRAN": "Iran",
    "IL": "Israel",
    "ISRAEL": "Israel",
    "CN": "China",
    "CHINA": "China",
}

POWER_LEVELS = {
    "head_of_state": 10,
    "head_of_government": 9,
    "vice_president": 8,
    "minister": 7,
    "deputy_minister": 6,
    "intl_official": 7,
    "diplomat": 6,
    "advisor": 5,
    "expert": 4,
    "moderator": 3,
    "journalist": 2,
    "panelist": 3,
}


def power_to_tier(power: int) -> str:
    if power >= 9:
        return "TIER1_SOVEREIGN"
    elif power >= 7:
        return "TIER2_MINISTER"
    elif power >= 5:
        return "TIER3_OFFICIAL"
    elif power >= 3:
        return "TIER4_EXPERT"
    else:
        return "TIER5_MEDIA"


# Metadata mapping for the 12 files
PANELS_METADATA = {
    "01_Ahmed Al-Sharaa.txt": {
        "title": "Ahmed Al-Sharaa Interview",
        "date": "April 2026",
        "theme": "Syrian Reconstruction & Middle East Relations",
        "file_number": 1,
    },
    "02_Cevdet Yılmaz.txt": {
        "title": "Cevdet Yılmaz Keynote Address",
        "date": "April 2026",
        "theme": "Turkish Economic Outlook & Regional Trade",
        "file_number": 2,
    },
    "03_Erdoğan.txt": {
        "title": "Recep Tayyip Erdoğan Address",
        "date": "April 2026",
        "theme": "Global Diplomacy & Multipolar World Order",
        "file_number": 3,
    },
    "04_Avrupa Başkanları.txt": {
        "title": "European Leaders File",
        "date": "April 2026",
        "theme": "Eurasian Security Architecture & Cooperation",
        "file_number": 4,
    },
    "05_Gazze Konuşması.txt": {
        "title": "Gaza Crisis & Middle East Peace File",
        "date": "April 2026",
        "theme": "Conflict Resolution & Palestine Crisis",
        "file_number": 5,
    },
    "06_Mevlüt Çavuşoğlu ve Cumhurbaşkanları.txt": {
        "title": "Regional Presidents Dialogue",
        "date": "April 2026",
        "theme": "Presidents File & Regional Connectivity",
        "file_number": 6,
    },
    "07_Sergei Lavrov.txt": {
        "title": "Sergei Lavrov Interview",
        "date": "April 2026",
        "theme": "Russian Foreign Policy & Global Order Crises",
        "file_number": 7,
    },
    "08_Somali.txt": {
        "title": "Somalia & Horn of Africa Security File",
        "date": "April 2026",
        "theme": "Maritime Security & East Africa Stability",
        "file_number": 8,
    },
    "09_Tom Barrack.txt": {
        "title": "Tom Barrack Dialogue",
        "date": "April 2026",
        "theme": "US Middle East Policy & Investment",
        "file_number": 9,
    },
    "10_Ukrayna Dışişleri Bakanı.txt": {
        "title": "Andrii Sybiha Interview",
        "date": "April 2026",
        "theme": "Ukraine Conflict & Security Guarantees",
        "file_number": 10,
    },
    "11_Hakan Fidan.txt": {
        "title": "Hakan Fidan Foreign Policy Q&A",
        "date": "April 2026",
        "theme": "Turkish Mediation & Strategic Autonomy",
        "file_number": 11,
    },
    "12_Climate.txt": {
        "title": "Climate Finance & Future COPs File",
        "date": "April 2026",
        "theme": "Climate Change, Energy Transition & Cooperation",
        "file_number": 12,
    },
}


def turkish_lower(text: str) -> str:
    """Correctly lowercases Turkish text by mapping I -> ı and İ -> i properly."""
    mapped = []
    for char in text:
        if char == "I":
            mapped.append("ı")
        elif char == "İ":
            mapped.append("i")
        else:
            mapped.append(char.lower())
    return "".join(mapped)


def _extract_target_entity(
    sentence_text: str,
    entities: list[dict[str, Any]],
    speaker_name: str,
    country: str,
) -> str | None:
    """Extracts the target geopolitical entity or organization (e.g. GPE, ORG) from a sentence.

    Filters out the speaker's own country and name.
    """
    speaker_lower = speaker_name.lower().strip()
    country_lower = country.lower().strip()
    exclude_terms = {
        "we",
        "us",
        "our",
        "me",
        "my",
        "i",
        "biz",
        "bize",
        "bizim",
        "ben",
        "bana",
        "benim",
        "the",
    }

    targets = []
    for ent in entities or []:
        ent_label = (ent.get("label") or ent.get("entity_group") or "").upper()
        ent_text = ent.get("text", "").strip()
        if not ent_text or len(ent_text) > 50:
            continue

        ent_lower = ent_text.lower()
        if ent_lower in exclude_terms:
            continue
        if speaker_lower in ent_lower or ent_lower in speaker_lower:
            continue
        if country_lower in ent_lower or ent_lower in country_lower:
            continue

        if ent_label in ("GPE", "ORG", "ORGANIZATION", "LOC", "LOCATION"):
            if ent_text not in targets:
                targets.append(ent_text)

    if targets:
        return ", ".join(targets)
    return None


def _classify_demand_category(sentence_lower: str) -> DemandCategory:
    """Classifies a demand sentence into a DemandCategory using keywords."""
    if any(
        k in sentence_lower
        for k in ["reform", "institution", "restructure", "kurumsal", "reformu"]
    ):
        return DemandCategory.INSTITUTIONAL_REFORM
    if any(
        k in sentence_lower
        for k in [
            "security",
            "military",
            "force",
            "defense",
            "güvenlik",
            "askeri",
            "savunma",
            "operasyon",
            "saldırı",
            "terör",
        ]
    ):
        return DemandCategory.SECURITY_ACTION
    if any(
        k in sentence_lower
        for k in [
            "economic",
            "trade",
            "finance",
            "cooperation",
            "investment",
            "ekonomi",
            "ticaret",
            "finans",
            "yatırım",
        ]
    ):
        return DemandCategory.ECONOMIC_COOPERATION
    if any(
        k in sentence_lower
        for k in ["humanitarian", "aid", "refugee", "insani", "yardım", "mülteci"]
    ):
        return DemandCategory.HUMANITARIAN_RESPONSE
    if any(
        k in sentence_lower
        for k in [
            "legal",
            "court",
            "accountability",
            "law",
            "hukuki",
            "mahkeme",
            "adalet",
        ]
    ):
        return DemandCategory.LEGAL_ACCOUNTABILITY
    return DemandCategory.DIPLOMATIC_ENGAGEMENT


def normalize_name_for_matching(name: str) -> str:
    """Normalize a name to lowercase ASCII by removing accents and special characters."""
    name_lower = name.lower()
    name_lower = (
        name_lower.replace("ı", "i")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ç", "c")
        .replace("ğ", "g")
    )
    import unicodedata

    nfkd_form = unicodedata.normalize("NFKD", name_lower)
    return nfkd_form.encode("ASCII", "ignore").decode("ASCII").strip()


def clean_speaker_name_helper(speaker: str) -> tuple[str, str]:
    """Extract clean speaker name and existing country code if present, otherwise map it."""
    match = re.search(r"\(([^)]+)\)$|\[([^\]]+)\]$", speaker)
    if match:
        country = (match.group(1) or match.group(2)).strip()
        country_upper = country.upper()
        if country_upper in COUNTRY_NORM_MAP:
            country = COUNTRY_NORM_MAP[country_upper]
        else:
            country = country.title()
        clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker).strip()
        return clean_name, country

    clean_name = speaker.strip()
    raw_country = SPEAKER_COUNTRY_MAP.get(clean_name, "unknown")
    if raw_country == "unknown":
        norm_clean = normalize_name_for_matching(clean_name)
        for name, code in SPEAKER_COUNTRY_MAP.items():
            if normalize_name_for_matching(name) == norm_clean:
                raw_country = code
                break

    if raw_country != "unknown":
        country = COUNTRY_NORM_MAP.get(raw_country.upper(), raw_country)
    else:
        country = "unknown"
    return clean_name, country


def parse_speakers_metadata(speakers_raw: str) -> dict[str, dict[str, Any]]:
    """
    Parses SPEAKERS line from file header.
    Format: "Cevdet Yılmaz (Turkey) [Power: 8], Hakan Fidan (Turkey) [Power: 9]"
    Returns:
        {"cevdet yılmaz": {"name": "Cevdet Yılmaz", "country": "Turkey", "power_level": 8}, ...}
    """
    speakers_map: dict[str, dict[str, Any]] = {}
    if not speakers_raw:
        return speakers_map

    parts = speakers_raw.split(", ")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*\[Power:\s*(\d+)\]$", part)
        if match:
            name = match.group(1).strip()
            country = match.group(2).strip()
            power_level = int(match.group(3).strip())
            speakers_map[name.lower()] = {
                "name": name,
                "country": country,
                "power_level": power_level,
            }
    return speakers_map


def get_speaker_power_level(speaker_name: str) -> int:
    """Helper to determine a speaker's power level using SPEAKER_MAP and POWER_LEVELS."""
    sp_info = SPEAKER_MAP.get(speaker_name)
    if not sp_info:
        for name, info in SPEAKER_MAP.items():
            if name.lower() == speaker_name.lower():
                sp_info = info
                break
    if not sp_info:
        norm_speaker = normalize_name_for_matching(speaker_name)
        for name, info in SPEAKER_MAP.items():
            if normalize_name_for_matching(name) == norm_speaker:
                sp_info = info
                break
    if sp_info:
        _, _, sp_role = sp_info
        return POWER_LEVELS.get(sp_role, 3)
    return 3


def _parse_transcript_header_and_dialogue(
    file_content: str,
) -> tuple[dict[str, str], list[str]]:
    """Parses metadata header and splits dialogue lines from transcript content."""
    lines = file_content.splitlines()
    metadata: dict[str, str] = {}
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
            line.startswith(x)
            for x in ["TITLE:", "DATE:", "THEME:", "PANEL_NUMBER:", "SPEAKERS:"]
        ):
            break

        matched = False
        for key in ["TITLE", "DATE", "THEME", "PANEL_NUMBER", "SPEAKERS"]:
            if line.startswith(f"{key}:"):
                metadata[key.lower()] = line.split(f"{key}:", 1)[1].strip()
                matched = True
                break
        if not matched:
            break
        line_idx += 1

    dialogue_lines = lines[line_idx:] if has_metadata else lines
    return metadata, dialogue_lines


def standardize_file_content(file_path: Path, file_content: str) -> str:
    """
    Standardize the raw transcript file content:
    - Adds metadata headers at the top if missing or incomplete.
    - Appends country code suffix to speakers.
    """
    metadata, dialogue_lines = _parse_transcript_header_and_dialogue(file_content)

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
    file_number = (
        metadata.get("panel_number")
        or PANELS_METADATA.get(file_path.name, {}).get("file_number")
        or ""
    )

    unique_speakers: dict[str, dict[str, Any]] = {}
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

        name_lower = clean_name.lower()
        if name_lower not in unique_speakers:
            power = get_speaker_power_level(clean_name)
            unique_speakers[name_lower] = {
                "name": clean_name,
                "country": country,
                "power": power,
            }

    sorted_speakers = sorted(unique_speakers.values(), key=lambda s: s["name"])
    speaker_strings = [
        f"{s['name']} ({s['country']}) [Power: {s['power']}]" for s in sorted_speakers
    ]
    speakers_line = "SPEAKERS: " + ", ".join(speaker_strings)

    header_block = [
        f"TITLE: {title}",
        f"DATE: {date}",
        f"THEME: {theme}",
        f"PANEL_NUMBER: {file_number}",
        speakers_line,
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


_SPEAKER_COUNTRY_LOWER_CACHE: dict[str, str] | None = None
_SPEAKER_COUNTRY_NORM_CACHE: dict[str, str] | None = None


def resolve_country(speaker_name: str) -> str:
    global _SPEAKER_COUNTRY_LOWER_CACHE, _SPEAKER_COUNTRY_NORM_CACHE
    if _SPEAKER_COUNTRY_LOWER_CACHE is None or _SPEAKER_COUNTRY_NORM_CACHE is None:
        _SPEAKER_COUNTRY_LOWER_CACHE = {
            k.lower(): v for k, v in SPEAKER_COUNTRY_MAP.items()
        }
        _SPEAKER_COUNTRY_NORM_CACHE = {
            normalize_name_for_matching(k): v for k, v in SPEAKER_COUNTRY_MAP.items()
        }

    lower_cache = _SPEAKER_COUNTRY_LOWER_CACHE
    norm_cache = _SPEAKER_COUNTRY_NORM_CACHE
    assert lower_cache is not None
    assert norm_cache is not None

    # First check SPEAKER_COUNTRY_MAP
    clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker_name).strip()
    if clean_name in SPEAKER_COUNTRY_MAP:
        return SPEAKER_COUNTRY_MAP[clean_name]

    # Try exact match case-insensitive
    clean_lower = clean_name.lower()
    if clean_lower in lower_cache:
        return lower_cache[clean_lower]

    # Try normalized match
    norm_clean = normalize_name_for_matching(clean_name)
    if norm_clean in norm_cache:
        return norm_cache[norm_clean]

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


def match_keyword_with_boundaries(kw: str, text: str) -> bool:
    import re

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
    await session.execute(
        delete(DiscourseNetworkEdge).where(DiscourseNetworkEdge.file_id == file_id)
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

    from bb_paxdata.domain.services.sentiment_service import SentimentService

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
            speaker_name=speaker_name,
            country=country,
            power_level=db_speaker.power_level if db_speaker else 5,
            seq_order=seg_idx,
            text=" ".join(seg["sentences"]),
        )
        session.add(db_segment)
        await session.flush()
        all_processed_segments.append(db_segment)

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
                speaker_power_level=float(db_speaker.power_level if db_speaker else 5)
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
            )

            words_count = (
                len(pipeline_res.analysis.tokens) if pipeline_res.analysis.tokens else 0
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

            # ── Extract entities (GPE + Person) from NER results ──
            _entities_gpe = []
            _entities_person = []
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

            # ── Serialize risk signals to JSON-friendly list ──
            _risk_signals_json = []
            for _rs in _risk_sigs:
                _risk_signals_json.append(
                    {
                        "signal_text": _rs.signal_text,
                        "signal_type": (
                            _rs.signal_type.value
                            if hasattr(_rs.signal_type, "value")
                            else str(_rs.signal_type)
                        ),
                        "escalation_multiplier": _rs.escalation_multiplier,
                        "credibility_score": _rs.credibility_score,
                    }
                )

            # ── Evidence types, Appraisal attitude, Audience type ──
            # FramingService: Martin & White (2005) Appraisal, Entman (1993) Evidence
            from bb_paxdata.domain.models.sentence import (
                Sentence as SentenceDomainModel,
            )
            from bb_paxdata.domain.services.framing_service import FramingService

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
                dominant_frame=(
                    str(pipeline_res.analysis.framing)
                    if pipeline_res.analysis.framing
                    else None
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

            if pipeline_res.analysis.topic_synthesis:
                ts = pipeline_res.analysis.topic_synthesis
                from bb_paxdata.infrastructure.db.topic_models import TopicAssignmentORM

                db_assignment = TopicAssignmentORM(
                    segment_id=db_segment.seg_id,
                    analysis_id=sent_id,
                    primary_topic=ts.dominant_topic or "-1",
                    topic_scores=ts.topic_scores or {},
                    topic_label=ts.topic_label,
                    ctfidf_keywords=ts.topic_keywords or {},
                    model_metadata={},
                )
                session.add(db_assignment)

            db_sentences_in_seg.append(db_sentence)
            all_processed_sentences.append(db_sentence)

            # Save AISentenceAnalysis
            ai_analysis = AISentenceAnalysis.from_domain(
                pipeline_res.analysis, sent_id=sent_id
            )
            ai_analysis.file_id = file_id
            ai_analysis.sentence_code = sent_code
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
                    file_id=file_id,
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
                        seg["sentences"][sent_idx - 2] if sent_idx >= 2 else "[START]"
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
                    from bb_paxdata.domain.lexicon.tr_diplo_lexicon import (
                        DIPLO_LEXICON_TR,
                    )
                    from bb_paxdata.domain.lexicon.tr_stopwords import STOPWORDS_TR

                    lexicon = DIPLO_LEXICON_TR
                    stop_words = STOPWORDS_TR
                else:
                    from bb_paxdata.domain.services.sentiment_service import (
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
                            from bb_paxdata.domain.services.sentiment_service import (
                                SentimentService,
                            )

                            w_score = SentimentService.DIPLO_LEXICON.get(
                                token_lower, 0.0
                            )
                        else:
                            from bb_paxdata.domain.lexicon.tr_diplo_lexicon import (
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

        risks = [s.risk_score for s in db_sentences_in_seg if s.risk_score is not None]
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
            logger.warning(f"VADER parsing failed for segment {db_segment.seg_id}: {e}")
            db_segment.vader_pos = 0.0
            db_segment.vader_neg = 0.0
            db_segment.vader_neu = 0.0

        # Recalculate SBI and DKI using auditor's formula so they are correct in DB
        from bb_paxdata.infrastructure.logic.formula_auditor import (
            RISK_SIGNAL_WEIGHTS,
            RISK_SIGNALS,
        )

        _power_levels = []
        _demand_weights = []
        _risk_scores = []
        _sp_power = float(db_speaker.power_level) if db_speaker else 5.0

        for s in db_sentences_in_seg:
            stxt_lower = (s.text or "").lower()
            _d_w = 0.5
            if any(w in stxt_lower for w in ["must", "require", "demand", "insist"]):
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

            def norm_val(val: float, min_v: float = 0.0, max_v: float = 10.0) -> float:
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
            Counter(valid_topics).most_common(1)[0][0] if valid_topics else "General"
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
                sum(s.vader_compound or 0.0 for s in _intro_sents) / len(_intro_sents)
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
                sum(s.vader_compound or 0.0 for s in _concl_sents) / len(_concl_sents)
                if _concl_sents
                else 0.0
            )
        else:
            db_segment.intro_sentiment = 0.0
            db_segment.develop_sentiment = 0.0
            db_segment.concl_sentiment = 0.0

        # dominant_audience, dominant_evidence, formula_manip_score
        audiences = [s.audience_type for s in db_sentences_in_seg if s.audience_type]
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

    # Save File ORM
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
        db_file.n_segments = len(segments_data)
        db_file.n_sentences = total_sentences_count
        db_file.n_speakers = len(unique_speakers_in_file)
        db_file.n_countries = len(unique_countries_in_file)
        db_file.total_words = total_words_in_file
        db_file.last_processed_at = datetime.now(timezone.utc)
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
            first_processed_at=datetime.now(timezone.utc),
            last_processed_at=datetime.now(timezone.utc),
            reprocess_count=0,
            force_rebuild=0,
            n_segments=len(segments_data),
            n_sentences=total_sentences_count,
            n_speakers=len(unique_speakers_in_file),
            n_countries=len(unique_countries_in_file),
            total_words=total_words_in_file,
            imported_at=datetime.now(timezone.utc),
        )
        session.add(db_file)

    # ── File Dynamics: cümle bazlı temporal değişim kayıtları ──
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

        db_dyn = FileDynamics(
            file_id=file_id,
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

    # Processed files tracking updated above

    # ── Topic Modeling Post-Processing (Faz 5) ──
    try:
        from bb_paxdata.domain.models.segment import Segment as SegmentDomain
        from bb_paxdata.domain.models.sentence import Sentence as SentenceDomain
        from bb_paxdata.infrastructure.db.topic_models import TopicAssignmentORM

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
            console.print(
                f"[bold blue]ℹ️ Running panel-level topic modeling on {len(domain_segments)} segments...[/bold blue]"
            )
            lang = "en"
            if all_processed_sentences and "pipeline_res" in locals():
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
            console.print(
                "[green][OK] Topic modeling post-processing completed successfully.[/green]"
            )
    except Exception as exc:
        console.print(
            f"[yellow][WARN] Topic modeling post-processing failed: {exc}[/yellow]"
        )
        logger.warning("build.topic_modeling_post_processing_failed", error=str(exc))

    # ── Formula Logic Audit (YENİ) ──
    try:
        import json
        import uuid

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        auditor = FormulaAuditor()

        # Group sentences by segment id for segment audit
        sents_by_seg: dict[str, list[Any]] = {}
        logic_fail_sents_added = set()

        for sent in all_processed_sentences:
            sents_by_seg.setdefault(sent.seg_id, []).append(sent)

            # Audit sentence
            sent_logs = auditor.audit_sentence(run_id, sent)
            for log_data in sent_logs:
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
                )
                session.add(db_log)

                # Flag to Human Review Queue if FAIL
                if (
                    log_data["status"] == "FAIL"
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
                        trigger_type="LOGIC_CHECK_FAILURE",
                        ai_risk_score=sent.risk_score,
                        anomaly_types=f"LOGIC_FAIL: {log_data['formula_name']}",
                        uncertainty_score=0.0,
                        status="PENDING",
                        original_ai_json=_ai_json,
                        flagged_at=datetime.now(timezone.utc),
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
                )
                session.add(db_log)

                # Flag to Human Review Queue if FAIL
                if log_data["status"] == "FAIL" and seg_sents:
                    first_sent = seg_sents[0]
                    if first_sent.sent_id not in logic_fail_sents_added:
                        logic_fail_sents_added.add(first_sent.sent_id)
                        _ai_json = json.dumps(
                            {
                                "formula_name": log_data["formula_name"],
                                "expected_constraint": log_data["expected_constraint"],
                                "actual_value": log_data["actual_value"],
                                "details": log_data["details"],
                                "segment_text": getattr(db_seg, "text", ""),
                            },
                            ensure_ascii=False,
                        )
                        review_entry = HumanReviewQueue(
                            sent_id=first_sent.sent_id,
                            sentence_code=getattr(first_sent, "sentence_code", None),
                            seg_id=db_seg.seg_id,
                            file_id=db_seg.file_id,
                            speaker_name=db_seg.speaker_name,
                            country=db_seg.country,
                            trigger_type="LOGIC_CHECK_FAILURE",
                            ai_risk_score=db_seg.risk_score,
                            anomaly_types=f"LOGIC_FAIL: {log_data['formula_name']}",
                            uncertainty_score=0.0,
                            status="PENDING",
                            original_ai_json=_ai_json,
                            flagged_at=datetime.now(timezone.utc),
                        )
                        session.add(review_entry)
        console.print(
            "[green][OK] Formula logic audit completed and logged to database.[/green]"
        )
    except Exception as exc:
        console.print(f"[yellow][WARN] Formula logic audit failed: {exc}[/yellow]")
        logger.warning("build.formula_logic_audit_failed", error=str(exc))

    # ── Temporal Drift Event Analysis ──
    try:
        from bb_paxdata.domain.services.temporal import TemporalAnalyzer
        from bb_paxdata.infrastructure.db.drift_events import (
            DriftEvent as DriftEventORM,
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

            sentence_data.append(
                {
                    "speaker_id": sp_id,
                    "global_sent_order": s.global_sent_order or 0,
                    "text": s.text or "",
                    "AI_Duygu_Skoru": s.vader_compound,
                    "AI_Risk_Skoru": s.risk_score,
                    "AI_Birincil_Konu": s.dominant_topic,
                    "AI_Diplomatik_Ton": s.dominant_frame,
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
            console.print(
                f"[green][OK] Detected and logged {len(drift_events)} temporal drift events to database.[/green]"
            )
        else:
            console.print(
                "[green][OK] Temporal drift analysis completed (no drift events detected).[/green]"
            )

    except Exception as exc:
        console.print(f"[yellow][WARN] Temporal drift analysis failed: {exc}[/yellow]")
        logger.warning("build.temporal_drift_analysis_failed", error=str(exc))

    # ── Phase 4 Discourse Network and Flows Integration ──
    try:
        await rebuild_network_for_file(session, file_id)
    except Exception as exc:
        console.print(
            f"[yellow][WARN] Rebuilding network data failed for {file_id}: {exc}[/yellow]"
        )
        logger.warning("build.rebuild_network_failed", file_id=file_id, error=str(exc))

    # ── Topic Matrix 2.0: Event Logging ──
    try:
        import uuid

        from bb_paxdata.domain.services.linguistic_helpers import (
            classify_speech_act,
            get_frame_distribution,
            get_vad_vector,
        )
        from bb_paxdata.infrastructure.db.models import SegmentAnalyzedEvent

        run_id_event = f"run_{uuid.uuid4().hex[:8]}"

        for db_seg in all_processed_segments:
            vad = get_vad_vector(db_seg.diplo_compound or 0.0, db_seg.emotion_category)
            act = classify_speech_act(db_seg.text or "", db_seg.demand_count or 0)
            frames_dist = get_frame_distribution(
                db_seg.text or "", db_seg.dominant_frame
            )

            event = SegmentAnalyzedEvent(
                event_id=str(uuid.uuid4()),
                event_timestamp=datetime.now(timezone.utc),
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

        console.print("[green][OK] Logged segment events to event store.[/green]")
    except Exception as exc:
        console.print(f"[yellow][WARN] Logging segment events failed: {exc}[/yellow]")
        logger.warning("build.segment_event_logging_failed", error=str(exc))

    await session.flush()
    return "processed"


async def rebuild_network_for_file(session: Any, file_id: str) -> None:
    """Rebuilds bilateral sentiments, discourse network edges, and discourse flows for a single file/panel."""
    from bb_paxdata.infrastructure.db.country_models import (
        BilateralSentimentTable,
        DiscourseFlowTable,
    )
    from bb_paxdata.infrastructure.db.discourse_network_table import (
        DiscourseNetworkEdgeTable,
    )
    from bb_paxdata.infrastructure.db.models import (
        ActorActionMatrixORM,
        DependencyTripleORM,
        DiscourseNetworkEdge,
    )
    from sqlalchemy import delete

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
        delete(DiscourseNetworkEdge).where(DiscourseNetworkEdge.file_id == file_id)
    )
    await session.execute(
        delete(DependencyTripleORM).where(DependencyTripleORM.file_id == file_id)
    )
    await session.execute(
        delete(ActorActionMatrixORM).where(ActorActionMatrixORM.file_id == file_id)
    )
    await session.flush()

    # Construct SegmentDomain and SentenceDomain from database Segment and Sentence ORM tables
    from bb_paxdata.domain.models.segment import Segment as SegmentDomain
    from bb_paxdata.domain.models.sentence import Sentence as SentenceDomain
    from bb_paxdata.infrastructure.db.models import Segment as SegmentORM
    from bb_paxdata.infrastructure.db.models import Sentence as SentenceORM

    # Get segments
    seg_res = await session.execute(
        select(SegmentORM)
        .where(SegmentORM.file_id == file_id)
        .order_by(SegmentORM.seq_order)
    )
    db_segs = seg_res.scalars().all()

    # Get sentences
    sent_res = await session.execute(
        select(SentenceORM)
        .where(SentenceORM.file_id == file_id)
        .order_by(SentenceORM.global_sent_order)
    )
    db_sents = sent_res.scalars().all()

    # Group sentences by segment id
    sents_by_seg: dict[str, list[Any]] = {}
    for s in db_sents:
        sents_by_seg.setdefault(s.seg_id, []).append(s)

    # Build domain segments
    domain_segments = []
    for db_seg in db_segs:
        seg_sents = sents_by_seg.get(db_seg.seg_id, [])
        domain_sents = [SentenceDomain(id=s.sent_id, text=s.text) for s in seg_sents]

        # Extract speaker, GPE, and tokens
        primary_speaker = db_seg.speaker_id
        segment_tokens = db_seg.text.lower().split() if db_seg.text else []
        concepts = []
        for s in seg_sents:
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
                id=db_seg.seg_id,
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
            console.print(
                f"[{file_id}] [green][OK] Bilateral sentiments aggregated successfully. Saved {bil_agg_output.created_count} new pairs.[/green]"
            )
        else:
            console.print(
                f"[{file_id}] [yellow][WARN] Bilateral sentiments aggregation failed: {bil_agg_output.errors}[/yellow]"
            )
    except Exception as exc:
        console.print(
            f"[{file_id}] [yellow][WARN] Bilateral sentiments aggregation failed: {exc}[/yellow]"
        )

    # ── 2. Discourse Network Analysis (Fischer DNA & Maoz Dyadic) ──
    try:
        from bb_paxdata.application.pipeline.stages.assemble_network import (
            NetworkAssemblyStage,
        )
        from bb_paxdata.application.pipeline.stages.finalize_network import (
            NetworkFinalizeStage,
        )
        from bb_paxdata.domain.models.analysis import Analysis as AnalysisDomain
        from bb_paxdata.infrastructure.db.country_models import BilateralSentimentTable
        from bb_paxdata.infrastructure.db.repositories.country_repository import (
            BilateralSentimentRepository,
        )
        from bb_paxdata.infrastructure.db.repositories.discourse_network_repository import (
            DiscourseNetworkRepository,
        )
        from bb_paxdata.infrastructure.nlp.fischer_dna_service import FischerDNAService
        from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService

        # Construct AnalysisDomain
        analysis_domain = AnalysisDomain(
            id=file_id,
            segments=domain_segments,
            bilateral_sentiments=[],
        )

        # Query existing bilateral sentiments for this file_id from database to populate domain model
        bil_res = await session.execute(
            select(BilateralSentimentTable).where(
                BilateralSentimentTable.file_id == file_id
            )
        )
        db_bilaterals = bil_res.scalars().all()
        domain_bilaterals = [b.to_domain() for b in db_bilaterals]

        analysis_domain = analysis_domain.model_copy(
            update={"bilateral_sentiments": domain_bilaterals}
        )

        # Instantiate services & repositories
        fischer_service = FischerDNAService()
        maoz_service = MaozDyadicService()

        network_repo = DiscourseNetworkRepository(session)
        bilateral_repo = BilateralSentimentRepository(session)

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

        console.print(
            f"[{file_id}] [green][OK] Discourse network analysis completed. Saved {enriched_analysis.discourse_flow.edge_count if enriched_analysis.discourse_flow else 0} modern edges.[/green]"
        )
    except Exception as exc:
        console.print(
            f"[{file_id}] [yellow][WARN] Discourse network analysis failed: {exc}[/yellow]"
        )

    # ── 3. Build Panel Network (Discourse Flows) ──
    try:
        from bb_paxdata.application.use_cases.build_panel_network import (
            BuildPanelNetworkInput,
            BuildPanelNetworkUseCase,
        )
        from bb_paxdata.infrastructure.db.repositories.country_repository import (
            BilateralSentimentRepository,
            DiscourseFlowRepository,
        )

        flow_use_case = BuildPanelNetworkUseCase(
            sentiment_repo=BilateralSentimentRepository(session),
            flow_repo=DiscourseFlowRepository(session),
        )
        flow_output = await flow_use_case.execute(
            BuildPanelNetworkInput(panel_id=file_id)
        )
        if flow_output.succeeded:
            console.print(
                f"[{file_id}] [green][OK] Discourse flows built successfully. Saved {flow_output.edges_created} flows.[/green]"
            )
        else:
            console.print(
                f"[{file_id}] [yellow][WARN] Discourse flows build had errors: {flow_output.errors}[/yellow]"
            )
    except Exception as exc:
        console.print(
            f"[{file_id}] [yellow][WARN] Discourse flows use case execution failed: {exc}[/yellow]"
        )

    # ── 4. Extract and Persist Grammatical Dependency Triples (SVO) ──
    try:
        from collections import defaultdict

        from bb_paxdata.domain.models.dependency import ActorActionMatrix
        from bb_paxdata.domain.services.actor_resolver import ActorResolver
        from bb_paxdata.infrastructure.container.service_container import (
            ServiceContainer,
        )
        from bb_paxdata.infrastructure.db.repositories.dependency import (
            DependencyRepository,
        )

        container = ServiceContainer.get_instance()
        nlp_en = container.ner_service._models.get("en")
        nlp_tr = container.ner_service._models.get("tr")
        from bb_paxdata.domain.services.language_detector import LanguageDetector

        dep_service = container.dependency_service
        dep_repo = DependencyRepository(session)

        matrix_counts: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "sentiment_sum": 0.0, "passive_cnt": 0, "neg_cnt": 0}
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
                t.sent_id = s.sent_id
                t.seg_id = s.seg_id
                t.panel_id = file_id
                t.speaker_name = s.speaker_name
                t.country = s.country

                t.sentiment_context = s.vader_compound
                t.risk_score = s.risk_score

                await dep_repo.insert_triple(t)

                if subj_res and obj_res:
                    key = (subj_res, obj_res, t.verb_lemma)
                    matrix_counts[key]["count"] += 1
                    matrix_counts[key]["sentiment_sum"] += s.vader_compound or 0.0
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

        console.print(
            f"[{file_id}] [green][OK] Dependency parsing completed successfully. Extracted triples persisted.[/green]"
        )
    except Exception as exc:
        console.print(
            f"[{file_id}] [yellow][WARN] Dependency parsing failed: {exc}[/yellow]"
        )

    await session.flush()


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

            from bb_paxdata.domain.services.sentiment_service import SentimentService

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
    from bb_paxdata.domain.services.linguistic_helpers import (
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

    run_id = f"backfill_{uuid.uuid4().hex[:8]}"
    for s in segments:
        vad = get_vad_vector(s.diplo_compound or 0.0, s.emotion_category)
        act = classify_speech_act(s.text or "", s.demand_count or 0)
        frames = get_frame_distribution(s.text or "", s.dominant_frame)

        event = SegmentAnalyzedEvent(
            event_id=str(uuid.uuid4()),
            event_timestamp=(
                datetime.now(timezone.utc)
                if hasattr(s, "created_at")
                else datetime.now(timezone.utc)
            ),
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
        console.print("\n[green][OK] Build completed!")
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
                    "  [yellow][WARN]  Limit doldu — sonraki cümleler logic-only ile analiz edildi.[/yellow]"
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
