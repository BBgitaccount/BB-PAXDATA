"""
Actor Resolver Service for mapping extracted entities to diplomatic actors.
"""

# Mock definitions for NER_GPE and SPEAKER_MAP as mentioned in Faz5.md
# In a real scenario, these would be loaded from a more robust configuration or
# database.
NER_GPE = {
    "Türkiye",
    "Turkey",
    "Turkey Republic",
    "Türkiye Cumhuriyeti",
    "Ukraine",
    "Ukrayna",
    "Russia",
    "Rusya",
    "Russian Federation",
    "USA",
    "United States",
    "ABD",
    "NATO",
    "EU",
    "AB",
    "UN",
    "BM",
}

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

        text_lower = text.lower()

        # 1. Check direct NER_GPE matches
        for country in NER_GPE:
            if country.lower() in text_lower:
                # Return canonical name (we use the first one in NER_GPE as a simple
                # heuristic)
                # In a real app, this would be a dict mapping.
                if "türkiye" in country.lower() or "turkey" in country.lower():
                    return "Turkey"
                if "ukrayna" in country.lower() or "ukraine" in country.lower():
                    return "Ukraine"
                if "rusya" in country.lower() or "russia" in country.lower():
                    return "Russia"
                return country

        # 2. Check SPEAKER_MAP matches
        for name, (country, _, _) in SPEAKER_MAP.items():
            if name.lower() in text_lower:
                return country

        return None
