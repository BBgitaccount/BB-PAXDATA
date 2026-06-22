# src/bb_paxdata/application/domain/lexicon/country_bloc_mapping.py

"""
Geopolitical and diplomatic bloc mappings for BB-PAXDATA.
This file serves as the single source of truth for country names, ISO3 codes, and diplomatic bloc assignments.
"""

from typing import TypedDict


class CountryInfo(TypedDict):
    name: str
    bloc: str
    power_level: float


# Standardized Diplomatic Blocs (matching BlocType enum)
BLOCS = {
    "WESTERN_ALLIANCE": "Western Alliance",
    "EASTERN_BLOC": "Eastern Bloc / Russian Sphere",
    "CHINA_LED": "China-led Bloc",
    "NON_ALIGNED": "Non-Aligned / Global South",
    "AFRICAN_UNION": "African Union Aligned",
    "ARAB_LEAGUE": "Arab League",
    "ASEAN": "ASEAN Aligned",
    "CENTRAL_ASIAN": "Central Asian Sphere",
    "INTERNATIONAL_ORG": "International Organizations",
    "OTHER": "Other",
}

# Single source of truth for countries and organizations
COUNTRY_BLOC_MAP: dict[str, CountryInfo] = {
    # ── Western Alliance ──
    "USA": {
        "name": "United States of America",
        "bloc": BLOCS["WESTERN_ALLIANCE"],
        "power_level": 1.0,
    },
    "CAN": {"name": "Canada", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.8},
    "GBR": {
        "name": "United Kingdom",
        "bloc": BLOCS["WESTERN_ALLIANCE"],
        "power_level": 0.8,
    },
    "FRA": {"name": "France", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.8},
    "DEU": {"name": "Germany", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.8},
    "ITA": {"name": "Italy", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.7},
    "ESP": {"name": "Spain", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.7},
    "POL": {"name": "Poland", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.6},
    "SWE": {"name": "Sweden", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.6},
    "NOR": {"name": "Norway", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.6},
    "CHE": {
        "name": "Switzerland",
        "bloc": BLOCS["WESTERN_ALLIANCE"],
        "power_level": 0.6,
    },
    "JPN": {"name": "Japan", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.8},
    "AUS": {"name": "Australia", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.7},
    "NZL": {
        "name": "New Zealand",
        "bloc": BLOCS["WESTERN_ALLIANCE"],
        "power_level": 0.6,
    },
    "LVA": {"name": "Latvia", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.5},
    "LTU": {"name": "Lithuania", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.5},
    "GRC": {"name": "Greece", "bloc": BLOCS["WESTERN_ALLIANCE"], "power_level": 0.5},
    "MKD": {
        "name": "North Macedonia",
        "bloc": BLOCS["WESTERN_ALLIANCE"],
        "power_level": 0.5,
    },
    # ── Eastern Bloc / Russian Sphere ──
    "RUS": {
        "name": "Russian Federation",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.9,
    },
    "BLR": {"name": "Belarus", "bloc": BLOCS["EASTERN_BLOC"], "power_level": 0.5},
    "PRK": {
        "name": "Democratic People's Republic of Korea (North Korea)",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.6,
    },
    "UKR": {
        "name": "Ukraine",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.7,
    },  # Former Soviet state
    "GEO": {
        "name": "Georgia",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.5,
    },  # Former Soviet state
    "ARM": {
        "name": "Armenia",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.5,
    },  # Former Soviet state
    "AZE": {
        "name": "Azerbaijan",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.6,
    },  # Former Soviet state
    "MDA": {
        "name": "Moldova",
        "bloc": BLOCS["EASTERN_BLOC"],
        "power_level": 0.5,
    },  # Former Soviet state
    "SRB": {"name": "Serbia", "bloc": BLOCS["EASTERN_BLOC"], "power_level": 0.5},
    # ── China-led Bloc ──
    "CHN": {
        "name": "People's Republic of China",
        "bloc": BLOCS["CHINA_LED"],
        "power_level": 1.0,
    },
    "PAK": {"name": "Pakistan", "bloc": BLOCS["CHINA_LED"], "power_level": 0.6},
    # ── Non-Aligned / Global South ──
    "IND": {"name": "India", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.8},
    "ZAF": {"name": "South Africa", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.7},
    "BRA": {"name": "Brazil", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.7},
    "ARG": {"name": "Argentina", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.6},
    "MEX": {"name": "Mexico", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.6},
    "TUR": {"name": "Turkey", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.7},
    "NGA": {"name": "Nigeria", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.6},
    "KEN": {"name": "Kenya", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.5},
    "ETH": {"name": "Ethiopia", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.5},
    "SEN": {"name": "Senegal", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.5},
    "EGY": {
        "name": "Egypt",
        "bloc": BLOCS["NON_ALIGNED"],
        "power_level": 0.6,
    },  # Independent diplomatic line
    "SLV": {"name": "El Salvador", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.5},
    "BRB": {"name": "Barbados", "bloc": BLOCS["NON_ALIGNED"], "power_level": 0.5},
    # ── African Union Aligned ──
    "COD": {
        "name": "Democratic Republic of the Congo",
        "bloc": BLOCS["AFRICAN_UNION"],
        "power_level": 0.5,
    },
    "COM": {"name": "Comoros", "bloc": BLOCS["AFRICAN_UNION"], "power_level": 0.5},
    "BDI": {"name": "Burundi", "bloc": BLOCS["AFRICAN_UNION"], "power_level": 0.5},
    "SLE": {"name": "Sierra Leone", "bloc": BLOCS["AFRICAN_UNION"], "power_level": 0.5},
    "SOM": {"name": "Somalia", "bloc": BLOCS["AFRICAN_UNION"], "power_level": 0.5},
    # ── Arab League ──
    "SAU": {"name": "Saudi Arabia", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.7},
    "ARE": {
        "name": "United Arab Emirates",
        "bloc": BLOCS["ARAB_LEAGUE"],
        "power_level": 0.7,
    },
    "QAT": {"name": "Qatar", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.6},
    "JOR": {"name": "Jordan", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.5},
    "IRQ": {"name": "Iraq", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.5},
    "LBN": {"name": "Lebanon", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.5},
    "YEM": {"name": "Yemen", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.5},
    "PSE": {"name": "Palestine", "bloc": BLOCS["ARAB_LEAGUE"], "power_level": 0.5},
    "SYR": {
        "name": "Syrian Arab Republic",
        "bloc": BLOCS["ARAB_LEAGUE"],
        "power_level": 0.5,
    },
    # ── ASEAN Aligned ──
    "VNM": {"name": "Vietnam", "bloc": BLOCS["ASEAN"], "power_level": 0.6},
    "THA": {"name": "Thailand", "bloc": BLOCS["ASEAN"], "power_level": 0.5},
    "MYS": {"name": "Malaysia", "bloc": BLOCS["ASEAN"], "power_level": 0.5},
    "PHL": {"name": "Philippines", "bloc": BLOCS["ASEAN"], "power_level": 0.5},
    "IDN": {"name": "Indonesia", "bloc": BLOCS["ASEAN"], "power_level": 0.6},
    # ── Central Asian Sphere ──
    "KAZ": {"name": "Kazakhstan", "bloc": BLOCS["CENTRAL_ASIAN"], "power_level": 0.6},
    "UZB": {"name": "Uzbekistan", "bloc": BLOCS["CENTRAL_ASIAN"], "power_level": 0.5},
    "KGZ": {"name": "Kyrgyzstan", "bloc": BLOCS["CENTRAL_ASIAN"], "power_level": 0.5},
    "TJK": {"name": "Tajikistan", "bloc": BLOCS["CENTRAL_ASIAN"], "power_level": 0.5},
    "TKM": {"name": "Turkmenistan", "bloc": BLOCS["CENTRAL_ASIAN"], "power_level": 0.5},
    # ── International Organizations ──
    "UN": {
        "name": "United Nations",
        "bloc": BLOCS["INTERNATIONAL_ORG"],
        "power_level": 0.7,
    },
    "NATO": {"name": "NATO", "bloc": BLOCS["INTERNATIONAL_ORG"], "power_level": 0.8},
    "EU": {
        "name": "European Union",
        "bloc": BLOCS["INTERNATIONAL_ORG"],
        "power_level": 0.8,
    },
    "ASEAN": {"name": "ASEAN", "bloc": BLOCS["INTERNATIONAL_ORG"], "power_level": 0.6},
    "AU": {
        "name": "African Union",
        "bloc": BLOCS["INTERNATIONAL_ORG"],
        "power_level": 0.6,
    },
}

