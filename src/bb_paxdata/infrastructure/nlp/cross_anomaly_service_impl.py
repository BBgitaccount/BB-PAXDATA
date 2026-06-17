from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import structlog

from bb_paxdata.application.domain.enums.anomaly_type import AnomalyType
from bb_paxdata.application.domain.enums.country_enums import NarrativeLayer
from bb_paxdata.application.domain.enums.negation_type import NegationType
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.anomaly import ContradictionResult
from bb_paxdata.application.domain.models.argument import (
    ArgumentEdge,
    ArgumentGraph,
    ArgumentNode,
    NodeType,
    RelationType,
)
from bb_paxdata.application.domain.models.negation_cue import NegationCue
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.models.sentence import Sentence
from bb_paxdata.application.domain.models.srl import SRLFrame
from bb_paxdata.application.domain.services.cross_anomaly_service import (
    CrossAnomalyService,
)

logger = structlog.get_logger(__name__)


class ContradictionPattern(str, Enum):
    """Taxonomy of detectable contradiction patterns."""

    EXACT_NEGATION_MISMATCH = "exact_negation_mismatch"
    SENTIMENT_POLARITY_FLIP = "sentiment_polarity_flip"
    MODAL_CERTAINTY_CONFLICT = "modal_certainty_conflict"
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"
    ACTOR_ACTION_MISMATCH = "actor_action_mismatch"
    ARGUMENTATIVE_ATTACK = "argumentative_attack"


@dataclass
class ArgumentContradictionDetail:
    """Detailed breakdown of argument-level contradictions."""

    pattern: ContradictionPattern
    edge: ArgumentEdge
    source_node: ArgumentNode
    target_node: ArgumentNode
    confidence: float
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    evidence: dict = field(default_factory=dict)


@dataclass
class SRLContradictionDetail:
    """Detailed breakdown of an SRL-based contradiction."""

    pattern: ContradictionPattern
    sentence_i_idx: int
    sentence_j_idx: int
    frame_i: SRLFrame
    frame_j: SRLFrame
    confidence: float
    description: str
    evidence: dict = field(default_factory=dict)


