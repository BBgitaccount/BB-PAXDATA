# src/bb_paxdata/infrastructure/mappings/country_iso_map.py


COUNTRY_ISO_MAP = {
    "Syrian Arab Republic": "SYR",
    "Syria": "SYR",
    "Russian Federation": "RUS",
    "Russia": "RUS",
    "Türkiye": "TUR",
    "Turkey": "TUR",
    "Turkiye": "TUR",
    "United States of America": "USA",
    "United States": "USA",
    "USA": "USA",
    "United Kingdom": "GBR",
    "UK": "GBR",
    "Great Britain": "GBR",
    "France": "FRA",
    "Germany": "DEU",
    "Italy": "ITA",
    "Spain": "ESP",
    "Poland": "POL",
    "Sweden": "SWE",
    "Norway": "NOR",
    "Switzerland": "CHE",
    "Japan": "JPN",
    "Australia": "AUS",
    "New Zealand": "NZL",
    "Latvia": "LVA",
    "Lithuania": "LTU",
    "Greece": "GRC",
    "North Macedonia": "MKD",
    "Belarus": "BLR",
    "North Korea": "PRK",
    "Democratic People's Republic of Korea": "PRK",
    "Ukraine": "UKR",
    "Georgia": "GEO",
    "Armenia": "ARM",
    "Azerbaijan": "AZE",
    "South Africa": "ZAF",
    "Sierra Leone": "SLE",
    "El Salvador": "SLV",
    "Lebanon": "LBN",
    "Barbados": "BRB",
    "Palestine": "PSE",
    "Brazil": "BRA",
    "Nigeria": "NGA",
    "Saudi Arabia": "SAU",
    "Qatar": "QAT",
    "Egypt": "EGY",
    "Burundi": "BDI",
    "Canada": "CAN",
    "India": "IND",
    "Argentina": "ARG",
    "Mexico": "MEX",
    "Kenya": "KEN",
    "Ethiopia": "ETH",
    "Senegal": "SEN",
    "Jordan": "JOR",
    "Iraq": "IRQ",
    "Thailand": "THA",
    "Malaysia": "MYS",
    "Philippines": "PHL",
    "Indonesia": "IDN",
    "Uzbekistan": "UZB",
    "Kyrgyzstan": "KGZ",
    "Tajikistan": "TJK",
    "Turkmenistan": "TKM",
    "China": "CHN",
    "Iran": "IRN",
    "Islamic Republic of Iran": "IRN",
}


def get_iso_alpha3(country_name: str | None) -> str | None:
    """
    Returns the ISO 3166-1 alpha-3 code for a given country name.
    If the name is not in the map, falls back to case-insensitive lookup
    and then project's standard normalize_country helper.
    """
    if not country_name:
        return None

    name = country_name.strip()

    # 1. Direct match
    if name in COUNTRY_ISO_MAP:
        return COUNTRY_ISO_MAP[name]

    # 2. Case-insensitive lookup
    name_upper = name.upper()
    for k, v in COUNTRY_ISO_MAP.items():
        if k.upper() == name_upper:
            return v

    # 3. Fallback to standard project domain mappings
    try:
        from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
            normalize_country,
        )

        iso3, _, _ = normalize_country(name)
        if iso3 and iso3 != "UNK":
            return iso3
    except Exception:
        pass

    return None
