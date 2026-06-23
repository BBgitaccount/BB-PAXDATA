"""Demand detection service for diplomatic demand analysis."""

import re
from typing import Any

from bb_paxdata.application.domain.enums.demand_category import DemandCategory
from bb_paxdata.application.domain.enums.demand_type import DemandType


class DemandDetector:
    """Detect diplomatic demands in text using rule-based approach."""

    # Demand marker lexicon for categorization
    DEMAND_MARKERS = {
        "WITHDRAWAL": [
            "withdraw",
            "withdrawal",
            "pullout",
            "retreat",
            "cease",
            "remove",
            "evacuate",
            "exit",
            "leave",
        ],
        "SANCTION": [
            "sanction",
            "embargo",
            "ban",
            "restrict",
            "freeze",
            "penalize",
            "punish",
            "impose",
        ],
        "COMPLIANCE": [
            "comply",
            "adhere",
            "respect",
            "abide",
            "implement",
            "follow",
            "observe",
            "uphold",
        ],
        "CEASEFIRE": [
            "ceasefire",
            "cease fire",
            "halt",
            "pause",
            "stop fighting",
            "truce",
            "armistice",
        ],
        "NEGOTIATION": [
            "negotiate",
            "dialogue",
            "talks",
            "discuss",
            "mediate",
            "engagement",
            "diplomacy",
        ],
        "HUMANITARIAN": [
            "humanitarian access",
            "aid",
            "relief",
            "evacuate",
            "corridor",
            "assistance",
            "support",
        ],
        "ACCOUNTABILITY": [
            "accountability",
            "justice",
            "tribunal",
            "prosecute",
            "investigate",
            "responsibility",
        ],
        "RECOGNITION": [
            "recognize",
            "acknowledge",
            "accept",
            "admit",
            "endorse",
            "validate",
        ],
    }

    # Demand verbs that indicate a demand is being made
    DEMAND_VERBS = {
        "demand",
        "urge",
        "call upon",
        "insist",
        "require",
        "must",
        "should",
        "need to",
        "have to",
        "obliged to",
        "expected to",
        "request",
        "appeal",
        "ask",
        "expect",
    }

    # Urgency indicators
    URGENCY_KEYWORDS = {
        "CRITICAL": ["immediately", "urgent", "emergency", "crisis", "critical"],
        "HIGH": ["must", "require", "insist", "demand", "essential"],
        "MEDIUM": ["should", "need to", "ought to", "important"],
        "LOW": ["call upon", "urge", "request", "appeal", "encourage"],
    }

    def __init__(self):
        """Initialize the demand detector."""
        # Compile regex patterns for efficiency
        self._verb_patterns = [
            re.compile(rf"\b{re.escape(verb)}\b", re.IGNORECASE)
            for verb in self.DEMAND_VERBS
        ]
        self._marker_patterns = {
            category: [
                re.compile(rf"\b{re.escape(marker)}\b", re.IGNORECASE)
                for marker in markers
            ]
            for category, markers in self.DEMAND_MARKERS.items()
        }

    def detect_demand(
        self,
        text: str,
        speaker_name: str | None = None,
        country: str | None = None,
        entities: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Detect if a sentence contains a diplomatic demand.

        Args:
            text: The sentence text to analyze
            speaker_name: Name of the speaker (optional)
            country: Country of the speaker (optional)
            entities: List of named entities found in the text (optional)

        Returns:
            Dictionary with demand information if detected, None otherwise
        """
        text_lower = text.lower()

        # Check for demand verbs
        demand_verb = None
        for pattern in self._verb_patterns:
            match = pattern.search(text_lower)
            if match:
                demand_verb = match.group().lower()
                break

        if not demand_verb:
            return None

        # Determine demand type based on markers
        demand_type = None
        matched_marker = None
        for category, patterns in self._marker_patterns.items():
            for pattern in patterns:
                if pattern.search(text_lower):
                    demand_type = category
                    matched_marker = pattern.search(text_lower).group()
                    break
            if demand_type:
                break

        # Default to INTENTION if no specific marker found
        if not demand_type:
            demand_type = "INTENTION"

        # Determine urgency level
        urgency_level = self._detect_urgency(text_lower)

        # Determine target entity from entities or context
        target_entity = self._extract_target(text, entities)

        # Calculate confidence score
        confidence = self._calculate_confidence(
            text_lower, demand_verb, matched_marker, urgency_level
        )

        # Map to domain enums
        demand_category = self._map_to_category(demand_type)
        demand_type_enum = self._map_to_demand_type(demand_verb, urgency_level)

        return {
            "demand_verb": demand_verb,
            "demand_type": demand_type,
            "demand_category": demand_category.value if demand_category else None,
            "target_entity": target_entity,
            "urgency_level": urgency_level,
            "confidence_score": confidence,
            "demand_type_enum": demand_type_enum.value if demand_type_enum else None,
        }

    def _detect_urgency(self, text: str) -> str:
        """Detect urgency level from text."""
        for level, keywords in self.URGENCY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return level
        return "MEDIUM"

    def _extract_target(
        self, text: str, entities: list[str] | None = None
    ) -> str | None:
        """Extract target entity from text or named entities."""
        # If entities provided, look for the most likely target
        if entities:
            # Filter for likely targets (countries, organizations)
            for entity in entities:
                entity_lower = entity.lower()
                # Skip if it's likely the speaker referring to themselves
                if any(
                    word in entity_lower
                    for word in ["we", "our", "us", "government", "state"]
                ):
                    continue
                return entity

        # Fallback: look for capitalized words that might be entities
        words = text.split()
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 2:
                # Check if it's followed by common entity indicators
                if i < len(words) - 1:
                    next_word = words[i + 1].lower()
                    if next_word in ["must", "should", "needs", "has"]:
                        return word

        return None

    def _calculate_confidence(
        self, text: str, verb: str | None, marker: str | None, urgency: str
    ) -> float:
        """Calculate confidence score for the detection."""
        confidence = 0.5  # Base confidence

        # Boost for explicit demand verbs
        if verb in ["demand", "require", "insist", "must"]:
            confidence += 0.2

        # Boost for specific markers
        if marker:
            confidence += 0.15

        # Boost for high urgency
        if urgency in ["CRITICAL", "HIGH"]:
            confidence += 0.1

        # Cap at 1.0
        return min(confidence, 1.0)

    def _map_to_category(self, demand_type: str) -> DemandCategory | None:
        """Map demand type string to DemandCategory enum."""
        mapping = {
            "WITHDRAWAL": DemandCategory.SECURITY_ACTION,
            "SANCTION": DemandCategory.ECONOMIC_COOPERATION,
            "COMPLIANCE": DemandCategory.DIPLOMATIC_ENGAGEMENT,
            "CEASEFIRE": DemandCategory.SECURITY_ACTION,
            "NEGOTIATION": DemandCategory.DIPLOMATIC_ENGAGEMENT,
            "HUMANITARIAN": DemandCategory.HUMANITARIAN_RESPONSE,
            "ACCOUNTABILITY": DemandCategory.LEGAL_ACCOUNTABILITY,
            "RECOGNITION": DemandCategory.DIPLOMATIC_ENGAGEMENT,
            "INTENTION": DemandCategory.DIPLOMATIC_ENGAGEMENT,
        }
        return mapping.get(demand_type)

    def _map_to_demand_type(self, verb: str, urgency: str) -> DemandType | None:
        """Map verb and urgency to DemandType enum."""
        if urgency == "CRITICAL" or verb in ["demand", "require", "must", "insist"]:
            return DemandType.OBLIGATORY
        elif verb in ["should", "need to", "ought to"]:
            return DemandType.CALL_TO_ACTION
        elif verb in ["call upon", "urge", "appeal", "request"]:
            return DemandType.RECOMMENDATION
        elif verb in ["expect", "expected to"]:
            return DemandType.EXPECTATION
        else:
            return DemandType.INTENTION