class CrossAnomalyServiceImpl(CrossAnomalyService):
    """Tsytsarau (2017) contradiction measure implementasyonu.

    Reference:
        - Tsytsarau, M. et al. (2017). Identifying Sentiment-based
          Contradictions.
          C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)
    """

    # Argument-specific configuration
    SELF_ATTACK_BOOST: float = 0.45  # High: same speaker attacking own claim
    CROSS_SPEAKER_ATTACK_BOOST: float = 0.25  # Medium: different speakers
    REBUTTAL_MISMATCH_PENALTY: float = 0.15  # Missing rebuttal for strong attack
    MAX_GRAPH_NODES_FOR_ANALYSIS: int = 500  # Limit for performance

    # SRL-specific weights (tunable hyperparameters)
    SRL_CONTRADICTION_WEIGHT: float = 0.35
    NEGATION_MISMATCH_BOOST: float = 0.40
    SENTIMENT_FLIP_THRESHOLD: float = -0.2
    ARGUMENT_SIMILARITY_THRESHOLD: float = 0.85  # For fuzzy matching

    async def detect_sentiment_risk_divergence(
        self,
        segment: Segment,
        polarity_values: list[float],
        theta: float = 0.1,
        window: float | None = None,
        threshold: float = 0.5,
    ) -> ContradictionResult:
        """Contradiction measure C hesaplar.

        Args:
            segment: Analiz edilen metin segmenti.
            polarity_values: Her cümlenin polarity skoru (örn. VADER compound).
                             Değer aralığı: [-1.0, 1.0]
            theta: Hassasiyet parametresi (ϑ). Varsayılan 0.1.
            window: Pencere boyutu (W). None ise n kullanılır.
            threshold: Anomali eşiği. C > threshold ise anomali.

        Returns:
            ContradictionResult: Hesaplanan C değeri ve metadata.

        Raises:
            ValueError: polarity_values boş ise.
        """
        if not polarity_values:
            raise ValueError("polarity_values boş olamaz")

        n = len(polarity_values)

        # Moment hesaplamaları
        m1 = sum(polarity_values) / n  # Birinci moment (ortalama)
        m2 = sum(p * p for p in polarity_values) / n  # İkinci moment

        # Pencere boyutu
        w = window if window is not None else float(n)

        # Numerator ve denominator
        # C = (n·M₂ − M₁²) / ((ϑ·n² + M₁²)·W)
        numerator = (n * m2) - (m1 * m1)
        denominator = ((theta * n * n) + (m1 * m1)) * w

        # C değeri (0'a bölme koruması)
        if denominator == 0:
            c = 0.0
        else:
            c = numerator / denominator

        # Faz 2: Negasyon filtrelemesi
        adjustment = self._compute_negation_adjustment(segment.sentences)
        adjusted_score = max(0.0, c - adjustment)
        is_anomaly = adjusted_score > threshold

        return ContradictionResult(
            score=round(adjusted_score, 6),
            threshold=threshold,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            n_sentences=n,
            m1=round(m1, 6),
            m2=round(m2, 6),
            theta=theta,
            window=w,
        )

    def _compute_negation_adjustment(self, sentences: list[Sentence]) -> float:
        """Negasyon kaynaklı false positive'leri hesapla ve düzeltme katsayısı üret."""
        if not sentences:
            return 0.0

        total_adjustment = 0.0
        for sentence in sentences:
            for cue in sentence.negation_cues:
                total_adjustment += self._evaluate_cue_false_positive_risk(
                    cue, sentence
                )

        # Normalize: cümle başına ortalama düzeltme
        return min(1.0, total_adjustment / len(sentences))

    def _evaluate_cue_false_positive_risk(
        self, cue: NegationCue, sentence: Sentence
    ) -> float:
        """Tek bir negasyon cue'yu için false positive risk skoru."""
        # SEMANTIC cue'lar zaten negatif sentiment'tir — contradiction değil
        if cue.negation_type == NegationType.SEMANTIC and cue.confidence > 0.8:
            return 0.35  # Yüksek düzeltme

        # SURFACE cue + kısa scope: VADER zaten negasyon heuristic'i uygular
        if cue.negation_type == NegationType.SURFACE and not cue.has_scope:
            return 0.25

        # SYNTACTIC cue + scope tespiti
        if cue.negation_type == NegationType.SYNTACTIC and cue.has_scope:
            return 0.20

        # SCOPE_WIDE: Geniş kapsamda contradiction daha muhtemeldir, düzeltme az
        if cue.negation_type == NegationType.SCOPE_WIDE:
            return 0.10

        return 0.0

    async def detect_power_asymmetry_anomaly(
        self,
        asymmetry_score: float,
        sentiment_delta: float,
        threshold_asymmetry: float = 0.5,
        threshold_delta: float = -0.3,
    ) -> bool:
        """Güç asimetrisi ve sentiment farkı üzerinden anomali tespiti.

        asymmetry_score > 0.5 + sentiment_delta < -0.3 -> POWER_ASYMMETRY_ANOMALY
        """
        return (
            asymmetry_score > threshold_asymmetry and sentiment_delta < threshold_delta
        )

    async def detect_cheap_talk_anomaly(
        self,
        power_weighted_score: float,
        signal_credibility: float,
        threshold_power: float = 0.1,
        threshold_credibility: float = 0.4,
    ) -> bool:
        """Cheap talk anomalisi tespiti.

        power_weighted_score > threshold + signal_credibility < 0.4 -> CHEAP_TALK_ANOMALY
        """
        return (
            power_weighted_score > threshold_power
            and signal_credibility < threshold_credibility
        )

    async def detect_narrative_clashes(
        self,
        analysis: Analysis,
        threshold: float = 0.5,
    ) -> ContradictionResult:
        """Detect strategic narrative clashes between opposing actors."""
        clash_detected = False
        clash_from = None
        clash_to = None
        clash_salience = 0.0
        identity_layer_count = 0.0
        boost = 0.0

        bilaterals = analysis.bilateral_metrics or []
        for rel in bilaterals:
            layer = getattr(rel, "narrative_layer", None)
            if layer == NarrativeLayer.IDENTITY:
                identity_layer_count += 1.0

            if rel.avg_sentiment < -0.3:
                salience = getattr(rel, "narrative_salience", 0.0)
                if layer == NarrativeLayer.IDENTITY and salience > 0.6:
                    if not clash_detected:
                        clash_from = rel.from_country
                        clash_to = rel.to_country
                        clash_salience = salience
                    clash_detected = True
                    boost += salience * 0.50  # COUNTER_NARRATIVE_BOOST

        final_score = round(min(boost, 1.5), 6)
        is_anomaly = final_score > threshold

        description = ""
        if clash_detected:
            description = (
                f"STRATEGIC NARRATIVE CLASH: Actor '{clash_from}' deflected confrontation "
                f"from '{clash_to}' via IDENTITY pivot. Salience: {clash_salience:.4f}."
            )

        metadata = {
            "narrative_clash": clash_detected,
            "description": description,
        }

        return ContradictionResult(
            score=final_score,
            threshold=threshold,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            n_sentences=len(analysis.sentences or []),
            m1=clash_salience,
            m2=identity_layer_count,
            theta=0.0,
            window=0.0,
            metadata=metadata,
        )

    async def detect_argument_anomalies(
        self,
        argument_graph: ArgumentGraph,
        base_score: float = 0.0,
        threshold: float = 0.5,
    ) -> ContradictionResult:
        """Analyze argument graph for structural anomalies and contradictions."""
        if not argument_graph or not argument_graph.nodes:
            return ContradictionResult(
                score=base_score,
                threshold=threshold,
                is_anomaly=base_score > threshold,
                anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
                n_sentences=0,
                m1=0.0,
                m2=0.0,
                theta=0.0,
                window=0.0,
            )

        # Limit graph size for performance
        if len(argument_graph.nodes) > self.MAX_GRAPH_NODES_FOR_ANALYSIS:
            logger.warning(
                f"Graph too large ({len(argument_graph.nodes)} nodes), "
                f"sampling subset for analysis"
            )
            analyzed_graph = self._sample_graph_for_analysis(argument_graph)
        else:
            analyzed_graph = argument_graph

        argument_boost = 0.0
        contradictions: list[ArgumentContradictionDetail] = []

        # Rule 1: Self-Attack Detection
        self_attacks = analyzed_graph.get_self_attacks()
        for edge, src_node, tgt_node in self_attacks:
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=edge,
                source_node=src_node,
                target_node=tgt_node,
                confidence=edge.confidence * self.SELF_ATTACK_BOOST,
                description=(
                    f"SELF-ATTACK DETECTED: Speaker '{src_node.speaker}' "
                    f"is attacking their own claim '{tgt_node.truncate_display_text(50)}' "
                    f"with '{src_node.truncate_display_text(50)}'. "
                    f"This indicates potential incoherence or rhetorical strategy."
                ),
                severity="high",
                evidence={
                    "speaker": src_node.speaker,
                    "attack_text": src_node.text,
                    "target_text": tgt_node.text,
                    "attack_confidence": edge.confidence,
                },
            )
            contradictions.append(detail)
            argument_boost += detail.confidence

        # Rule 2: Unmatched Strong Attacks
        unmatched_attacks = self._find_unmatched_strong_attacks(analyzed_graph)
        for edge, src_node, tgt_node in unmatched_attacks:
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=edge,
                source_node=src_node,
                target_node=tgt_node,
                confidence=edge.confidence * 0.30,
                description=(
                    f"UNMATCHED STRONG ATTACK: '{src_node.speaker}' attacks "
                    f"'{tgt_node.speaker}'s claim with confidence {edge.confidence:.2f} "
                    f"but no REBUTTAL detected."
                ),
                severity="medium",
                evidence={
                    "attacker": src_node.speaker,
                    "defender": tgt_node.speaker,
                    "attack_strength": edge.confidence,
                },
            )
            contradictions.append(detail)
            argument_boost += detail.confidence

        # Rule 3: Discourse Hostility Ratio
        hostility_ratio = self._compute_hostility_ratio(analyzed_graph)
        if hostility_ratio > 0.7:  # More than 70% of relations are attacks
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=ArgumentEdge(
                    source_id="", target_id="", relation_type=RelationType.ATTACK
                ),
                source_node=ArgumentNode(
                    segment_id="_system",
                    text="System",
                    node_type=NodeType.CLAIM,
                    speaker="_system",
                    timestamp=0.0,
                ),
                target_node=ArgumentNode(
                    segment_id="_system",
                    text="System",
                    node_type=NodeType.CLAIM,
                    speaker="_system",
                    timestamp=0.0,
                ),
                confidence=0.35,
                description=(
                    f"HIGH HOSTILITY DISCOURSE: Attack-to-support ratio is "
                    f"{hostility_ratio:.2%}. This indicates confrontational dialogue."
                ),
                severity="medium",
                evidence={"hostility_ratio": hostility_ratio},
            )
            contradictions.append(detail)
            argument_boost += detail.confidence

        # Rule 4: Isolated Root Claims (no supporting evidence)
        isolated_claims = self._find_isolated_claims(analyzed_graph)
        for claim_node in isolated_claims:
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=ArgumentEdge(
                    source_id="", target_id="", relation_type=RelationType.SUPPORT
                ),
                source_node=claim_node,
                target_node=claim_node,
                confidence=0.20,
                description=(
                    f"ISOLATED CLAIM: '{claim_node.speaker}'s claim "
                    f"'{claim_node.truncate_display_text(40)}' has no supporting arguments."
                ),
                severity="low",
                evidence={"speaker": claim_node.speaker, "claim_text": claim_node.text},
            )
            contradictions.append(detail)
            argument_boost += detail.confidence

        # Compute final score
        final_score = min(base_score + argument_boost, 1.5)
        is_anomaly = final_score > threshold

        result = ContradictionResult(
            score=round(final_score, 6),
            threshold=threshold,
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            n_sentences=len(analyzed_graph.nodes),
            m1=0.0,  # Not applicable for graph analysis
            m2=0.0,
            theta=0.0,
            window=0.0,
        )

        # Attach argument evidence
        if hasattr(result, "extend_metadata"):
            result.extend_metadata(
                {
                    "argument_analysis": {
                        "total_contradictions": len(contradictions),
                        "argument_boost": round(argument_boost, 4),
                        "self_attacks": len(self_attacks),
                        "unmatched_attacks": len(unmatched_attacks),
                        "isolated_claims": len(isolated_claims),
                        "hostility_ratio": round(hostility_ratio, 3),
                        "patterns": [
                            {
                                "pattern": c.pattern.value,
                                "severity": c.severity,
                                "confidence": c.confidence,
                                "description": c.description,
                            }
                            for c in contradictions
                        ],
                    }
                }
            )

        return result

    def _find_unmatched_strong_attacks(
        self, graph: ArgumentGraph, strength_threshold: float = 0.80
    ) -> list[tuple[ArgumentEdge, ArgumentNode, ArgumentNode]]:
        """Find high-confidence attacks without corresponding rebuttals."""
        unmatched = []

        for edge in graph.get_attacks():
            if edge.confidence < strength_threshold:
                continue

            # Check if there's a rebuttal defending the target
            has_rebuttal = any(
                e.relation_type == RelationType.REBUTTAL
                and e.target_id == edge.source_id
                for e in graph.edges
            )

            if not has_rebuttal:
                src = graph.get_node(edge.source_id)
                tgt = graph.get_node(edge.target_id)
                if src and tgt:
                    unmatched.append((edge, src, tgt))

        return unmatched

    def _compute_hostility_ratio(self, graph: ArgumentGraph) -> float:
        """Calculate ratio of attack relations to total relations."""
        if not graph.edges:
            return 0.0

        attack_count = len(graph.get_attacks())
        total_count = len(graph.edges)

        return attack_count / total_count

    def _find_isolated_claims(self, graph: ArgumentGraph) -> list[ArgumentNode]:
        """Find root claims with no incoming SUPPORT edges."""
        isolated = []

        for root_id in graph.root_claim_ids:
            root_node = graph.get_node(root_id)
            if not root_node:
                continue

            # Check for incoming support edges
            has_support = any(
                e.relation_type == RelationType.SUPPORT and e.target_id == root_id
                for e in graph.edges
            )

            if not has_support:
                isolated.append(root_node)

        return isolated

    def _sample_graph_for_analysis(
        self, graph: ArgumentGraph, max_nodes: int = 200
    ) -> ArgumentGraph:
        """Sample manageable subset of large graph for analysis."""
        important_nodes = set()

        # Always include root claims
        important_nodes.update(graph.root_claim_ids)

        # Include neighbors of roots
        for root_id in graph.root_claim_ids:
            for neighbor_id, edge in graph._adjacency_list.get(root_id, []):
                important_nodes.add(neighbor_id)
                if edge.is_attack_relation:
                    important_nodes.add(neighbor_id)

        # Fill remaining slots with high-confidence nodes
        remaining_slots = max_nodes - len(important_nodes)
        if remaining_slots > 0:
            sorted_nodes = sorted(graph.nodes, key=lambda n: n.confidence, reverse=True)
            for node in sorted_nodes:
                if len(important_nodes) >= max_nodes:
                    break
                important_nodes.add(node.segment_id)

        return graph.get_subgraph(important_nodes)

    async def _analyze_srl_contradictions(
        self, sentences: list, polarity_values: list[float]
    ) -> tuple[float, list[SRLContradictionDetail]]:
        """Perform pairwise SRL frame comparison for contradictions."""
        total_boost = 0.0
        contradictions: list[SRLContradictionDetail] = []

        n_sentences = len(sentences)

        for i in range(n_sentences):
            for j in range(i + 1, n_sentences):
                s1, s2 = sentences[i], sentences[j]

                # Skip if either lacks SRL data
                if not (hasattr(s1, "srl_frames") and hasattr(s2, "srl_frames")):
                    continue
                if not s1.srl_frames or not s2.srl_frames:
                    continue

                # Pairwise frame comparison
                for f1 in s1.srl_frames:
                    for f2 in s2.srl_frames:
                        contradiction = self._detect_frame_contradiction(
                            frame_a=f1,
                            frame_b=f2,
                            sent_idx_a=i,
                            sent_idx_b=j,
                            polarity_a=polarity_values[i],
                            polarity_b=polarity_values[j],
                        )

                        if contradiction:
                            contradictions.append(contradiction)
                            total_boost += (
                                contradiction.confidence * self.SRL_CONTRADICTION_WEIGHT
                            )

        return total_boost, contradictions

    def _detect_frame_contradiction(
        self,
        frame_a: SRLFrame,
        frame_b: SRLFrame,
        sent_idx_a: int,
        sent_idx_b: int,
        polarity_a: float,
        polarity_b: float,
    ) -> SRLContradictionDetail | None:
        """Detect contradiction between two SRL frames."""
        # Require both frames to have core arguments
        if not (frame_a.has_complete_triplet and frame_b.has_complete_triplet):
            return None

        # Normalize arguments for comparison
        arg0_match = self._normalize_text(frame_a.actor_text) == self._normalize_text(
            frame_b.actor_text
        )
        arg1_match = self._normalize_text(frame_a.target_text) == self._normalize_text(
            frame_b.target_text
        )

        # Must share both actor and target
        if not (arg0_match and arg1_match):
            return None

        # Pattern 1: Negation mismatch on same verb
        if frame_a.verb == frame_b.verb:
            if frame_a.argm_neg != frame_b.argm_neg:
                return SRLContradictionDetail(
                    pattern=ContradictionPattern.EXACT_NEGATION_MISMATCH,
                    sentence_i_idx=sent_idx_a,
                    sentence_j_idx=sent_idx_b,
                    frame_i=frame_a,
                    frame_j=frame_b,
                    confidence=self.NEGATION_MISMATCH_BOOST,
                    description=(
                        f"Negation conflict: '{frame_a.actor_text}' "
                        f"{'did NOT' if frame_a.argm_neg else 'DID'} '{frame_a.verb}' "
                        f"'{frame_a.target_text}' vs "
                        f"{'did NOT' if frame_b.argm_neg else 'DID'} '{frame_b.verb}'"
                    ),
                    evidence={
                        "verb": frame_a.verb,
                        "neg_a": frame_a.argm_neg,
                        "neg_b": frame_b.argm_neg,
                    },
                )

        # Pattern 2: Sentiment polarity flip
        if (polarity_a * polarity_b) < self.SENTIMENT_FLIP_THRESHOLD:
            return SRLContradictionDetail(
                pattern=ContradictionPattern.SENTIMENT_POLARITY_FLIP,
                sentence_i_idx=sent_idx_a,
                sentence_j_idx=sent_idx_b,
                frame_i=frame_a,
                frame_j=frame_b,
                confidence=abs(polarity_a * polarity_b) * 0.5,
                description=(
                    f"Sentiment flip detected: "
                    f"'{frame_a.actor_text}' → '{frame_a.target_text}' "
                    f"(sentiment: {polarity_a:+.2f} vs {polarity_b:+.2f})"
                ),
                evidence={
                    "polarity_a": polarity_a,
                    "polarity_b": polarity_b,
                    "product": polarity_a * polarity_b,
                },
            )

        # Pattern 3: Modal certainty conflict
        modal_conflict = self._check_modal_conflict(frame_a, frame_b)
        if modal_conflict:
            return SRLContradictionDetail(
                pattern=ContradictionPattern.MODAL_CERTAINTY_CONFLICT,
                sentence_i_idx=sent_idx_a,
                sentence_j_idx=sent_idx_b,
                frame_i=frame_a,
                frame_j=frame_b,
                confidence=0.25,
                description=f"Modal conflict: {modal_conflict}",
                evidence={"modals": (frame_a.argm_mod, frame_b.argm_mod)},
            )

        return None

    def _check_modal_conflict(self, frame_a: SRLFrame, frame_b: SRLFrame) -> str | None:
        """Detect conflicting modal expressions."""
        mod_a = (frame_a.argm_mod or "").lower()
        mod_b = (frame_b.argm_mod or "").lower()

        if not mod_a or not mod_b:
            return None

        low_certainty = {"might", "could", "may", "possibly"}
        high_certainty = {"must", "will", "shall", "certainly"}

        if (mod_a in low_certainty and mod_b in high_certainty) or (
            mod_b in low_certainty and mod_a in high_certainty
        ):
            return f"'{mod_a}' vs '{mod_b}' certainty mismatch"

        return None

    @staticmethod
    def _normalize_text(text: str | None) -> str:
        """Normalize text for comparison (lowercase, strip whitespace)."""
        if not text:
            return ""
        return " ".join(text.lower().split())
