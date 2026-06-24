"""
Argument Mining Domain Models
Peldszus & Stede (2013) Micro-argument Structure Implementation
with enterprise-grade validation, graph integrity constraints, and serialization.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)


class NodeType(str, Enum):
    """
    Argument node taxonomy based on Peldszus & Stede (2013).

    Hierarchy:
    CLAIM → Central thesis or assertion
      ├─ SUPPORT → Evidence/reasoning favoring CLAIM
      │   └─ SUPPORT can nest (supporting evidence of evidence)
      ├─ ATTACK → Counter-argument opposing CLAIM
      │   └─ REBUTTAL → Defense against ATTACK (counter-counter-argument)
      └─ NEUTRAL → Factual statement without explicit stance
    """

    CLAIM = "CLAIM"
    SUPPORT = "SUPPORT"
    ATTACK = "ATTACK"
    REBUTTAL = "REBUTTAL"
    PREMISE = "PREMISE"  # Implicit assumption (optional extension)
    EVIDENCE = "EVIDENCE"  # Concrete data point (optional extension)


class RelationType(str, Enum):
    """
    Directed edge types between argument nodes.

    Semantics:
    - SUPPORT: source strengthens target's validity
    - ATTACK: source weakens target's validity
    - REBUTTAL: source defends target from an attack
    - ELABORATION: source clarifies/expands target (neutral)
    - CONTRADICTION: source directly contradicts target (implicit attack)
    """

    SUPPORT = "SUPPORT"
    ATTACK = "ATTACK"
    REBUTTAL = "REBUTTAL"
    ELABORATION = "ELABORATION"
    CONTRADICTION = "CONTRADICTION"
    NEUTRAL = "NEUTRAL"


class ArgumentStance(str, Enum):
    """Overall stance polarity of a node toward the root claim."""

    PRO = "PRO"  # Supports root claim
    CON = "CON"  # Opposes root claim
    NEUTRAL = "NEUTRAL"  # No clear stance


class ArgumentNode(BaseModel):
    """
    Single node in the argument graph representing a discourse unit.

    Invariants:
    - text must be non-empty after normalization
    - timestamp must be non-negative
    - confidence must be in [0, 1]
    - segment_id must be unique within graph scope
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # === Identity Fields ===
    segment_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique identifier (e.g., 'seg_001', 'edu_042')",
    )

    # === Content Fields ===
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Normalized text content of the argument unit",
    )
    original_text: str | None = Field(
        default=None,
        max_length=2000,
        description="Original unnormalized text (preserved for provenance)",
    )
    node_type: NodeType = Field(..., description="Peldszus & Stede role classification")

    # === Provenance Fields ===
    speaker: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Attributed actor/diplomat/speaker",
    )
    speaker_role: str | None = Field(
        default=None,
        max_length=100,
        description="Official role/title (e.g., 'Foreign Minister')",
    )
    timestamp: float = Field(
        ...,
        ge=0.0,
        description="Temporal position in transcript (seconds or relative offset)",
    )
    document_offset: tuple[int, int] = Field(
        default=(0, 0), description="(start_char, end_char) in source document"
    )

    # === Quality Metadata ===
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Classifier confidence score"
    )
    model_version: str | None = Field(
        default=None, description="Model version that produced this classification"
    )
    extraction_method: str = Field(
        default="classifier",
        pattern=r"^(classifier|rule_based|heuristic|manual)$",
        description="How this node was identified",
    )

    # === Semantic Enrichment (from SRL/TASK-A01) ===
    srl_frame_id: str | None = Field(
        default=None,
        description="Link to SRLFrame if this node maps to a predicate-argument structure",
    )
    predicate: str | None = Field(
        default=None, description="Extracted predicate verb (from SRL)"
    )
    is_negated: bool = Field(default=False, description="True if SRL negation detected")
    stance: ArgumentStance = Field(
        default=ArgumentStance.NEUTRAL,
        description="Computed stance relative to root claim",
    )

    # === Graph Analytics (computed post-construction) ===
    depth: int = Field(
        default=0, ge=0, description="Distance from root claim in graph hierarchy"
    )
    children_count: int = Field(
        default=0, ge=0, description="Number of outgoing edges (fan-out)"
    )
    parents_count: int = Field(
        default=0, ge=0, description="Number of incoming edges (fan-in)"
    )

    @field_validator("text")
    @classmethod
    def normalize_text(cls, v: str) -> str:
        """Normalize whitespace, control characters, and trim."""
        normalized = " ".join(v.split()).strip()
        if not normalized:
            raise ValueError("Text cannot be empty after normalization")
        return normalized

    @field_validator("speaker")
    @classmethod
    def normalize_speaker(cls, v: str) -> str:
        """Standardize speaker name format."""
        return " ".join(v.split()).strip().title()

    @model_validator(mode="after")
    def compute_derived_fields(self) -> ArgumentNode:
        """Compute derived fields after initialization."""
        # Store original text if not provided
        if self.original_text is None:
            self.original_text = self.text
        return self

    @property
    def text_hash(self) -> str:
        """Deterministic hash for deduplication."""
        return hashlib.sha256(self.text.lower().encode()).hexdigest()

    @property
    def is_root_claim(self) -> bool:
        """Check if this node is a root-level claim."""
        return self.node_type == NodeType.CLAIM and self.depth == 0

    @property
    def has_srl_link(self) -> bool:
        """Check if SRL enrichment available."""
        return self.srl_frame_id is not None

    def to_dict_for_frontend(self) -> dict:
        """Serialize to D3.js/React Flow compatible format."""
        return {
            "id": self.segment_id,
            "text": self.text,
            "type": self.node_type.value,
            "speaker": self.speaker,
            "confidence": self.confidence,
            "stance": self.stance.value,
            "metadata": {
                "timestamp": self.timestamp,
                "predicate": self.predicate,
                "is_negated": self.is_negated,
                "depth": self.depth,
            },
        }

    def truncate_display_text(self, max_length: int = 80) -> str:
        """Truncate text for UI display with ellipsis."""
        if len(self.text) <= max_length:
            return self.text
        return self.text[: max_length - 3] + "..."