# Normalization mapping from 2-letter, old names, and abbreviations to standard ISO3
RAW_MAPPING: dict[str, str] = {
    # Turkey
    "TR": "TUR",
    "TURKEY": "TUR",
    "TÜRKİYE": "TUR",
    # USA
    "US": "USA",
    "AMERICA": "USA",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    # UK
    "UK": "GBR",
    "GB": "GBR",
    "BRITAIN": "GBR",
    "UNITED KINGDOM": "GBR",
    # Russia
    "RU": "RUS",
    "RUSSIA": "RUS",
    "RUSYA": "RUS",
    "RUSSIAN FEDERATION": "RUS",
    # South Korea
    "KR": "KOR",
    "REPUBLIC OF KOREA": "KOR",
    "SOUTH KOREA": "KOR",
    # North Korea
    "PRK": "PRK",
    "NK": "PRK",
    "NORTH KOREA": "PRK",
    # Iran
    "IR": "IRN",
    "IRAN": "IRN",
    "ISLAMIC REPUBLIC OF IRAN": "IRN",
    # Syria
    "SY": "SYR",
    "SYRIA": "SYR",
    "SYRIAN ARAB REPUBLIC": "SYR",
    # Vietnam
    "VN": "VNM",
    "VIETNAM": "VNM",
    # China
    "CN": "CHN",
    "CHINA": "CHN",
    "PEOPLE'S REPUBLIC OF CHINA": "CHN",
    # Taiwan
    "TW": "TWN",
    "TAIWAN": "TWN",
    # Tanzania
    "TZ": "TZA",
    "TANZANIA": "TZA",
    # Bolivia
    "BO": "BOL",
    "BOLIVIA": "BOL",
    # Macedonia / North Macedonia
    "MK": "MKD",
    "MACEDONIA": "MKD",
    "NORTH MACEDONIA": "MKD",
    # Ukraine
    "UA": "UKR",
    "UKRAINE": "UKR",
    # Azerbaijan
    "AZ": "AZE",
    "AZERBAIJAN": "AZE",
    # Greece
    "GR": "GRC",
    "GREECE": "GRC",
    # Italy
    "IT": "ITA",
    "ITALY": "ITA",
    # Serbia
    "RS": "SRB",
    "SERBIA": "SRB",
    # Poland
    "PL": "POL",
    "POLAND": "POL",
    "SOYISIM": "POL",  # Handle parsing anomaly for Marabski
    # Belarus
    "BY": "BLR",
    "BEL": "BLR",  # Handle incorrect 3-letter code
    "BELARUS": "BLR",
    # Switzerland
    "CH": "CHE",
    "SWITZERLAND": "CHE",
    # Yemen
    "YE": "YEM",
    "YEMEN": "YEM",
    # DRC
    "CD": "COD",
    "DRC": "COD",
    "CONGO": "COD",
    "DEMOCRATIC REPUBLIC OF THE CONGO": "COD",
    "DEMOCRATIC REPUBLIC OF CONGO": "COD",
    # Comoros
    "KM": "COM",
    "COMOROS": "COM",
    # Somalia
    "SO": "SOM",
    "SOMALIA": "SOM",
    # Georgia
    "GE": "GEO",
    "GEORGIA": "GEO",
    # Kazakhstan
    "KZ": "KAZ",
    "KAZAKHSTAN": "KAZ",
    # Lithuania
    "LT": "LTU",
    "LIT": "LTU",  # Handle incorrect 3-letter code
    "LITHUANIA": "LTU",
    # France
    "FR": "FRA",
    "FRANCE": "FRA",
    # South Africa
    "ZA": "ZAF",
    "SOUTH AFRICA": "ZAF",
    # Sierra Leone
    "SL": "SLE",
    "SIERRA LEONE": "SLE",
    # El Salvador
    "SV": "SLV",
    "EL SALVADOR": "SLV",
    # Lebanon
    "LB": "LBN",
    "LEB": "LBN",  # Handle incorrect 3-letter code
    "LEBANON": "LBN",
    # Barbados
    "BB": "BRB",
    "BAR": "BRB",  # Handle incorrect 3-letter code
    "BARBADOS": "BRB",
    # Palestine
    "PS": "PSE",
    "PALESTINE": "PSE",
    # Brazil
    "BR": "BRA",
    "BRAZIL": "BRA",
    # Nigeria
    "NG": "NGA",
    "NIGERIA": "NGA",
    # Latvia
    "LV": "LVA",
    "LAT": "LVA",  # Handle incorrect 3-letter code
    "LATVIA": "LVA",
    # Sweden
    "SE": "SWE",
    "SWEDEN": "SWE",
    # UAE
    "AE": "ARE",
    "UAE": "ARE",
    "UNITED ARAB EMIRATES": "ARE",
    # Saudi Arabia
    "SA": "SAU",
    "SAUDI ARABIA": "SAU",
    # Qatar
    "QA": "QAT",
    "QATAR": "QAT",
    # Egypt
    "EG": "EGY",
    "EGYPT": "EGY",
    # Burundi
    "BI": "BDI",
    "BURUNDI": "BDI",
    # Canada
    "CA": "CAN",
    "CANADA": "CAN",
    # Japan
    "JP": "JPN",
    "JAPAN": "JPN",
    # Australia
    "AU": "AUS",  # Note: AU can stand for African Union or Australia depending on context, handled below
    "AUSTRALIA": "AUS",
    # New Zealand
    "NZ": "NZL",
    "NEW ZEALAND": "NZL",
    # Norway
    "NO": "NOR",
    "NORWAY": "NOR",
    # Spain
    "ES": "ESP",
    "SPAIN": "ESP",
    # Germany
    "DE": "DEU",
    "GERMANY": "DEU",
    # India
    "IN": "IND",
    "INDIA": "IND",
    # Argentina
    "AR": "ARG",
    "ARGENTINA": "ARG",
    # Mexico
    "MX": "MEX",
    "MEXICO": "MEX",
    # Kenya
    "KE": "KEN",
    "KENYA": "KEN",
    # Ethiopia
    "ET": "ETH",
    "ETHIOPIA": "ETH",
    # Senegal
    "SN": "SEN",
    "SENEGAL": "SEN",
    # Jordan
    "JO": "JOR",
    "JORDAN": "JOR",
    # Iraq
    "IQ": "IRQ",
    "IRAQ": "IRQ",
    # Thailand
    "TH": "THA",
    "THAILAND": "THA",
    # Malaysia
    "MY": "MYS",
    "MALAYSIA": "MYS",
    # Philippines
    "PH": "PHL",
    "PHILIPPINES": "PHL",
    # Indonesia
    "ID": "IDN",
    "INDONESIA": "IDN",
    # Uzbekistan
    "UZ": "UZB",
    "UZBEKISTAN": "UZB",
    # Kyrgyzstan
    "KG": "KGZ",
    "KYRGYZSTAN": "KGZ",
    # Tajikistan
    "TJ": "TJK",
    "TAJIKISTAN": "TJK",
    # Turkmenistan
    "TM": "TKM",
    "TURKMENISTAN": "TKM",
    # Organizations
    "UN": "UN",
    "UNITED NATIONS": "UN",
    "BM": "UN",
    "NATO": "NATO",
    "EU": "EU",
    "AB": "EU",
    "EUROPEAN UNION": "EU",
    "ASEAN": "ASEAN",
    "AUSTRALIAN UNION": "AU",  # Just in case
    "AFRICAN UNION": "AU",
}


