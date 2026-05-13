"""Data contract validation using Pandera for input/output validation."""

from collections.abc import Sized
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pandera as pa
import structlog
from pandera.typing import Series

logger = structlog.get_logger(__name__)


class AISentenceOutputSchema(pa.DataFrameModel):
    """AI analizi sonrası DataFrame validasyonu."""

    sent_id: Series[str] = pa.Field(nullable=False)
    AI_Duygu_Skoru: Series[float] = pa.Field(ge=-1.0, le=1.0, nullable=True)
    AI_Risk_Skoru: Series[int] = pa.Field(ge=0, le=10, nullable=True)
    AI_Potansiyel_Risk: Series[str] = pa.Field(
        isin=["none", "low", "medium", "high", "critical"], nullable=True
    )
    AI_Diplomatik_Ton: Series[str] = pa.Field(
        isin=[
            "assertive",
            "conciliatory",
            "evasive",
            "confrontational",
            "neutral",
            "persuasive",
            "defensive",
        ],
        nullable=True,
    )
    AI_Manipulasyon_Skor: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=True)
    AI_Talep_Var: Series[int] = pa.Field(isin=[0, 1], nullable=True)
    AI_Birincil_Konu: Series[str] = pa.Field(nullable=True)
    AI_Cerceveleme: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = True


class ValidationResult:
    """Validation result container."""

    def __init__(
        self, passed: bool, message: str = "", details: dict[str, Any] | None = None
    ) -> None:
        self.passed = passed
        self.message = message
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.passed


class TranscriptInputContract:
    """Pre-parse validation for transcript files."""

    @staticmethod
    def validate(raw_text: str, file_path: Path) -> ValidationResult:
        """
        Validate transcript input before parsing.

        Args:
            raw_text: Raw transcript content
            file_path: Path to transcript file

        Returns:
            ValidationResult with pass/fail status and details
        """
        checks = [
            (len(raw_text.strip()) > 100, "Dosya çok kısa veya boş"),
            (raw_text.count("\n") >= 2, "Yetersiz satır sayısı"),
            (":" in raw_text or "[" in raw_text, "Konuşmacı ayırıcı bulunamadı"),
            (len(raw_text.encode("utf-8")) < 50_000_000, "Dosya 50MB'tan büyük"),
        ]

        failed_checks = []
        for check, error_msg in checks:
            if not check:
                failed_checks.append(error_msg)

        if failed_checks:
            logger.warning(
                "Transcript validation failed",
                file_path=str(file_path),
                errors=failed_checks,
            )
            return ValidationResult(
                passed=False,
                message=f"Transcript validation failed: {'; '.join(failed_checks)}",
                details={"failed_checks": failed_checks, "file_path": str(file_path)},
            )

        logger.info("Transcript validation passed", file_path=str(file_path))
        return ValidationResult(
            passed=True,
            message="Transcript validation passed",
            details={"file_path": str(file_path), "text_length": len(raw_text)},
        )


class DataContractValidator:
    """Main data contract validator for both input and output validation."""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(__name__)

    def validate_transcript_input(
        self, raw_text: str, file_path: Path
    ) -> ValidationResult:
        """Validate transcript input before parsing."""
        return TranscriptInputContract.validate(raw_text, file_path)

    def validate_ai_output(self, df: "pd.DataFrame") -> ValidationResult:
        """
        Validate AI analysis output using Pandera schema.

        Args:
            df: DataFrame containing AI analysis results

        Returns:
            ValidationResult with pass/fail status and details
        """
        try:
            # Import here to avoid circular imports
            import pandas as pd

            # Ensure we have a DataFrame
            if not isinstance(df, pd.DataFrame):
                return ValidationResult(
                    passed=False,
                    message="Input is not a pandas DataFrame",
                    details={"input_type": str(type(df))},
                )

            # Validate against schema
            validated_df = AISentenceOutputSchema.validate(df)

            self.logger.info(
                "AI output validation passed",
                row_count=len(cast(Sized, validated_df)),
            )

            return ValidationResult(
                passed=True,
                message="AI output validation passed",
                details={"row_count": len(cast(Sized, validated_df))},
            )

        except pa.errors.SchemaError as e:
            self.logger.error(
                "AI output validation failed",
                error=str(e),
                failure_cases=str(e.failure_cases),
            )

            return ValidationResult(
                passed=False,
                message=f"AI output validation failed: {str(e)}",
                details={
                    "schema_error": str(e),
                    "failure_cases": (
                        str(e.failure_cases) if hasattr(e, "failure_cases") else None
                    ),
                },
            )
        except Exception as e:
            self.logger.error("Unexpected validation error", error=str(e))

            return ValidationResult(
                passed=False,
                message=f"Unexpected validation error: {str(e)}",
                details={"error_type": type(e).__name__},
            )
