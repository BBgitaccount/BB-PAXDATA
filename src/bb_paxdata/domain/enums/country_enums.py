# src/bb_paxdata/domain/enums/country_enums.py
from enum import StrEnum


class RelationshipType(StrEnum):
    """İki ülke arasındaki diplomatik ilişkinin analitik sınıfı."""

    ALLY = "ALLY"
    PARTNER = "PARTNER"
    CAUTIOUS = "CAUTIOUS"
    ADVERSARY = "ADVERSARY"
    NEUTRAL = "NEUTRAL"


class ReferenceContext(StrEnum):
    """Ülke atıfının gerçekleştiği diplomatik bağlam."""

    ACCUSATION = "ACCUSATION"
    PRAISE = "PRAISE"
    NEGOTIATION = "NEGOTIATION"
    THREAT = "THREAT"
    COOPERATION = "COOPERATION"
    NEUTRAL_MENTION = "NEUTRAL_MENTION"


class EdgeType(StrEnum):
    """Söylem ağındaki kenar (edge) tipi."""

    DIPLOMATIC_REFERENCE = "diplomatic_reference"
    CONFRONTATIONAL = "confrontational"
    COOPERATIVE = "cooperative"
    TRANSACTIONAL = "transactional"