def normalize_country(name_or_code: str) -> tuple[str, str, str]:
    """
    Normalizes any country name or code string to (ISO3, Standard Full Name, Standard Bloc).

    If unrecognized, returns ('UNK', name_or_code, 'Unknown').
    """
    if not name_or_code:
        return "UNK", "Unknown", "unknown"

    cleaned = name_or_code.strip().upper()

    # 1. Direct check in standard ISO3 map
    if cleaned in COUNTRY_BLOC_MAP:
        info = COUNTRY_BLOC_MAP[cleaned]
        return cleaned, info["name"], info["bloc"]

    # 2. Check in translation/abbreviation map
    iso3 = RAW_MAPPING.get(cleaned)
    if iso3 and iso3 in COUNTRY_BLOC_MAP:
        info = COUNTRY_BLOC_MAP[iso3]
        return iso3, info["name"], info["bloc"]

    # 3. Fallback for "AU" (African Union vs Australia)
    if cleaned == "AU":
        # Default to African Union in our organizations context
        info = COUNTRY_BLOC_MAP["AU"]
        return "AU", info["name"], info["bloc"]

    # Try mapping title case if we can match by name
    for k, info in COUNTRY_BLOC_MAP.items():
        if info["name"].upper() == cleaned:
            return k, info["name"], info["bloc"]

    return "UNK", name_or_code, "unknown"
