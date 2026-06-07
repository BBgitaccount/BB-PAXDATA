"""Drift events model for temporal analysis."""

from typing import TYPE_CHECKING, Literal, get_args

_DRIFT_TYPE_V1 = Literal["SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK"]
_DRIFT_TYPE_V2 = Literal[
    "SENTIMENT", "TOPIC", "LEXICAL", "TONE", "RISK", "ILLOCUTIONARY"
]


def normalize_drift_type(value: str) -> _DRIFT_TYPE_V2:
    if value in get_args(_DRIFT_TYPE_V2):
        return value  # type: ignore[return-value]
    return "RISK"  # Safe fallback for legacy rows


from sqlalchemy import Integer, String, Text  # noqa: E402
from sqlalchemy.orm import Mapped, mapped_column  # noqa: E402

from bb_paxdata.infrastructure.db.base import Base  # noqa: E402

if TYPE_CHECKING:
    pass


class DriftEvent(Base):
    """Tracks temporal drift events in speaker language."""

    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    speaker_id: Mapped[str] = mapped_column(String, nullable=False)
    panel_id: Mapped[str] = mapped_column(String, nullable=False)
    drift_type: Mapped[_DRIFT_TYPE_V2] = mapped_column(String, nullable=False)
    start_position: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # global_sent_order
    end_position: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = mapped_column(
        String, nullable=False
    )
    before_state: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Örn: "cooperative tone"
    after_state: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Örn: "confrontational tone"
    confidence: Mapped[float] = mapped_column(Integer, nullable=False)
    algorithm: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "CUSUM", "JS_DIVERGENCE", "MATTR"
