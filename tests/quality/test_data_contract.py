"""Tests for DataContractValidator."""

from pathlib import Path

import pandas as pd  # type: ignore
from bb_paxdata.quality.data_contract import (
    DataContractValidator,
    TranscriptInputContract,
)


class TestTranscriptInputContract:
    """Test transcript input validation."""

    def test_valid_transcript(self) -> None:
        """Test validation of valid transcript."""
        valid_text = """
        Speaker 1: Hello everyone, welcome to the panel.
        Speaker 2: Thank you for having me here today.
        Speaker 1: Let's begin with the first topic.
        """

        result = TranscriptInputContract.validate(valid_text, Path("test.txt"))

        assert result.passed is True
        assert "validation passed" in result.message.lower()

    def test_empty_transcript(self) -> None:
        """Test validation of empty transcript."""
        result = TranscriptInputContract.validate("", Path("empty.txt"))

        assert result.passed is False
        assert "very short" in result.message.lower()

    def test_short_transcript(self) -> None:
        """Test validation of very short transcript."""
        result = TranscriptInputContract.validate("Hi", Path("short.txt"))

        assert result.passed is False
        assert "very short" in result.message.lower()

    def test_no_delimiter_transcript(self) -> None:
        """Test transcript without speaker delimiter."""
        text = "Hello everyone welcome to the panel. Thank you for having me."
        result = TranscriptInputContract.validate(text, Path("no_delim.txt"))

        assert result.passed is False
        assert "delimiter" in result.message.lower()

    def test_large_transcript(self) -> None:
        """Test oversized transcript."""
        large_text = "x" * 51_000_000  # 51MB
        result = TranscriptInputContract.validate(large_text, Path("large.txt"))

        assert result.passed is False
        assert "50mb" in result.message.lower()


class TestAISentenceOutputSchema:
    """Test AI output schema validation."""

    def test_valid_ai_output(self) -> None:
        """Test validation of valid AI output."""
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001", "sent_002"],
                "AI_Duygu_Skoru": [0.2, -0.5],
                "AI_Risk_Skoru": [3, 7],
                "AI_Potansiyel_Risk": ["low", "high"],
                "AI_Diplomatik_Ton": ["neutral", "assertive"],
                "AI_Manipulasyon_Skor": [0.1, 0.4],
                "AI_Talep_Var": [0, 1],
                "AI_Birincil_Konu": ["Ekonomi", "Güvenlik"],
                "AI_Cerceveleme": ["economic_frame", "security_frame"],
            }
        )

        validator = DataContractValidator()
        result = validator.validate_ai_output(df)

        assert result.passed is True
        assert result.details["row_count"] == 2

    def test_invalid_sentiment_range(self) -> None:
        """Test invalid sentiment score range."""
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001"],
                "AI_Duygu_Skoru": [1.5],  # Invalid: > 1.0
                "AI_Risk_Skoru": [3],
                "AI_Potansiyel_Risk": ["low"],
                "AI_Diplomatik_Ton": ["neutral"],
                "AI_Manipulasyon_Skor": [0.1],
                "AI_Talep_Var": [0],
            }
        )

        validator = DataContractValidator()
        result = validator.validate_ai_output(df)

        assert result.passed is False
        assert "schema error" in result.message.lower()

    def test_invalid_risk_range(self) -> None:
        """Test invalid risk score range."""
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001"],
                "AI_Duygu_Skoru": [0.2],
                "AI_Risk_Skoru": [15],  # Invalid: > 10
                "AI_Potansiyel_Risk": ["low"],
                "AI_Diplomatik_Ton": ["neutral"],
                "AI_Manipulasyon_Skor": [0.1],
                "AI_Talep_Var": [0],
            }
        )

        validator = DataContractValidator()
        result = validator.validate_ai_output(df)

        assert result.passed is False
        assert "schema error" in result.message.lower()

    def test_invalid_risk_category(self) -> None:
        """Test invalid risk category."""
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001"],
                "AI_Duygu_Skoru": [0.2],
                "AI_Risk_Skoru": [3],
                "AI_Potansiyel_Risk": ["invalid_category"],  # Invalid
                "AI_Diplomatik_Ton": ["neutral"],
                "AI_Manipulasyon_Skor": [0.1],
                "AI_Talep_Var": [0],
            }
        )

        validator = DataContractValidator()
        result = validator.validate_ai_output(df)

        assert result.passed is False
        assert "schema error" in result.message.lower()

    def test_missing_required_fields(self) -> None:
        """Test missing required fields."""
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001"],
                "AI_Duygu_Skoru": [0.2],
                # Missing AI_Risk_Skoru
                "AI_Potansiyel_Risk": ["low"],
                "AI_Diplomatik_Ton": ["neutral"],
                "AI_Manipulasyon_Skor": [0.1],
                "AI_Talep_Var": [0],
            }
        )

        validator = DataContractValidator()
        result = validator.validate_ai_output(df)

        assert result.passed is False
        assert "schema error" in result.message.lower()

    def test_non_dataframe_input(self) -> None:
        """Test non-DataFrame input."""
        validator = DataContractValidator()
        result = validator.validate_ai_output("not a dataframe")

        assert result.passed is False
        assert "not a pandas dataframe" in result.message.lower()


class TestDataContractValidator:
    """Test main DataContractValidator."""

    def test_validator_initialization(self) -> None:
        """Test validator initialization."""
        validator = DataContractValidator()
        assert validator is not None
        assert hasattr(validator, "logger")

    def test_integration_workflow(self) -> None:
        """Test complete validation workflow."""
        validator = DataContractValidator()

        # Test input validation
        transcript = """
        Speaker 1: Welcome to our discussion.
        Speaker 2: Thank you for inviting me.
        """
        input_result = validator.validate_transcript_input(transcript, Path("test.txt"))
        assert input_result.passed is True

        # Test output validation
        df = pd.DataFrame(
            {
                "sent_id": ["sent_001"],
                "AI_Duygu_Skoru": [0.1],
                "AI_Risk_Skoru": [4],
                "AI_Potansiyel_Risk": ["medium"],
                "AI_Diplomatik_Ton": ["neutral"],
                "AI_Manipulasyon_Skor": [0.2],
                "AI_Talep_Var": [0],
            }
        )
        output_result = validator.validate_ai_output(df)
        assert output_result.passed is True
