"""
Domain models for Dependency Parsing and Actor-Action Matrix in BB-PAXDATA.
"""

from pydantic import BaseModel


class DependencyTriple(BaseModel):
    """
    Represents a subject-verb-object triple extracted from a sentence.
    """

    sent_id: str
    seg_id: str | None = None
    panel_id: str | None = None
    speaker_name: str | None = None
    country: str | None = None

    subject_raw: str  # e.g., "Türkiye Cumhuriyeti"
    subject_resolved: str  # e.g., "Turkey"
    verb_lemma: str  # e.g., "destekle"
    object_raw: str  # e.g., "Ukrayna'nın toprak bütünlüğü"
    object_resolved: str  # e.g., "Ukraine"

    is_passive: bool = False
    is_negative: bool = False

    sentiment_context: float = 0.0
    risk_score: int = 0

    # SpaCy metadata
    subject_head_pos: str = ""
    object_head_pos: str = ""
    verb_pos: str = ""


class ActorActionMatrix(BaseModel):
    """
    Aggregate matrix of actor actions within a panel.
    """

    panel_id: str
    actor_id: str
    action_type: str
    count: int = 0
    weight: float = 0.0
