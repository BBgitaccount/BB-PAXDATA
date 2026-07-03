"""
Actor Resolver Service for mapping extracted entities to diplomatic actors.
"""

from bb_paxdata.application.domain.lexicon.country_bloc_mapping import normalize_country

# SPEAKER_MAP: name -> (country, role, power_level)
SPEAKER_MAP = {
    "Erdoğan": ("Turkey", "President", 10),
    "Fidan": ("Turkey", "Foreign Minister", 9),
    "Zelenskyy": ("Ukraine", "President", 9),
    "Putin": ("Russia", "President", 10),
    "Biden": ("USA", "President", 10),
    "Guterres": ("UN", "Secretary-General", 8),
}


class ActorResolver:
    """
    Resolves raw text entities to canonical diplomatic actors.
    """

    @staticmethod
    def resolve_actor(text: str) -> str | None:
        """
        Map a text string to a canonical country or organization name.

        Args:
            text: The raw entity text (e.g., "Türkiye Cumhuriyeti").

        Returns:
            The canonical name (e.g., "Turkey") or None if not resolved.
        """
        if not text:
            return None

        # Use the standard normalization function from country_bloc_mapping
        # This ensures consistent handling of Turkey/turkey/Türkiye variations
        iso3, standard_name, _ = normalize_country(text)

        if iso3 != "UNK":
            return standard_name

        # 2. Check SPEAKER_MAP matches
        text_lower = text.lower()
        for name, (country, _, _) in SPEAKER_MAP.items():
            if name.lower() in text_lower:
                return country

        return None
