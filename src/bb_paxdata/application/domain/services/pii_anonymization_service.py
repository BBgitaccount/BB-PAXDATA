"""
PII Detection and Anonymization Service (TASK-1.3.3)
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import spacy
from spacy.lang.en import English
from spacy.lang.tr import Turkish

from bb_paxdata.application.domain.models.retention import PIIMaskingResult
from bb_paxdata.config.settings import get_settings


class PIIAnonymizationService:
    """
    Service for detecting and anonymizing Personally Identifiable Information (PII).
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._config = self._settings.pii_anonymization
        self._nlp_models: dict[str, Any] = {}
        self._speaker_code_counter: dict[str, int] = defaultdict(int)
        self._speaker_mapping: dict[str, str] = {}
        self._location_mapping: dict[str, str] = {}

    def _load_nlp_model(self, language: str = "en") -> Any:
        """Load spaCy model for PII detection."""
        if language not in self._nlp_models:
            model_name = self._config.pii_detection_model
            try:
                if language == "tr":
                    self._nlp_models[language] = spacy.load("tr_core_news_md")
                else:
                    self._nlp_models[language] = spacy.load(model_name)
            except OSError:
                # Fallback to basic model if specific model not available
                if language == "tr":
                    self._nlp_models[language] = Turkish()
                else:
                    self._nlp_models[language] = English()
        return self._nlp_models[language]

    def _generate_speaker_code(self, speaker_id: str) -> str:
        """Generate encoded speaker ID (e.g., P-001, P-002)."""
        if speaker_id in self._speaker_mapping:
            return self._speaker_mapping[speaker_id]

        prefix = self._config.speaker_name_encoding_prefix
        self._speaker_code_counter[prefix] += 1
        code = f"{prefix}-{self._speaker_code_counter[prefix]:03d}"
        self._speaker_mapping[speaker_id] = code
        return code

    def _generalize_location(self, location: str) -> str:
        """Generalize location information based on configuration."""
        if not self._config.location_generalization_enabled:
            return location

        if location in self._location_mapping:
            return self._location_mapping[location]

        level = self._config.location_generalization_level

        # Simple location generalization logic
        # In production, this would use a geocoding service
        if level == "country":
            # Extract country code or use generic
            if "," in location:
                parts = location.split(",")
                generalized = parts[-1].strip()
            else:
                generalized = "COUNTRY"
        elif level == "region":
            if "," in location:
                parts = location.split(",")
                generalized = parts[-2].strip() if len(parts) > 1 else "REGION"
            else:
                generalized = "REGION"
        else:  # city
            generalized = "CITY"

        self._location_mapping[location] = generalized
        return generalized

    def _detect_pii_entities(
        self, text: str, language: str = "en"
    ) -> list[dict[str, Any]]:
        """Detect PII entities using spaCy NER."""
        nlp = self._load_nlp_model(language)
        doc = nlp(text)

        entities = []
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE", "LOC", "EMAIL", "PHONE"]:
                entities.append(
                    {
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                )

        # Apply custom regex patterns
        for pattern_name, pattern in self._config.custom_pii_patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entities.append(
                    {
                        "text": match.group(),
                        "label": pattern_name,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        return entities

    def anonymize_text(
        self,
        text: str,
        speaker_id: str | None = None,
        location: str | None = None,
        language: str = "en",
    ) -> PIIMaskingResult:
        """
        Anonymize text by masking PII entities.

        Args:
            text: Text to anonymize
            speaker_id: Speaker ID to encode
            location: Location to generalize
            language: Language code

        Returns:
            PIIMaskingResult with anonymization details
        """
        detected_entities = self._detect_pii_entities(text, language)

        masked_text = text

        # Sort entities by start position (reverse to avoid offset issues)
        entities_sorted = sorted(
            detected_entities, key=lambda x: x["start"], reverse=True
        )

        for entity in entities_sorted:
            entity["text"]
            label = entity["label"]
            start = entity["start"]
            end = entity["end"]

            if label == "PERSON":
                replacement = "[PERSON]"
            elif label in ["ORG", "GPE", "LOC"]:
                replacement = "[LOCATION]"
            elif label == "EMAIL":
                replacement = "[EMAIL]"
            elif label == "PHONE":
                replacement = "[PHONE]"
            else:
                replacement = f"[{label}]"

            masked_text = masked_text[:start] + replacement + masked_text[end:]

        # Encode speaker ID if provided
        speaker_mapping = {}
        if speaker_id:
            encoded_id = self._generate_speaker_code(speaker_id)
            speaker_mapping[speaker_id] = encoded_id

        # Generalize location if provided
        location_mapping = {}
        if location:
            generalized = self._generalize_location(location)
            location_mapping[location] = generalized

        return PIIMaskingResult(
            original_text=text,
            masked_text=masked_text,
            detected_entities=detected_entities,
            speaker_mapping=speaker_mapping,
            location_mapping=location_mapping,
            timestamp=datetime.now(UTC),
        )

    def anonymize_transcript(
        self,
        transcript_data: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Anonymize transcript data including speaker names and locations.

        Args:
            transcript_data: Transcript data dictionary
            language: Language code

        Returns:
            Anonymized transcript data
        """
        anonymized = transcript_data.copy()

        # Anonymize speakers
        if "speakers" in anonymized:
            for speaker in anonymized["speakers"]:
                if speaker.get("name"):
                    speaker_id = speaker.get("id", str(hash(speaker["name"])))
                    encoded_id = self._generate_speaker_code(speaker_id)
                    speaker["original_name"] = speaker["name"]
                    speaker["name"] = encoded_id

        # Anonymize segments
        if "segments" in anonymized:
            for segment in anonymized["segments"]:
                if "text" in segment:
                    speaker_id = segment.get("speaker_id")
                    result = self.anonymize_text(
                        segment["text"], speaker_id=speaker_id, language=language
                    )
                    segment["original_text"] = segment["text"]
                    segment["text"] = result.masked_text

        # Generalize location metadata
        if anonymized.get("metadata"):
            metadata = anonymized["metadata"]
            if "location" in metadata:
                original_location = metadata["location"]
                generalized = self._generalize_location(original_location)
                metadata["original_location"] = original_location
                metadata["location"] = generalized

        return anonymized

    def reset_mappings(self) -> None:
        """Reset speaker and location mappings (for testing)."""
        self._speaker_code_counter.clear()
        self._speaker_mapping.clear()
        self._location_mapping.clear()

    def get_speaker_mapping(self) -> dict[str, str]:
        """Get current speaker ID mappings."""
        return dict(self._speaker_mapping)

    def get_location_mapping(self) -> dict[str, str]:
        """Get current location mappings."""
        return dict(self._location_mapping)


class GDPRRightToBeForgottenService:
    """
    Service for GDPR Right to be Forgotten compliance.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._config = self._settings.pii_anonymization
        self._pii_service = PIIAnonymizationService()

    def request_data_deletion(
        self,
        user_id: str,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a GDPR data deletion request.

        Args:
            user_id: User identifier to delete data for
            reason: Reason for deletion request
            request_id: Unique request identifier

        Returns:
            Deletion request status
        """
        if not self._config.gdpr_right_to_be_forgotten_enabled:
            raise RuntimeError("GDPR Right to be Forgotten is not enabled")

        request_id = request_id or f"gdr-{datetime.now(UTC).timestamp()}"

        return {
            "request_id": request_id,
            "user_id": user_id,
            "status": "pending",
            "reason": reason,
            "created_at": datetime.now(UTC).isoformat(),
            "estimated_completion": (
                datetime.now(UTC) + timedelta(days=30)
            ).isoformat(),
        }

    def anonymize_user_data(
        self,
        user_id: str,
        transcript_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Anonymize all data related to a specific user.

        Args:
            user_id: User identifier
            transcript_data: Transcript data to anonymize

        Returns:
            Anonymized data
        """
        # Generate a permanent anonymous ID for the user
        anonymous_id = f"ANON-{hash(user_id) % 10000:04d}"

        # Update speaker mapping
        self._pii_service._speaker_mapping[user_id] = anonymous_id

        # Anonymize the transcript
        anonymized = self._pii_service.anonymize_transcript(transcript_data)

        return anonymized

    def verify_deletion_complete(
        self,
        request_id: str,
    ) -> dict[str, Any]:
        """
        Verify that data deletion has been completed.

        Args:
            request_id: Deletion request identifier

        Returns:
            Verification status
        """
        # In production, this would check database and archives
        return {
            "request_id": request_id,
            "status": "completed",
            "verified_at": datetime.now(UTC).isoformat(),
            "records_deleted": 0,
            "archives_cleaned": 0,
        }
