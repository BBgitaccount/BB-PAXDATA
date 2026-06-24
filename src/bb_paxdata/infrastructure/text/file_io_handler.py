"""File I/O and Transcript Standardization Handler."""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from bb_paxdata.application.domain.enums.demand_category import DemandCategory
from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
    COUNTRY_BLOC_MAP,
    RAW_MAPPING,
)

logger = structlog.get_logger(__name__)

SPEAKER_COUNTRY_MAP = {
    "Abdul Hamid": "PSE",
    "Abdul Hamid Siyam": "PSE",
    "Ahmed Al-Sharaa": "SYR",
    "Andrii Sybiha": "UKR",
    "André Corrêa do Lago": "BRA",
    "Azali Assoumani": "COM",
    "Babatunde Ahonsi": "NGA",
    "Baiba Braže": "LVA",
    "Carl Skau": "SWE",
    "Cevdet Yılmaz": "TUR",
    "Daniel Levy": "GBR",
    "David Moinina Sengeh": "SLE",
    "Deniz Kilislioğlu": "TUR",
    "Eda Özdemir": "TUR",
    "Emile Hokayem": "LBN",
    "Faisal Dawjee": "ZAF",
    "Félix Antoine Tshisekedi": "COD",
    "Félix Ulloa": "SLV",
    "Gordana Siljanovska-Davkova": "MKD",
    "Gökhan Çeliker": "TUR",
    "Hakan Fidan": "TUR",
    "Hassan Sheikh Mohamud": "SOM",
    "Hikmet Hajiyev": "AZE",
    "Irakli Kobakhidze": "GEO",
    "Kassym-Jomart Tokayev": "KAZ",
    "Keir Simmons": "GBR",
    "Kemal Cebe": "TUR",
    "Kęstutis Budrys": "LTU",
    "Laurent Fabius": "FRA",
    "Levent Gümrükçü": "TUR",
    "Lizzie Porter": "GBR",
    "Manolis Kostidis": "GRC",
    "Marabski [Soyisim]": "POL",
    "Maria Fantappiè": "ITA",
    "Mercy Bamola": "NGA",
    "Mevlüt Çavuşoğlu": "TUR",
    "Miloš Vučević": "SRB",
    "Mukhtar Babayev": "AZE",
    "Murat Kurum": "TUR",
    "Olga Osacheva": "BLR",
    "Radmila Šekerinska": "MKD",
    "Recep Tayyip Erdoğan": "TUR",
    "Selwin Hart": "BRB",
    "Sergei Lavrov": "RUS",
    "Shayea Mohsin Al-Zindani": "YEM",
    "Thomas Greminger": "CHE",
    "Tom Barrack": "USA",
    "Varsen Aghabekian": "PSE",
    "Xəyalə Rəis": "AZE",
    "İsmail": "TUR",
    "Əli Vəliyev": "AZE",
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
    "Ahmed Al Sharaa": ("Syrian Arab Republic", "President", "head_of_state"),
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
    "Sergey Lavrov": ("Russian Federation", "Minister of Foreign Affairs", "minister"),
    "Sergei Lavrov": ("Russian Federation", "Minister of Foreign Affairs", "minister"),
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
    "Babatunde Ahonsi": (
        "United Nations",
        "Resident Coordinator in Türkiye",
        "intl_official",
    ),
    "Carl Skau": ("United Nations", "Deputy Exec. Dir. WFP", "intl_official"),
    "Laurent Fabius": (
        "France",
        "Former Prime Minister / President of COP21",
        "expert",
    ),
    "Radmila Šekerinska": ("NATO", "Deputy Secretary General", "intl_official"),
    "Selwin Hart": (
        "United Nations",
        "Special Adviser on Climate Action",
        "intl_official",
    ),
    "Tom Barrack": ("United States of America", "US Ambassador", "diplomat"),
    "Thomas Greminger": ("Switzerland", "Director of GCSP", "moderator"),
    "Abdul Hamid": ("United States of America", "UN Correspondent", "journalist"),
    "Abdul Hamid Siyam": ("United States of America", "UN Correspondent", "journalist"),
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

BLOC_MAP = {}
for iso3, info in COUNTRY_BLOC_MAP.items():
    BLOC_MAP[info["name"]] = info["bloc"]
    BLOC_MAP[iso3] = info["bloc"]

COUNTRY_NORM_MAP = {}
for raw, iso3 in RAW_MAPPING.items():
    if iso3 in COUNTRY_BLOC_MAP:
        COUNTRY_NORM_MAP[raw] = COUNTRY_BLOC_MAP[iso3]["name"]
for iso3, info in COUNTRY_BLOC_MAP.items():
    COUNTRY_NORM_MAP[iso3] = info["name"]
    COUNTRY_NORM_MAP[info["name"].upper()] = info["name"]

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
    from bb_paxdata.infrastructure.text.normalizer import normalize_person_name

    match = re.search(r"\(([^)]+)\)$|\[([^\]]+)\]$", speaker)
    if match:
        country = (match.group(1) or match.group(2)).strip()
        country_upper = country.upper()
        if country_upper in COUNTRY_NORM_MAP:
            country = COUNTRY_NORM_MAP[country_upper]
        else:
            country = country.title()
        clean_name = re.sub(r"\s*\(.*\)$|\s*\[.*\]$", "", speaker).strip()
        clean_name = normalize_person_name(clean_name)
        return clean_name, country

    clean_name = speaker.strip()
    clean_name = normalize_person_name(clean_name)
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


def utc_now() -> datetime:
    """Get current UTC datetime as timezone-naive (required for TIMESTAMP WITHOUT TIME ZONE columns)."""
    return datetime.now(UTC).replace(tzinfo=None)


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
    if lower_cache is None or norm_cache is None:
        logger.error(
            "Speaker country cache not initialized",
            lower_cache_is_none=lower_cache is None,
            norm_cache_is_none=norm_cache is None,
        )
        # Fallback to direct map lookup without caching
        lower_cache = {}
        norm_cache = {}

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