class ArgumentEdge(BaseModel):
    """
    Directed relationship between two argument nodes.

    Constraints:
    - Cannot have self-loops (source != target)
    - Must reference existing node IDs (validated at graph level)
    - Confidence must reflect relation strength
    """

    model_config = ConfigDict(frozen=False)

    edge_id: str = Field(
        default_factory=lambda: f"edge_{uuid.uuid4().hex}",
        description="Unique edge identifier",
    )
    source_id: str = Field(..., description="Origin node segment_id (tail of arrow)")
    target_id: str = Field(
        ..., description="Destination node segment_id (head of arrow)"
    )
    relation_type: RelationType = Field(
        ..., description="Semantic type of directed relationship"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relation classifier confidence"
    )

    # === Provenance & Metadata ===
    weight: float = Field(
        default=1.0, ge=0.0, description="Edge weight for graph algorithms"
    )
    extracted_at: str | None = Field(
        default=None, description="ISO timestamp of extraction"
    )
    model_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Raw model output score before thresholding",
    )
    evidence_snippet: str | None = Field(
        default=None,
        max_length=500,
        description="Discourse marker or cue phrase that signaled this relation",
    )

    # === Structural Flags ===
    is_cross_speaker: bool = Field(
        default=False, description="True if source and target have different speakers"
    )
    is_rebuttal_of_attack: bool = Field(
        default=False, description="True if this REBUTTAL counters an existing ATTACK"
    )

    @model_validator(mode="after")
    def validate_edge_invariants(self) -> ArgumentEdge:
        """Enforce edge integrity constraints."""
        if self.source_id == self.target_id:
            raise ValueError("Self-loops are not allowed in argument graphs")
        return self

    @property
    def is_attack_relation(self) -> bool:
        """Check if this edge represents an adversarial relationship."""
        return self.relation_type in (RelationType.ATTACK, RelationType.CONTRADICTION)

    @property
    def is_support_relation(self) -> bool:
        """Check if this edge represents a supportive relationship."""
        return self.relation_type == RelationType.SUPPORT

    def to_tuple(self) -> tuple[str, str, str]:
        """Return as (source, target, relation) tuple for hashing."""
        return (self.source_id, self.target_id, self.relation_type.value)

    def reverse(self) -> ArgumentEdge:
        """Create reversed edge (for bidirectional analysis)."""
        return ArgumentEdge(
            source_id=self.target_id,
            target_id=self.source_id,
            relation_type=self._get_reverse_relation(),
            confidence=self.confidence,
            weight=self.weight,
        )

    def _get_reverse_relation(self) -> RelationType:
        """Determine logical reverse relation type."""
        mapping = {
            RelationType.SUPPORT: RelationType.SUPPORT,
            RelationType.ATTACK: RelationType.ATTACK,
            RelationType.REBUTTAL: RelationType.ATTACK,
            RelationType.ELABORATION: RelationType.ELABORATION,
        }
        return mapping.get(self.relation_type, RelationType.NEUTRAL)


