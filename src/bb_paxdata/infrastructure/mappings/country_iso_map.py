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


def get_country_aliases(country: str) -> list[str]:
    """
    Given a country name or ISO-3 code (e.g., "TUR" or "Turkey"),
    returns a list of known aliases/names for that country
    to match database records.
    """
    if not country:
        return []

    country_clean = country.strip()
    country_upper = country_clean.upper()

    aliases = {country_clean}

    # 1. If it's a 3-letter ISO code, find all matching keys in COUNTRY_ISO_MAP
    # Also find standard names in country_bloc_mapping if available
    iso3 = None
    if len(country_clean) == 3:
        iso3 = country_upper
    else:
        # Get ISO-3 from map
        iso3 = COUNTRY_ISO_MAP.get(country_clean)
        if not iso3:
            # Try case-insensitive
            for k, v in COUNTRY_ISO_MAP.items():
                if k.upper() == country_upper:
                    iso3 = v
                    break

    if iso3:
        aliases.add(iso3)
        aliases.add(iso3.lower())
        # Find all keys in COUNTRY_ISO_MAP that map to this ISO-3
        for k, v in COUNTRY_ISO_MAP.items():
            if v == iso3:
                aliases.add(k)

        # Also check standard country bloc mapping
        try:
            from bb_paxdata.application.domain.lexicon.country_bloc_mapping import (
                COUNTRY_BLOC_MAP,
            )

            if iso3 in COUNTRY_BLOC_MAP:
                info = COUNTRY_BLOC_MAP[iso3]
                aliases.add(info["name"])
        except Exception:
            pass

    return sorted(list(aliases))


def is_unknown_country(country_name: str | None) -> bool:
    """
    Returns True if the country name represents an unknown country.
    """
    if not country_name:
        return True
    name = country_name.strip()
    if name.upper() in ("UNKNOWN", "UNK"):
        return True
    if get_iso_alpha3(name) is None:
        return True
    return False
