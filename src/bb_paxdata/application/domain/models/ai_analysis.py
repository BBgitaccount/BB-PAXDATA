# ============================================================
# DOSYA: src/bb_paxdata/domain/models/ai_analysis.py
# AÇIKLAMA: AIAnalyst servisinin dönüş tipi — Pydantic DTO
# ============================================================


from typing import Optional

from pydantic import BaseModel, Field, computed_field

from bb_paxdata.application.domain.models.appraisal_vector import AppraisalVector
from bb_paxdata.application.domain.models.argument import ArgumentGraph
from bb_paxdata.application.domain.models.presupposition import Presupposition


class AIAnalysisResult(BaseModel):
    """
    AIAnalyst.analyze() metodunun dönüş tipi.
    Ham dict yerine Pydantic modeli kullanılır → tip güvenliği + validasyon.
    """

    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    sentiment_label: str | None = None
    risk_factors: list[str] = Field(default_factory=list)
    summary: str | None = None
    key_claims: list[str] = Field(default_factory=list)
    raw_output: str | None = Field(default=None, description="Ham AI metin yanıtı")

    # Audit trail alanları — AnalysisAssembler tarafından Analysis modeline aktarılır
    prompt_version: str = Field(description="prompt_id@version formatı")
    prompt_hash: str | None = Field(
        default=None, description="SHA256 hash (ilk 16 karakter)"
    )
    model_name: str = Field(default="", description="Kullanılan AI modeli")

    # Hata durumunda doldurulur
    error: str | None = None
    parse_error: str | None = None

    # === TASK-A02 Entegrasyonu ===
    argument_graph: Optional[ArgumentGraph] = Field(
        default=None,
        description="Peldszus & Stede (2013) argumentation structure graph",
    )
    argument_quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall argumentation quality metric (coherence, coverage)",
    )
    key_claims_extracted: list[str] = Field(
        default_factory=list, description="Top-N most important claims identified"
    )
    controversy_level: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Discourse controversy indicator (0=consensus, 1=highly contested)",
    )

    # === TASK-A03 Entegrasyonu ===
    appraisal_vector: Optional[AppraisalVector] = Field(
        default=None, description="Appraisal theory evaluation vector"
    )
    appraisal_judgment_sanction_count: int = Field(
        default=0, ge=0, description="Total negative social sanction judgments"
    )
    dominant_appraisal_axis: Optional[str] = Field(
        default=None,
        description="Dominant appraisal axis (AFFECT, JUDGMENT, APPRECIATION)",
    )

    # === TASK-A06 Entegrasyonu ===
    hidden_commitments: list[Presupposition] = Field(
        default_factory=list,
        description=(
            "Presuppositions extracted per Lewis (1979) / Beaver & Geurts (2014). "
            "Populated by PresuppositionService post-TASK-A01 SRL enrichment."
        ),
    )

    @computed_field
    @property
    def hidden_commitment_count(self) -> int:
        return len(self.hidden_commitments)

    @computed_field
    @property
    def commitment_by_type(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for p in self.hidden_commitments:
            result[p.trigger_type.value] = result.get(p.trigger_type.value, 0) + 1
        return result

    @property
    def appraisal_attitude_from_vector(self) -> str:
        """
        Bridge: derive legacy AppraisalAttitude string from AppraisalVector.
        Supersedes ai_appraisal_attitude for downstream rules.
        Returns: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
        """
        if self.appraisal_vector is None or not self.appraisal_vector.has_any_detection:
            val = getattr(self, "ai_appraisal_attitude", "NEUTRAL") or "NEUTRAL"
            return str(val).upper()
        v = self.appraisal_vector
        dominant_score = max(
            v.affect_score * v.affect_confidence,
            v.judgment_score * v.judgment_confidence,
            v.appreciation_score * v.appreciation_confidence,
            key=abs,
        )
        if dominant_score > 0.15:
            return "POSITIVE"
        if dominant_score < -0.15:
            return "NEGATIVE"
        return "NEUTRAL"

    @property
    def has_argument_analysis(self) -> bool:
        """Check if argument graph analysis completed."""
        return self.argument_graph is not None and len(self.argument_graph.nodes) > 0

    def get_summary_arguments(self, top_n: int = 5) -> list[dict]:
        """Extract top-N most significant arguments for reporting."""
        # Assign to local variable so type checkers (and runtime) know
        # argument_graph cannot be None past this point.
        graph = self.argument_graph
        if graph is None or len(graph.nodes) == 0:
            return []

        # Sort by confidence × depth weight
        scored_nodes = [
            {
                "segment_id": node.segment_id,
                "text": node.text[:200],
                "type": node.node_type.value,
                "speaker": node.speaker,
                "confidence": node.confidence,
                "significance": node.confidence * (1 + node.depth * 0.1),
            }
            for node in graph.nodes
        ]

        scored_nodes.sort(key=lambda x: x["significance"], reverse=True)
        return scored_nodes[:top_n]
