from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from bb_paxdata.domain.enums.negation_type import NegationType


class NegationCue(BaseModel):
    """Bir negasyon cue'unun domain modeli.

    Morante & Blanco (2012)'ye göre: cue → scope → focus üçlüsü.
    Immutable. Her güncelleme model_copy(update=...) ile yapılır.
    """

    model_config = ConfigDict(frozen=False, strict=True)

    cue_text: str = Field(..., min_length=1, description="Negasyon işaretçisi metni")
    cue_start: int = Field(..., ge=0, description="Cue başlangıç karakter indeksi")
    cue_end: int = Field(..., ge=0, description="Cue bitiş karakter indeksi")

    # Scope: negasyonun etki alanındaki token indeksleri (spaCy token.i)
    scope_token_indices: Sequence[int] = Field(
        default_factory=tuple, description="Scope'daki token indexleri"
    )
    scope_text: str | None = Field(default=None, description="Scope metni (span.text)")

    # Focus: scope içinde negasyonun odaklandığı token
    focus_token_index: int | None = Field(
        default=None, description="Focus token indeksi"
    )
    focus_text: str | None = Field(default=None, description="Focus metni")

    negation_type: NegationType = Field(..., description="Morante & Blanco taksonomisi")

    # Metadata
    sentence_id: str = Field(..., description="Ait olduğu sentence UUID")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Scope detection güven skoru"
    )

    # Safe property: scope var mı?
    @property
    def has_scope(self) -> bool:
        return len(self.scope_token_indices) > 0

    def with_scope(
        self,
        indices: Sequence[int],
        text: str,
        focus_idx: int | None = None,
        focus_txt: str | None = None,
    ) -> "NegationCue":
        """Immutable scope güncellemesi."""
        from typing import Any

        update_dict: dict[str, Any] = {
            "scope_token_indices": tuple(indices),
            "scope_text": text,
        }
        if focus_idx is not None:
            update_dict["focus_token_index"] = focus_idx
        if focus_txt is not None:
            update_dict["focus_text"] = focus_txt
        return self.model_copy(update=update_dict)