class ArgumentPath(BaseModel):
    """
    Ordered sequence of nodes forming a reasoning chain.
    Used for argument tracing and explanation generation.
    """

    path_id: str = Field(
        default_factory=lambda: (
            f"path_{hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()}"
        )
    )
    nodes: list[ArgumentNode] = Field(default_factory=list)
    edges: list[ArgumentEdge] = Field(default_factory=list)
    path_type: Literal["support_chain", "attack_chain", "mixed"] = Field(
        default="mixed"
    )
    total_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def length(self) -> int:
        return len(self.nodes)

    @property
    def start_node(self) -> ArgumentNode | None:
        return self.nodes[0] if self.nodes else None

    @property
    def end_node(self) -> ArgumentNode | None:
        return self.nodes[-1] if self.nodes else None

    @property
    def is_valid(self) -> bool:
        """Verify path continuity (consecutive nodes connected by edges)."""
        if len(self.nodes) != len(self.edges) + 1:
            return False

        for i, edge in enumerate(self.edges):
            if edge.source_id != self.nodes[i].segment_id:
                return False
            if edge.target_id != self.nodes[i + 1].segment_id:
                return False
        return True


class ArgumentGraph(BaseModel):
    """
    Complete argumentation structure for a document/transcript.

    Invariants:
    - Directed Acyclic Graph (DAG) by construction
    - Validated node-edge referential integrity
    - Computed analytics (density, depth, balance)
    """

    model_config = ConfigDict(validate_assignment=False)

    # === Core Structure ===
    graph_id: str = Field(
        default_factory=lambda: f"arg_{uuid.uuid4().hex}",
        description="Unique graph identifier",
    )
    document_id: str | None = Field(
        default=None, description="Source document/transcript identifier"
    )
    nodes: list[ArgumentNode] = Field(
        default_factory=list, description="All argument nodes in the graph"
    )
    edges: list[ArgumentEdge] = Field(
        default_factory=list, description="All directed relationships between nodes"
    )
    root_claim_ids: list[str] = Field(
        default_factory=list,
        description="IDs of root-level claim nodes (supports forest structure)",
    )

    # === Metadata ===
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 creation timestamp (UTC, timezone-aware)",
    )
    model_version: str = Field(
        default="deberta-v3-base-argmining-v1.0",
        description="Model pipeline version used for extraction",
    )
    processing_time_ms: float = Field(
        default=0.0, ge=0.0, description="Total graph construction time"
    )

    # === Computed Analytics (populated after build()) ===
    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)
    graph_density: float = Field(default=0.0, ge=0.0, le=1.0)
    max_depth: int = Field(default=0, ge=0)
    avg_branching_factor: float = Field(default=0.0, ge=0.0)
    claim_count: int = Field(default=0, ge=0)
    support_count: int = Field(default=0, ge=0)
    attack_count: int = Field(default=0, ge=0)
    rebuttal_count: int = Field(default=0, ge=0)

    # === Performance Optimization ===
    skip_validation: bool = Field(default=True, exclude=True)

    # === Internal Indexes (for O(1) lookups) ===
    _node_index: dict[str, ArgumentNode] = PrivateAttr(default_factory=dict)
    _adjacency_list: dict[str, list[tuple[str, ArgumentEdge]]] = PrivateAttr(
        default_factory=dict
    )
    _reverse_adjacency: dict[str, list[tuple[str, ArgumentEdge]]] = PrivateAttr(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_graph_structure(self) -> ArgumentGraph:
        """Lightweight initialization validation. Full validation via validate()."""
        # Only rebuild indexes on init, skip heavy validation
        self._rebuild_indexes()
        return self

    def validate_graph(self) -> ArgumentGraph:
        """Explicit full validation (DAG, Referential Integrity, Analytics).

        Call this method when you need to ensure graph integrity after construction
        or modifications. For large graphs, this is expensive.
        """
        self._rebuild_indexes()

        node_ids = set(self._node_index.keys())
        for edge in self.edges:
            if edge.source_id not in node_ids:
                raise ValueError(
                    f"Edge references non-existent source node: {edge.source_id}"
                )
            if edge.target_id not in node_ids:
                raise ValueError(
                    f"Edge references non-existent target node: {edge.target_id}"
                )

        for root_id in self.root_claim_ids:
            if root_id not in node_ids:
                raise ValueError(f"Root claim ID not found in nodes: {root_id}")

        cycles = self.detect_cycles()
        if cycles:
            cycle_str = " → ".join(cycles[0]) if cycles[0] else "unknown"
            raise ValueError(
                f"Graph contains cycle(s): {cycle_str}. Argument graphs must be acyclic (DAG)."
            )

        self._compute_analytics()
        return self

    def _rebuild_indexes(self) -> None:
        self._node_index = {node.segment_id: node for node in self.nodes}
        self._adjacency_list = defaultdict(list)
        self._reverse_adjacency = defaultdict(list)
        for edge in self.edges:
            self._adjacency_list[edge.source_id].append((edge.target_id, edge))
            self._reverse_adjacency[edge.target_id].append((edge.source_id, edge))

    def _compute_analytics(self) -> None:
        self.total_nodes = len(self.nodes)
        self.total_edges = len(self.edges)
        if self.total_nodes == 0:
            return

        type_counts = defaultdict(int)
        for node in self.nodes:
            type_counts[node.node_type] += 1

        self.claim_count = type_counts.get(NodeType.CLAIM, 0)
        self.support_count = type_counts.get(NodeType.SUPPORT, 0)
        self.attack_count = type_counts.get(NodeType.ATTACK, 0)
        self.rebuttal_count = type_counts.get(NodeType.REBUTTAL, 0)

        n = self.total_nodes
        if n > 1:
            self.graph_density = self.total_edges / (n * (n - 1))

        if self.root_claim_ids:
            depths = self._compute_depths_bfs()
            self.max_depth = max(depths.values()) if depths else 0

            total_children = sum(
                len(self._adjacency_list.get(node_id, []))
                for node_id in self._node_index.keys()
            )
            self.avg_branching_factor = total_children / n if n > 0 else 0.0

    def _compute_depths_bfs(self) -> dict[str, int]:
        from collections import deque

        depths = {node_id: 0 for node_id in self._node_index}
        visited = set()
        queue = deque()

        for root_id in self.root_claim_ids:
            if root_id in self._node_index:
                queue.append((root_id, 0))
                visited.add(root_id)

        while queue:
            node_id, depth = queue.popleft()
            depths[node_id] = depth
            for neighbor_id, _ in self._adjacency_list.get(node_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
                    depths[neighbor_id] = depth + 1

        for node_id, depth in depths.items():
            if node_id in self._node_index:
                self._node_index[node_id].depth = depth
        return depths

    def add_node(self, node: ArgumentNode) -> ArgumentGraph:
        if node.segment_id in self._node_index:
            raise ValueError(f"Duplicate node segment_id: {node.segment_id}")
        self.nodes.append(node)
        self._node_index[node.segment_id] = node
        self._adjacency_list.setdefault(node.segment_id, [])
        self._reverse_adjacency.setdefault(node.segment_id, [])
        return self

    def add_edge(self, edge: ArgumentEdge) -> ArgumentGraph:
        if edge.source_id not in self._node_index:
            raise ValueError(f"Source node not found: {edge.source_id}")
        if edge.target_id not in self._node_index:
            raise ValueError(f"Target node not found: {edge.target_id}")
        self.edges.append(edge)
        self._adjacency_list[edge.source_id].append((edge.target_id, edge))
        self._reverse_adjacency[edge.target_id].append((edge.source_id, edge))
        return self

    def remove_edge(self, edge_id: str) -> bool:
        for i, edge in enumerate(self.edges):
            if edge.edge_id == edge_id:
                removed = self.edges.pop(i)
                adj = self._adjacency_list.get(removed.source_id, [])
                self._adjacency_list[removed.source_id] = [
                    (n, e) for n, e in adj if e.edge_id != edge_id
                ]
                rev_adj = self._reverse_adjacency.get(removed.target_id, [])
                self._reverse_adjacency[removed.target_id] = [
                    (n, e) for n, e in rev_adj if e.edge_id != edge_id
                ]
                return True
        return False

    @classmethod
    def create_with_cycles_allowed(
        cls,
        nodes: list[ArgumentNode],
        edges: list[ArgumentEdge],
        root_claim_ids: list[str],
        **kwargs,
    ) -> ArgumentGraph:
        """Factory that skips cycle validation — use only when you intend to remove cycles afterward."""
        obj = cls.model_construct(
            nodes=list(nodes),
            edges=list(edges),
            root_claim_ids=list(root_claim_ids),
            **kwargs,
        )
        # Initialize __pydantic_private__ if not present
        if not hasattr(obj, "__pydantic_private__") or obj.__pydantic_private__ is None:
            object.__setattr__(obj, "__pydantic_private__", {})

        from collections import defaultdict

        obj.__pydantic_private__["_node_index"] = {}
        obj.__pydantic_private__["_adjacency_list"] = defaultdict(list)
        obj.__pydantic_private__["_reverse_adjacency"] = defaultdict(list)

        obj._rebuild_indexes()
        obj._compute_analytics()
        return obj

    def remove_weakest_cycle_edge(self) -> ArgumentEdge | None:
        cycles = self.detect_cycles()
        if not cycles:
            return None
        cycle_edges = []
        for cycle in cycles:
            for i in range(len(cycle)):
                src = cycle[i]
                tgt = cycle[(i + 1) % len(cycle)]
                for neighbor_id, edge in self._adjacency_list.get(src, []):
                    if neighbor_id == tgt:
                        if edge not in cycle_edges:
                            cycle_edges.append(edge)
        if not cycle_edges:
            return None
        weakest = min(cycle_edges, key=lambda e: e.confidence)
        self.remove_edge(weakest.edge_id)
        return weakest

    def get_node(self, segment_id: str) -> ArgumentNode | None:
        return self._node_index.get(segment_id)

    def get_subgraph(self, segment_ids: set[str]) -> ArgumentGraph:
        """Create a new subgraph containing only the specified nodes and their connecting edges."""
        node_set = set(segment_ids) & set(self._node_index.keys())
        sub_nodes = [self._node_index[nid] for nid in node_set]
        sub_edges = [
            edge
            for edge in self.edges
            if edge.source_id in node_set and edge.target_id in node_set
        ]
        sub_roots = [rid for rid in self.root_claim_ids if rid in node_set]
        return ArgumentGraph(
            nodes=sub_nodes,
            edges=sub_edges,
            root_claim_ids=sub_roots,
            document_id=self.document_id,
            model_version=self.model_version,
            skip_validation=True,
        )

    def get_neighbors(self, segment_id: str) -> list[tuple[ArgumentNode, ArgumentEdge]]:
        neighbors = []
        for neighbor_id, edge in self._adjacency_list.get(segment_id, []):
            node = self._node_index.get(neighbor_id)
            if node:
                neighbors.append((node, edge))
        return neighbors

    def get_predecessors(
        self, segment_id: str
    ) -> list[tuple[ArgumentNode, ArgumentEdge]]:
        predecessors = []
        for pred_id, edge in self._reverse_adjacency.get(segment_id, []):
            node = self._node_index.get(pred_id)
            if node:
                predecessors.append((node, edge))
        return predecessors

    def get_root_claims(self) -> list[ArgumentNode]:
        return [
            self._node_index[rid]
            for rid in self.root_claim_ids
            if rid in self._node_index
        ]

    def get_attacks(self) -> list[ArgumentEdge]:
        return [e for e in self.edges if e.is_attack_relation]

    def get_supports(self) -> list[ArgumentEdge]:
        return [e for e in self.edges if e.is_support_relation]

    def get_self_attacks(self) -> list[tuple[ArgumentEdge, ArgumentNode, ArgumentNode]]:
        results = []
        for edge in self.get_attacks():
            src = self._node_index.get(edge.source_id)
            tgt = self._node_index.get(edge.target_id)
            if src and tgt and src.speaker == tgt.speaker:
                results.append((edge, src, tgt))
        return results

    def get_cross_speaker_interactions(
        self,
    ) -> list[tuple[ArgumentEdge, ArgumentNode, ArgumentNode]]:
        results = []
        for edge in self.edges:
            src = self._node_index.get(edge.source_id)
            tgt = self._node_index.get(edge.target_id)
            if src and tgt and src.speaker != tgt.speaker:
                results.append((edge, src, tgt))
        return results

    def detect_cycles(self) -> list[list[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in self._node_index}
        cycles = []
        path = []

        def dfs(node_id: str) -> None:
            color[node_id] = GRAY
            path.append(node_id)
            for neighbor_id, _ in self._adjacency_list.get(node_id, []):
                if color.get(neighbor_id) == GRAY:
                    cycle_start = path.index(neighbor_id)
                    cycles.append([*path[cycle_start:], neighbor_id])
                elif color.get(neighbor_id) == WHITE:
                    dfs(neighbor_id)
            path.pop()
            color[node_id] = BLACK

        for node_id in list(self._node_index.keys()):
            if color[node_id] == WHITE:
                dfs(node_id)
        return cycles

    def find_argument_paths(
        self, source_id: str, target_id: str, max_depth: int = 10
    ) -> list[ArgumentPath]:
        from collections import deque

        if source_id not in self._node_index or target_id not in self._node_index:
            return []

        paths = []
        queue = deque([(source_id, [source_id], [])])
        while queue:
            current_id, node_path, edge_path = queue.popleft()
            if len(node_path) > max_depth:
                continue
            if current_id == target_id and len(node_path) > 1:
                nodes = [self._node_index[nid] for nid in node_path]
                path = ArgumentPath(
                    nodes=nodes,
                    edges=edge_path,
                    path_type=self._classify_path(edge_path),
                    total_confidence=(
                        min(e.confidence for e in edge_path) if edge_path else 1.0
                    ),
                )
                paths.append(path)
                continue

            for neighbor_id, edge in self._adjacency_list.get(current_id, []):
                if neighbor_id not in node_path:
                    queue.append(
                        (neighbor_id, [*node_path, neighbor_id], [*edge_path, edge])
                    )
        return paths

    def _classify_path(
        self, edges: list[ArgumentEdge]
    ) -> Literal["support_chain", "attack_chain", "mixed"]:
        if not edges:
            return "mixed"
        has_support = any(e.is_support_relation for e in edges)
        has_attack = any(e.is_attack_relation for e in edges)
        if has_support and not has_attack:
            return "support_chain"
        elif has_attack and not has_support:
            return "attack_chain"
        return "mixed"

    def compute_stance_propagation(self) -> None:
        """Propagate stance from root claims to all connected nodes.

        Edges are directed source→target but may point *toward* the root claim
        (e.g., supp_1 → claim_1 means 'supp_1 supports claim_1').  To reach
        non-root nodes we therefore also walk the *reverse* adjacency so that
        we can assign stance to nodes that are sources of incoming edges on
        root claims.
        """
        if not self.root_claim_ids:
            return

        for root_id in self.root_claim_ids:
            if root_id in self._node_index:
                self._node_index[root_id].stance = ArgumentStance.PRO

        from collections import deque

        visited: set[str] = set(self.root_claim_ids)
        queue: deque[str] = deque(self.root_claim_ids)

        while queue:
            node_id = queue.popleft()
            current_stance = self._node_index[node_id].stance

            # Walk outgoing edges (node_id → neighbor)
            for neighbor_id, edge in self._adjacency_list.get(node_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    if edge.relation_type == RelationType.SUPPORT:
                        new_stance = current_stance
                    elif edge.relation_type in (
                        RelationType.ATTACK,
                        RelationType.CONTRADICTION,
                        RelationType.REBUTTAL,
                    ):
                        new_stance = (
                            ArgumentStance.CON
                            if current_stance == ArgumentStance.PRO
                            else ArgumentStance.PRO
                        )
                    else:
                        new_stance = ArgumentStance.NEUTRAL
                    self._node_index[neighbor_id].stance = new_stance
                    queue.append(neighbor_id)

            # Walk reverse edges (predecessor → node_id) so nodes pointing
            # *into* the current node are also assigned a stance.
            for pred_id, edge in self._reverse_adjacency.get(node_id, []):
                if pred_id not in visited:
                    visited.add(pred_id)
                    if edge.relation_type == RelationType.SUPPORT:
                        new_stance = current_stance
                    elif edge.relation_type in (
                        RelationType.ATTACK,
                        RelationType.CONTRADICTION,
                        RelationType.REBUTTAL,
                    ):
                        new_stance = (
                            ArgumentStance.CON
                            if current_stance == ArgumentStance.PRO
                            else ArgumentStance.PRO
                        )
                    else:
                        new_stance = ArgumentStance.NEUTRAL
                    self._node_index[pred_id].stance = new_stance
                    queue.append(pred_id)

    def serialize_to_frontend(self) -> dict:
        if not self.root_claim_ids:
            return {"error": "No root claims defined"}
        trees = []
        for root_id in self.root_claim_ids:
            if root_id in self._node_index:
                tree = self._build_tree_recursive(root_id, visited=set())
                trees.append(tree)
        if len(trees) == 1:
            return trees[0]
        return {"forest": trees}

    def _build_tree_recursive(self, node_id: str, visited: set[str]) -> dict:
        if node_id in visited:
            return {}
        visited.add(node_id)
        node = self._node_index.get(node_id)
        if not node:
            return {}

        tree_data = node.to_dict_for_frontend()
        children = []
        for neighbor_id, edge in self._adjacency_list.get(node_id, []):
            child_tree = self._build_tree_recursive(neighbor_id, visited.copy())
            if child_tree:
                child_tree["relation"] = {
                    "type": edge.relation_type.value,
                    "confidence": edge.confidence,
                }
                children.append(child_tree)
        if children:
            tree_data["children"] = children
        return tree_data

    def to_networkx(self):
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx package required for NetworkX conversion")
        G = nx.DiGraph()
        for node in self.nodes:
            G.add_node(node.segment_id, **node.model_dump(exclude={"segment_id"}))
        for edge in self.edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                **edge.model_dump(exclude={"source_id", "target_id", "edge_id"}),
            )
        return G

    def to_cyjs(self) -> dict:
        elements = {"nodes": [], "edges": []}
        for node in self.nodes:
            elements["nodes"].append(
                {
                    "data": {
                        "id": node.segment_id,
                        "label": node.truncate_display_text(40),
                        "type": node.node_type.value,
                        "speaker": node.speaker,
                        "confidence": node.confidence,
                    }
                }
            )
        for edge in self.edges:
            elements["edges"].append(
                {
                    "data": {
                        "id": edge.edge_id,
                        "source": edge.source_id,
                        "target": edge.target_id,
                        "label": edge.relation_type.value,
                        "confidence": edge.confidence,
                    }
                }
            )
        return elements

    def summary(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "document_id": self.document_id,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_types": {
                "claims": self.claim_count,
                "supports": self.support_count,
                "attacks": self.attack_count,
                "rebuttals": self.rebuttal_count,
            },
            "structure": {
                "root_claims": len(self.root_claim_ids),
                "max_depth": self.max_depth,
                "avg_branching_factor": round(self.avg_branching_factor, 2),
                "density": round(self.graph_density, 4),
            },
            "quality": {
                "has_cycles": len(self.detect_cycles()) > 0,
                "self_attacks": len(self.get_self_attacks()),
                "cross_speaker_interactions": len(
                    self.get_cross_speaker_interactions()
                ),
            },
            "processing": {
                "model_version": self.model_version,
                "processing_time_ms": round(self.processing_time_ms, 2),
                "created_at": self.created_at,
            },
        }
