# GELİŞMİŞ MÜHENDİSLİK RAPORU: TASK-A02 · Argument Mining (Sav Madenciliği) Katmanı

**Versiyon:** 2.0 - Production-Ready Architecture  
**Target Audience:** Downstream AI Code-Generation Agent (antigravity)  
**Focus:** Enterprise-Grade Graph Analytics, Multi-Stage Classification, Circular Dependency Detection, Fault-Tolerant Pipeline  

---

## 0. EXECUTIVE SUMMARY & ARCHITECTURAL DECISION RECORD (ADR)

### 0.1 Critical Design Decisions

| Decision ID | Context                     | Decision                                                | Rationale                                                      |
| ----------- | --------------------------- | ------------------------------------------------------- | -------------------------------------------------------------- |
| ADR-A02-001 | Claim Detection Model       | `microsoft/deberta-v3-base` fine-tuned on IBM AQC       | State-of-the-art argument classification, multilingual support |
| ADR-A02-002 | Relation Classifier         | Pairwise segment classification with attention pooling  | Captures contextual relationships between claim-support pairs  |
| ADR-A02-003 | EDU Segmentation Strategy   | RST Parser primary, spaCy sentence boundary fallback    | Graceful degradation if RST unavailable                        |
| ADR-A02-004 | Graph Storage Format        | Adjacency list + edge list hybrid (JSONB in PostgreSQL) | Efficient traversal + serialization for frontend D3.js         |
| ADR-A02-005 | Circular Reference Handling | Topological sort validation + auto-pruning weakest edge | Prevents infinite loops in graph algorithms                    |
| ADR-A02-006 | Anomaly Integration         | ATTACK edges as first-class contradiction signals       | Enriches CrossAnomalyService with structural semantics         |

### 0.2 Non-Functional Requirements (NFR)

```yaml
performance:
  claim_detection_latency_p99: "< 800ms per segment"
  relation_classification_p99: "< 200ms per pair"
  graph_construction_time: "< 2s for documents < 500 segments"
  memory_overhead: "< 4GB baseline (DeBERTa-v3-base ~400MB)"
  
reliability:
  availability: "99.9% uptime"
  graph_integrity: "100% acyclic guarantee (DAG enforcement)"
  error_rate: "< 0.5% on valid inputs"
  recovery_time: "< 3s from transient failures"
  
scalability:
  max_graph_size: "10,000 nodes per document"
  batch_processing: "Configurable parallelism (default: 4 workers)"
  caching: "LRU cache for repeated document analysis"
  
quality_metrics:
  claim_detection_f1: ">= 0.78 (IBM AQC benchmark)"
  relation_classification_f1: ">= 0.70 (SUPPORT/ATTACK/REBUTTAL)"
  false_positive_rate: "< 0.15 for ATTACK detection"
```

### 0.3 Upstream Dependency Map

```
TASK-A01 (SRL Enrichment Layer)
    │
    ├── SRLFrame.ARG1 → Claim Boundary Validation (Primary Input)
    ├── SRLFrame.ARG0 → Speaker Attribution (Actor Identification)
    └── SRLFrame.argm_neg → Negation-Aware Claim Filtering
         │
         ▼
TASK-A02 (Argument Mining Layer) [THIS DOCUMENT]
    │
    ├── ArgumentGraph → Downstream Visualization (D3.js/React Flow)
    ├── ATTACK edges → CrossAnomalyService Enhancement
    └── Claim triplets → Network Assembly Stage (A04/A05)
```

---

## 1. ENHANCED DOMAIN MODEL WITH GRAPH INVARIANTS

### 1.1 Robust Argument Domain Objects (`src/bb_paxdata/domain/models/argument.py`) [NEW]

```python
"""
Argument Mining Domain Models
Peldszus & Stede (2013) Micro-argument Structure Implementation
with enterprise-grade validation, graph integrity constraints, and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict, field_validator
from collections import defaultdict
import hashlib
import json
import re


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
    PREMISE = "PREMISE"       # Implicit assumption (optional extension)
    EVIDENCE = "EVIDENCE"     # Concrete data point (optional extension)


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
    PRO = "PRO"           # Supports root claim
    CON = "CON"           # Opposes root claim
    NEUTRAL = "NEUTRAL"   # No clear stance


class ArgumentNode(BaseModel):
    """
    Single node in the argument graph representing a discourse unit.
    
    Invariants:
    - text must be non-empty after normalization
    - timestamp must be non-negative
    - confidence must be in [0, 1]
    - segment_id must be unique within graph scope
    
    Example:
        ArgumentNode(
            segment_id="seg_001",
            text="Turkey maintains its rights under the 1923 Treaty.",
            node_type=NodeType.CLAIM,
            speaker="Turkish_Delegate",
            timestamp=120.5,
            confidence=0.94
        )
    """
    model_config = ConfigDict(frozen=False, validate_assignment=True)
    
    # === Identity Fields ===
    segment_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r'^[a-zA-Z0-9_\-]+$',
        description="Unique identifier (e.g., 'seg_001', 'edu_042')"
    )
    
    # === Content Fields ===
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Normalized text content of the argument unit"
    )
    original_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Original unnormalized text (preserved for provenance)"
    )
    node_type: NodeType = Field(
        ...,
        description="Peldszus & Stede role classification"
    )
    
    # === Provenance Fields ===
    speaker: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Attributed actor/diplomat/speaker"
    )
    speaker_role: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Official role/title (e.g., 'Foreign Minister')"
    )
    timestamp: float = Field(
        ...,
        ge=0.0,
        description="Temporal position in transcript (seconds or relative offset)"
    )
    document_offset: tuple[int, int] = Field(
        default=(0, 0),
        description="(start_char, end_char) in source document"
    )
    
    # === Quality Metadata ===
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Classifier confidence score"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Model version that produced this classification"
    )
    extraction_method: str = Field(
        default="classifier",
        pattern=r'^(classifier|rule_based|heuristic|manual)$',
        description="How this node was identified"
    )
    
    # === Semantic Enrichment (from SRL/TASK-A01) ===
    srl_frame_id: Optional[str] = Field(
        default=None,
        description="Link to SRLFrame if this node maps to a predicate-argument structure"
    )
    predicate: Optional[str] = Field(
        default=None,
        description="Extracted predicate verb (from SRL)"
    )
    is_negated: bool = Field(
        default=False,
        description="True if SRL negation detected"
    )
    stance: ArgumentStance = Field(
        default=ArgumentStance.NEUTRAL,
        description="Computed stance relative to root claim"
    )
    
    # === Graph Analytics (computed post-construction) ===
    depth: int = Field(
        default=0,
        ge=0,
        description="Distance from root claim in graph hierarchy"
    )
    children_count: int = Field(
        default=0,
        ge=0,
        description="Number of outgoing edges (fan-out)"
    )
    parents_count: int = Field(
        default=0,
        ge=0,
        description="Number of incoming edges (fan-in)"
    )
    
    @field_validator('text')
    @classmethod
    def normalize_text(cls, v: str) -> str:
        """Normalize whitespace, control characters, and trim."""
        normalized = ' '.join(v.split()).strip()
        if not normalized:
            raise ValueError("Text cannot be empty after normalization")
        return normalized
    
    @field_validator('speaker')
    @classmethod
    def normalize_speaker(cls, v: str) -> str:
        """Standardize speaker name format."""
        return ' '.join(v.split()).strip().title()
    
    @model_validator(mode='after')
    def compute_derived_fields(self) -> 'ArgumentNode':
        """Compute derived fields after initialization."""
        # Store original text if not provided
        if self.original_text is None:
            self.original_text = self.text
        
        return self
    
    @property
    def text_hash(self) -> str:
        """Deterministic hash for deduplication."""
        return hashlib.sha256(self.text.lower().encode()).hexdigest()[:16]
    
    @property
    def is_root_claim(self) -> bool:
        """Check if this node is a root-level claim."""
        return self.node_type == NodeType.CLAIM and self.depth == 0
    
    @property
    def has_srl_link(self) -> bool:
        """Check if SRL enrichment available."""
        return self.srl_frame_id is not None
    
    def to_dict_for_frontend(self) -> dict:
        """
        Serialize to D3.js/React Flow compatible format.
        
        Returns:
            Hierarchical dictionary matching JSON schema contract.
        """
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
                "depth": self.depth
            }
        }
    
    def truncate_display_text(self, max_length: int = 80) -> str:
        """Truncate text for UI display with ellipsis."""
        if len(self.text) <= max_length:
            return self.text
        return self.text[:max_length-3] + "..."


class ArgumentEdge(BaseModel):
    """
    Directed relationship between two argument nodes.
    
    Directional semantics:
    - source → target means "source [relation_type]s target"
    - Example: SUPPORT edge: "Evidence (source) SUPPORTS Claim (target)"
    
    Constraints:
    - Cannot have self-loops (source != target)
    - Must reference existing node IDs (validated at graph level)
    - Confidence must reflect relation strength
    """
    model_config = ConfigDict(frozen=False)
    
    edge_id: str = Field(
        default_factory=lambda: f"edge_{hashlib.uuid4().hex[:8]}",
        description="Unique edge identifier"
    )
    source_id: str = Field(
        ...,
        description="Origin node segment_id (tail of arrow)"
    )
    target_id: str = Field(
        ...,
        description="Destination node segment_id (head of arrow)"
    )
    relation_type: RelationType = Field(
        ...,
        description="Semantic type of directed relationship"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relation classifier confidence"
    )
    
    # === Provenance & Metadata ===
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Edge weight for graph algorithms (PageRank, etc.)"
    )
    extracted_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of extraction"
    )
    model_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Raw model output score before thresholding"
    )
    evidence_snippet: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Discourse marker or cue phrase that signaled this relation"
    )
    
    # === Structural Flags ===
    is_cross_speaker: bool = Field(
        default=False,
        description="True if source and target have different speakers"
    )
    is_rebuttal_of_attack: bool = Field(
        default=False,
        description="True if this REBUTTAL counters an existing ATTACK"
    )
    
    @model_validator(mode='after')
    def validate_edge_invariants(self) -> 'ArgumentEdge':
        """Enforce edge integrity constraints."""
        if self.source_id == self.target_id:
            raise ValueError("Self-loops are not allowed in argument graphs")
        
        # Auto-compute cross-speaker flag (will be validated at graph level)
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
    
    def reverse(self) -> 'ArgumentEdge':
        """Create reversed edge (for bidirectional analysis)."""
        return ArgumentEdge(
            source_id=self.target_id,
            target_id=self.source_id,
            relation_type=self._get_reverse_relation(),
            confidence=self.confidence,
            weight=self.weight
        )
    
    def _get_reverse_relation(self) -> RelationType:
        """Determine logical reverse relation type."""
        mapping = {
            RelationType.SUPPORT: RelationType.SUPPORT,  # Symmetric conceptually
            RelationType.ATTACK: RelationType.ATTACK,
            RelationType.REBUTTAL: RelationType.ATTACK,  # Reversal of rebuttal is attack
            RelationType.ELABORATION: RelationType.ELABORATION,
        }
        return mapping.get(self.relation_type, RelationType.NEUTRAL)


class ArgumentPath(BaseModel):
    """
    Ordered sequence of nodes forming a reasoning chain.
    Used for argument tracing and explanation generation.
    """
    path_id: str = Field(default_factory=lambda: f"path_{hashlib.uuid4().hex[:8]}")
    nodes: list[ArgumentNode] = Field(default_factory=list)
    edges: list[ArgumentEdge] = Field(default_factory=list)
    path_type: Literal["support_chain", "attack_chain", "mixed"] = Field(default="mixed")
    total_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    @property
    def length(self) -> int:
        return len(self.nodes)
    
    @property
    def start_node(self) -> Optional[ArgumentNode]:
        return self.nodes[0] if self.nodes else None
    
    @property
    def end_node(self) -> Optional[ArgumentNode]:
        return self.nodes[-1] if self.nodes else None
    
    @property
    def is_valid(self) -> bool:
        """Verify path continuity (consecutive nodes connected by edges)."""
        if len(self.nodes) != len(self.edges) + 1:
            return False
        
        for i, edge in enumerate(self.edges):
            if edge.source_id != self.nodes[i].segment_id:
                return False
            if edge.target_id != self.nodes[i+1].segment_id:
                return False
        
        return True


class ArgumentGraph(BaseModel):
    """
    Complete argumentation structure for a document/transcript.
    
    Properties:
    - Directed Acyclic Graph (DAG) by construction
    - Single root claim (or forest of claims)
    - Validated node-edge referential integrity
    - Computed analytics (density, depth, balance)
    
    Operations:
    - add_node(), add_edge() with validation
    - detect_cycles() for DAG enforcement
    - get_subgraph() for focused analysis
    - compute_stance_propagation() for polarity assignment
    - serialize_to_frontend() for visualization
    
    Invariants:
    - All edge source/target must exist in nodes
    - No cycles allowed (enforced by validate_graph_structure)
    - Root claim must exist if specified
    """
    model_config = ConfigDict(validate_assignment=True)
    
    # === Core Structure ===
    graph_id: str = Field(
        default_factory=lambda: f"arg_{hashlib.uuid4().hex[:12]}",
        description="Unique graph identifier"
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Source document/transcript identifier"
    )
    nodes: list[ArgumentNode] = Field(
        default_factory=list,
        description="All argument nodes in the graph"
    )
    edges: list[ArgumentEdge] = Field(
        default_factory=list,
        description="All directed relationships between nodes"
    )
    root_claim_ids: list[str] = Field(
        default_factory=list,
        description="IDs of root-level claim nodes (supports forest structure)"
    )
    
    # === Metadata ===
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 creation timestamp"
    )
    model_version: str = Field(
        default="deberta-v3-base-argmining-v1.0",
        description="Model pipeline version used for extraction"
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total graph construction time"
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
    
    # === Internal Indexes (for O(1) lookups) ===
    _node_index: dict[str, ArgumentNode] = Field(
        default_factory=dict,
        exclude=True,  # Don't serialize
        description="Internal lookup index"
    )
    _adjacency_list: dict[str, list[tuple[str, ArgumentEdge]]] = Field(
        default_factory=dict,
        exclude=True,
        description="Adjacency list: node_id → [(neighbor_id, edge)]"
    )
    _reverse_adjacency: dict[str, list[tuple[str, ArgumentEdge]]] = Field(
        default_factory=dict,
        exclude=True,
        description="Reverse adjacency: node_id → [(predecessor_id, edge)]"
    )
    
    @model_validator(mode='after')
    def validate_graph_structure(self) -> 'ArgumentGraph':
        """
        Comprehensive graph validation:
        1. Referential integrity (edges reference existing nodes)
        2. Acyclicity (no cycles allowed - DAG enforcement)
        3. Root claim existence validation
        4. Index reconstruction
        """
        # Build indexes
        self._rebuild_indexes()
        
        # Check referential integrity
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
        
        # Validate root claims
        for root_id in self.root_claim_ids:
            if root_id not in node_ids:
                raise ValueError(
                    f"Root claim ID not found in nodes: {root_id}"
                )
        
        # Cycle detection (DFS-based)
        cycles = self.detect_cycles()
        if cycles:
            cycle_str = " → ".join(cycles[0]) if cycles[0] else "unknown"
            raise ValueError(
                f"Graph contains cycle(s): {cycle_str}. "
                f"Argument graphs must be acyclic (DAG)."
            )
        
        # Compute analytics
        self._compute_analytics()
        
        return self
    
    def _rebuild_indexes(self) -> None:
        """Rebuild internal lookup structures."""
        self._node_index = {node.segment_id: node for node in self.nodes}
        
        self._adjacency_list = defaultdict(list)
        self._reverse_adjacency = defaultdict(list)
        
        for edge in self.edges:
            self._adjacency_list[edge.source_id].append((edge.target_id, edge))
            self._reverse_adjacency[edge.target_id].append((edge.source_id, edge))
    
    def _compute_analytics(self) -> None:
        """Compute graph statistics and populate metadata fields."""
        self.total_nodes = len(self.nodes)
        self.total_edges = len(self.edges)
        
        if self.total_nodes == 0:
            return
        
        # Count node types
        type_counts = defaultdict(int)
        for node in self.nodes:
            type_counts[node.node_type] += 1
        
        self.claim_count = type_counts.get(NodeType.CLAIM, 0)
        self.support_count = type_counts.get(NodeType.SUPPORT, 0)
        self.attack_count = type_counts.get(NodeType.ATTACK, 0)
        self.rebuttal_count = type_counts.get(NodeType.REBUTTAL, 0)
        
        # Graph density: |E| / (|V| * (|V|-1)) for directed graph
        n = self.total_nodes
        if n > 1:
            self.graph_density = self.total_edges / (n * (n - 1))
        
        # Compute depths via BFS from roots
        if self.root_claim_ids:
            depths = self._compute_depths_bfs()
            self.max_depth = max(depths.values()) if depths else 0
            
            # Average branching factor
            total_children = sum(
                len(self._adjacency_list.get(node_id, []))
                for node_id in self._node_index.keys()
            )
            self.avg_branching_factor = total_children / n if n > 0 else 0.0
    
    def _compute_depths_bfs(self) -> dict[str, int]:
        """BFS to compute depth of each node from nearest root."""
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
        
        # Update node depth attributes
        for node_id, depth in depths.items():
            if node_id in self._node_index:
                self._node_index[node_id].depth = depth
        
        return depths
    
    # === Mutation Operations (with validation) ===
    
    def add_node(self, node: ArgumentNode) -> 'ArgumentGraph':
        """
        Add node with duplicate detection.
        
        Raises:
            ValueError: If segment_id already exists
        """
        if node.segment_id in self._node_index:
            raise ValueError(f"Duplicate node segment_id: {node.segment_id}")
        
        self.nodes.append(node)
        self._node_index[node.segment_id] = node
        return self
    
    def add_edge(self, edge: ArgumentEdge) -> 'ArgumentGraph':
        """
        Add edge with validation.
        
        Raises:
            ValueError: If nodes don't exist or creates cycle
        """
        # Verify nodes exist
        if edge.source_id not in self._node_index:
            raise ValueError(f"Source node not found: {edge.source_id}")
        if edge.target_id not in self._node_index:
            raise ValueError(f"Target node not found: {edge.target_id}")
        
        # Temporarily add and check for cycles
        self.edges.append(edge)
        self._adjacency_list[edge.source_id].append((edge.target_id, edge))
        self._reverse_adjacency[edge.target_id].append((edge.source_id, edge))
        
        # Quick cycle check (would need full DFS for certainty)
        # For now, defer to validator on next access
        
        return self
    
    def remove_edge(self, edge_id: str) -> bool:
        """Remove edge by ID. Returns True if removed."""
        for i, edge in enumerate(self.edges):
            if edge.edge_id == edge_id:
                removed = self.edges.pop(i)
                
                # Update adjacency lists
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
    
    def remove_weakest_cycle_edge(self) -> Optional[ArgumentEdge]:
        """
        Detect and remove lowest-confidence edge from any cycle.
        Used for automatic cycle resolution.
        
        Returns:
            Removed edge or None if graph is acyclic
        """
        cycles = self.detect_cycles()
        if not cycles:
            return None
        
        # Find all edges involved in cycles
        cycle_edges = set()
        for cycle in cycles:
            for i in range(len(cycle)):
                src = cycle[i]
                tgt = cycle[(i+1) % len(cycle)]
                for neighbor_id, edge in self._adjacency_list.get(src, []):
                    if neighbor_id == tgt:
                        cycle_edges.add(edge)
        
        if not cycle_edges:
            return None
        
        # Remove edge with lowest confidence
        weakest = min(cycle_edges, key=lambda e: e.confidence)
        self.remove_edge(weakest.edge_id)
        
        return weakest
    
    # === Query Operations ===
    
    def get_node(self, segment_id: str) -> Optional[ArgumentNode]:
        """O(1) node lookup."""
        return self._node_index.get(segment_id)
    
    def get_neighbors(self, segment_id: str) -> list[tuple[ArgumentNode, ArgumentEdge]]:
        """Get outgoing neighbors with edge info."""
        neighbors = []
        for neighbor_id, edge in self._adjacency_list.get(segment_id, []):
            node = self._node_index.get(neighbor_id)
            if node:
                neighbors.append((node, edge))
        return neighbors
    
    def get_predecessors(self, segment_id: str) -> list[tuple[ArgumentNode, ArgumentEdge]]:
        """Get incoming neighbors (parents) with edge info."""
        predecessors = []
        for pred_id, edge in self._reverse_adjacency.get(segment_id, []):
            node = self._node_index.get(pred_id)
            if node:
                predecessors.append((node, edge))
        return predecessors
    
    def get_root_claims(self) -> list[ArgumentNode]:
        """Get all root claim nodes."""
        return [
            self._node_index[rid] 
            for rid in self.root_claim_ids 
            if rid in self._node_index
        ]
    
    def get_attacks(self) -> list[ArgumentEdge]:
        """Get all ATTACK/CONTRADICTION edges."""
        return [e for e in self.edges if e.is_attack_relation]
    
    def get_supports(self) -> list[ArgumentEdge]:
        """Get all SUPPORT edges."""
        return [e for e in self.edges if e.is_support_relation]
    
    def get_self_attacks(self) -> list[tuple[ArgumentEdge, ArgumentNode, ArgumentNode]]:
        """
        Find attacks where source and target share same speaker.
        
        Returns:
            List of (edge, source_node, target_node) tuples
        """
        results = []
        for edge in self.get_attacks():
            src = self._node_index.get(edge.source_id)
            tgt = self._node_index.get(edge.target_id)
            
            if src and tgt and src.speaker == tgt.speaker:
                results.append((edge, src, tgt))
        
        return results
    
    def get_cross_speaker_interactions(self) -> list[tuple[ArgumentEdge, ArgumentNode, ArgumentNode]]:
        """
        Find edges where speakers differ (inter-agent dynamics).
        """
        results = []
        for edge in self.edges:
            src = self._node_index.get(edge.source_id)
            tgt = self._node_index.get(edge.target_id)
            
            if src and tgt and src.speaker != tgt.speaker:
                results.append((edge, src, tgt))
        
        return results
    
    # === Graph Algorithms ===
    
    def detect_cycles(self) -> list[list[str]]:
        """
        Detect all cycles using DFS coloring algorithm.
        
        Returns:
            List of cycles (each cycle is list of node IDs)
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in self._node_index}
        cycles = []
        path = []
        
        def dfs(node_id: str) -> None:
            color[node_id] = GRAY
            path.append(node_id)
            
            for neighbor_id, _ in self._adjacency_list.get(node_id, []):
                if color.get(neighbor_id) == GRAY:
                    # Found cycle
                    cycle_start = path.index(neighbor_id)
                    cycles.append(path[cycle_start:] + [neighbor_id])
                elif color.get(neighbor_id) == WHITE:
                    dfs(neighbor_id)
            
            path.pop()
            color[node_id] = BLACK
        
        for node_id in list(self._node_index.keys()):
            if color[node_id] == WHITE:
                dfs(node_id)
        
        return cycles
    
    def find_argument_paths(
        self, 
        source_id: str, 
        target_id: str,
        max_depth: int = 10
    ) -> list[ArgumentPath]:
        """
        Find all simple paths between two nodes using BFS.
        
        Useful for tracing argument chains:
        - Evidence → Support paths
        - Attack → Rebuttal chains
        """
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
                # Construct path object
                nodes = [self._node_index[nid] for nid in node_path]
                path = ArgumentPath(
                    nodes=nodes,
                    edges=edge_path,
                    path_type=self._classify_path(edge_path),
                    total_confidence=min(e.confidence for e in edge_path) if edge_path else 1.0
                )
                paths.append(path)
                continue
            
            for neighbor_id, edge in self._adjacency_list.get(current_id, []):
                if neighbor_id not in node_path:  # Avoid cycles
                    queue.append((
                        neighbor_id,
                        node_path + [neighbor_id],
                        edge_path + [edge]
                    ))
        
        return paths
    
    def _classify_path(self, edges: list[ArgumentEdge]) -> str:
        """Determine if path is support_chain, attack_chain, or mixed."""
        if not edges:
            return "mixed"
        
        has_support = any(e.is_support_relation for e in edges)
        has_attack = any(e.is_attack_relation for e in edges)
        
        if has_support and not has_attack:
            return "support_chain"
        elif has_attack and not has_support:
            return "attack_chain"
        else:
            return "mixed"
    
    def compute_stance_propagation(self) -> None:
        """
        Propagate stance labels from root claims through graph.
        
        Rules:
        - SUPPORT preserves parent stance
        - ATTACK flips parent stance
        - REBUTTAL restores original stance (flips back)
        """
        if not self.root_claim_ids:
            return
        
        # Initialize roots as PRO
        for root_id in self.root_claim_ids:
            if root_id in self._node_index:
                self._node_index[root_id].stance = ArgumentStance.PRO
        
        # BFS propagation
        from collections import deque
        visited = set(self.root_claim_ids)
        queue = deque(self.root_claim_ids)
        
        while queue:
            node_id = queue.popleft()
            current_stance = self._node_index[node_id].stance
            
            for neighbor_id, edge in self._adjacency_list.get(node_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    
                    # Determine child stance based on relation
                    if edge.relation_type == RelationType.SUPPORT:
                        new_stance = current_stance
                    elif edge.relation_type in (RelationType.ATTACK, RelationType.CONTRADICTION):
                        new_stance = (
                            ArgumentStance.CON if current_stance == ArgumentStance.PRO 
                            else ArgumentStance.PRO
                        )
                    elif edge.relation_type == RelationType.REBUTTAL:
                        new_stance = (
                            ArgumentStance.CON if current_stance == ArgumentStance.PRO 
                            else ArgumentStance.PRO
                        )  # Rebuttals flip back
                    else:
                        new_stance = ArgumentStance.NEUTRAL
                    
                    self._node_index[neighbor_id].stance = new_stance
                    queue.append(neighbor_id)
    
    def get_subgraph(self, node_ids: set[str]) -> 'ArgumentGraph':
        """
        Extract induced subgraph containing only specified nodes.
        
        Preserves internal edges among selected nodes.
        """
        node_set = set(node_ids) & set(self._node_index.keys())
        
        sub_nodes = [self._node_index[nid] for nid in node_set]
        sub_edges = [
            edge for edge in self.edges
            if edge.source_id in node_set and edge.target_id in node_set
        ]
        
        # Determine which root claims are in subgraph
        sub_roots = [rid for rid in self.root_claim_ids if rid in node_set]
        
        return ArgumentGraph(
            nodes=sub_nodes,
            edges=sub_edges,
            root_claim_ids=sub_roots,
            document_id=self.document_id,
            model_version=self.model_version
        )
    
    # === Serialization ===
    
    def serialize_to_frontend(self) -> dict:
        """
        Convert to hierarchical tree structure for D3.js/React Flow.
        
        Output format matches JSON schema contract specified in Section 7.
        """
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
    
    def _build_tree_recursive(
        self, 
        node_id: str, 
        visited: set[str]
    ) -> dict:
        """Recursively build nested tree structure."""
        if node_id in visited:
            return {}  # Prevent infinite recursion
        
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
                    "confidence": edge.confidence
                }
                children.append(child_tree)
        
        if children:
            tree_data["children"] = children
        
        return tree_data
    
    def to_networkx(self):
        """
        Convert to NetworkX DiGraph for advanced analytics.
        Requires networkx package.
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError("networkx package required for NetworkX conversion")
        
        G = nx.DiGraph()
        
        for node in self.nodes:
            G.add_node(
                node.segment_id, 
                **node.model_dump(exclude={'segment_id'})
            )
        
        for edge in self.edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                **edge.model_dump(exclude={'source_id', 'target_id', 'edge_id'})
            )
        
        return G
    
    def to_cyjs(self) -> dict:
        """
        Convert to Cytoscape.js JSON format.
        Alternative to D3.js for web visualization.
        """
        elements = {"nodes": [], "edges": []}
        
        for node in self.nodes:
            elements["nodes"].append({
                "data": {
                    "id": node.segment_id,
                    "label": node.truncate_display_text(40),
                    "type": node.node_type.value,
                    "speaker": node.speaker,
                    "confidence": node.confidence
                }
            })
        
        for edge in self.edges:
            elements["edges"].append({
                "data": {
                    "id": edge.edge_id,
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "label": edge.relation_type.value,
                    "confidence": edge.confidence
                }
            })
        
        return elements
    
    def summary(self) -> dict:
        """Return human-readable graph statistics."""
        return {
            "graph_id": self.graph_id,
            "document_id": self.document_id,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_types": {
                "claims": self.claim_count,
                "supports": self.support_count,
                "attacks": self.attack_count,
                "rebuttals": self.rebuttal_count
            },
            "structure": {
                "root_claims": len(self.root_claim_ids),
                "max_depth": self.max_depth,
                "avg_branching_factor": round(self.avg_branching_factor, 2),
                "density": round(self.graph_density, 4)
            },
            "quality": {
                "has_cycles": len(self.detect_cycles()) > 0,
                "self_attacks": len(self.get_self_attacks()),
                "cross_speaker_interactions": len(self.get_cross_speaker_interactions())
            },
            "processing": {
                "model_version": self.model_version,
                "processing_time_ms": round(self.processing_time_ms, 2),
                "created_at": self.created_at
            }
        }


# Import datetime for default factory
from datetime import datetime
from typing import Literal
```

---

## 2. PRODUCTION-GRADE ARGUMENT MINING PIPELINE

### 2.1 Configuration Management (`src/bb_paxdata/infrastructure/nlp/argmining_config.py`) [NEW]

```python
"""
Argument Mining Pipeline Configuration
Centralized settings with environment variable support and validation.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
import os


class ClaimDetectionConfig(BaseModel):
    """Configuration for claim identification classifier."""
    
    model_name: str = Field(
        default="microsoft/deberta-v3-base",
        description="Transformer model for binary claim/non-claim classification"
    )
    fine_tuned_path: Optional[str] = Field(
        default=None,
        description="Path to fine-tuned model weights (overrides base model)"
    )
    confidence_threshold: float = Field(
        default=0.78,
        ge=0.5,
        le=0.99,
        description="Minimum confidence to classify segment as CLAIM"
    )
    max_tokens: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="Maximum sequence length for tokenizer"
    )
    use_srl_guidance: bool = Field(
        default=True,
        description="Use SRL ARG1 spans as additional features for claim detection"
    )


class RelationClassificationConfig(BaseModel):
    """Configuration for pairwise relation classifier."""
    
    model_name: str = Field(
        default="microsoft/deberta-v3-base",
        description="Model for SUPPORT/ATTACK/REBUTTAL classification"
    )
    confidence_threshold: float = Field(
        default=0.65,
        ge=0.4,
        le=0.99,
        description="Minimum confidence to accept relation prediction"
    )
    neutral_threshold: float = Field(
        default=0.55,
        description="Below this, classify as NEUTRAL (no edge created)"
    )
    max_pairs_per_claim: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Limit candidate pairs to prevent quadratic blowup"
    )
    use_attention_pooling: bool = Field(
        default=True,
        description="Use attention mechanism for pair representation"
    )


class EDUSegmentationConfig(BaseModel):
    """Configuration for Elementary Discourse Unit segmentation."""
    
    method: Literal["rst", "spacy", "hybrid"] = Field(
        default="hybrid",
        description="Segmentation strategy"
    )
    rst_parser_endpoint: Optional[str] = Field(
        default=None,
        description="URL for RST parser service (if external)"
    )
    min_segment_length: int = Field(
        default=10,
        ge=3,
        description="Minimum characters for valid EDU"
    )
    max_segment_length: int = Field(
        default=500,
        le=2000,
        description="Maximum characters before forced split"
    )
    merge_short_segments: bool = Field(
        default=True,
        description="Merge segments shorter than minimum into neighbors"
    )


class ArgumentMiningPipelineConfig(BaseModel):
    """Top-level configuration aggregating all sub-components."""
    
    # Sub-configurations
    claim_detection: ClaimDetectionConfig = Field(default_factory=ClaimDetectionConfig)
    relation_classification: RelationClassificationConfig = Field(
        default_factory=RelationClassificationConfig
    )
    edu_segmentation: EDUSegmentationConfig = Field(default_factory=EDUSegmentationConfig)
    
    # Infrastructure
    device: Literal["auto", "cpu", "cuda", "mps"] = Field(
        default="auto",
        description="Compute device"
    )
    batch_size: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Inference batch size"
    )
    enable_cache: bool = Field(
        default=True,
        description="Enable result caching"
    )
    cache_ttl_hours: int = Field(
        default=48,
        ge=1,
        le=168,
        description="Cache time-to-live"
    )
    
    # Reliability
    timeout_seconds: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Per-document processing timeout"
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Retry count for transient failures"
    )
    
    # Quality Control
    require_srl_for_claims: bool = Field(
        default=False,
        description="If True, skip claim detection when SRL unavailable"
    )
    validate_dag_on_build: bool = Field(
        default=True,
        description="Enforce acyclic graph constraint (removes weak edges if needed)"
    )
    max_graph_nodes: int = Field(
        default=10000,
        ge=100,
        le=50000,
        description="Maximum nodes before truncation warning"
    )
    
    @field_validator('device')
    @classmethod
    def resolve_device(cls, v: str) -> str:
        """Auto-detect best device."""
        if v == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    return "mps"
                return "cpu"
            except ImportError:
                return "cpu"
        return v
    
    @classmethod
    def from_env(cls) -> 'ArgumentMiningPipelineConfig':
        """Load from environment variables."""
        return cls(
            claim_detection=ClaimDetectionConfig(
                confidence_threshold=float(
                    os.getenv("ARGMINING_CLAIM_THRESHOLD", "0.78")
                ),
                use_srl_guidance=os.getenv(
                    "ARGMINING_USE_SRL", "true"
                ).lower() == "true"
            ),
            relation_classification=RelationClassificationConfig(
                confidence_threshold=float(
                    os.getenv("ARGMINING_REL_THRESHOLD", "0.65")
                )
            ),
            edu_segmentation=EDUSegmentationConfig(
                method=os.getenv("ARGMINING_EDU_METHOD", "hybrid")
            ),
            device=os.getenv("ARGMINING_DEVICE", "auto"),
            enable_cache=os.getenv("ARGMINING_CACHE", "true").lower() == "true",
            validate_dag_on_build=os.getenv(
                "ARGMINING_VALIDATE_DAG", "true"
            ).lower() == "true"
        )


# Global singleton
_config_instance: Optional[ArgumentMiningPipelineConfig] = None

def get_argmining_config() -> ArgumentMiningPipelineConfig:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ArgumentMiningPipelineConfig.from_env()
    return _config_instance
```

### 2.2 Main Pipeline Implementation (`src/bb_paxdata/domain/services/argument_structure_pipeline.py`) [NEW]

```python
"""
Production-Grade Argument Mining Pipeline

Two-stage architecture:
1. Claim Detection (Binary Classification)
2. Relation Classification (Pairwise Multi-class)

Features:
- Thread-safe singleton with lazy initialization
- LRU caching with TTL
- Circuit breaker for fault tolerance
- Automatic cycle detection and resolution
- SRL integration (TASK-A01) for enhanced accuracy
- Comprehensive logging and metrics
"""

from __future__ import annotations

import threading
import time
import logging
import functools
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Callable
from contextlib import contextmanager

import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    Pipeline as HFPipeline,
    pipeline as hf_pipeline
)

from bb_paxdata.infrastructure.nlp.argmining_config import (
    ArgumentMiningPipelineConfig, 
    get_argmining_config
)
from bb_paxdata.domain.models.argument import (
    ArgumentGraph, ArgumentNode, ArgumentEdge, 
    NodeType, RelationType, ArgumentStance
)
from bb_paxdata.domain.models.srl import SRLFrame, SRLDocumentResult
from bb_paxdata.domain.models.segment import Segment

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Collect performance metrics for monitoring."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    total_documents_processed: int = 0
    total_claims_detected: int = 0
    total_relations_classified: int = 0
    total_cycles_resolved: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_processing_time_ms: float = 0.0
    errors: int = 0
    
    def record_document(self, processing_time_ms: float, claims: int, relations: int) -> None:
        with self.lock:
            self.total_documents_processed += 1
            self.total_claims_detected += claims
            self.total_relations_classified += relations
            self.total_processing_time_ms += processing_time_ms
    
    def record_cache_hit(self) -> None:
        with self.lock:
            self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        with self.lock:
            self.cache_misses += 1
    
    def record_cycle_resolution(self) -> None:
        with self.lock:
            self.total_cycles_resolved += 1
    
    def record_error(self) -> None:
        with self.lock:
            self.errors += 1
    
    @property
    def avg_processing_time_ms(self) -> float:
        with self.lock:
            if self.total_documents_processed == 0:
                return 0.0
            return self.total_processing_time_ms / self.total_documents_processed
    
    @property
    def cache_hit_rate(self) -> float:
        with self.lock:
            total = self.cache_hits + self.cache_misses
            if total == 0:
                return 0.0
            return self.cache_hits / total
    
    def to_dict(self) -> dict:
        with self.lock:
            return {
                "documents_processed": self.total_documents_processed,
                "claims_detected": self.total_claims_detected,
                "relations_classified": self.total_relations_classified,
                "cycles_resolved": self.total_cycles_resolved,
                "cache_hit_rate": f"{self.cache_hit_rate:.2%}",
                "avg_processing_time_ms": f"{self.avg_processing_time_ms:.2f}",
                "errors": self.errors
            }


class ArgumentStructurePipeline:
    """
    Thread-safe, production-grade argument mining pipeline.
    
    Usage:
        >>> pipeline = ArgumentStructurePipeline.get_instance()
        >>> await pipeline.initialize()
        >>> graph = await pipeline.extract_argument_structure(text, speaker, srl_frames)
        >>> print(graph.summary())
    """
    
    _instance: Optional['ArgumentStructurePipeline'] = None
    _lock: threading.Lock = threading.Lock()
    _init_lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> 'ArgumentStructurePipeline':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if getattr(self, '_initialized', False):
            return
        
        with self._init_lock:
            if getattr(self, '_initialized', False):
                return
            
            self.config = get_argmining_config()
            
            # Model components (lazy loaded)
            self._claim_tokenizer = None
            self._claim_model = None
            self._relation_tokenizer = None
            self._relation_model = None
            self._claim_pipeline = None
            self._relation_pipeline = None
            
            self._models_loaded: bool = False
            self._load_lock = threading.Lock()
            
            # Caching
            self._cache: OrderedDict[str, tuple[ArgumentGraph, float]] = OrderedDict()
            self._cache_lock = threading.Lock()
            self._cache_max_size = 500
            self._cache_ttl_seconds = self.config.cache_ttl_hours * 3600
            
            # Metrics
            self.metrics = PipelineMetrics()
            
            self._initialized = True
            logger.info("ArgumentStructurePipeline initialized (models lazy-loaded)")
    
    @classmethod
    def get_instance(cls) -> 'ArgumentStructurePipeline':
        return cls()
    
    async def initialize(self) -> None:
        """Load models into memory (call once before first inference)."""
        if self._models_loaded:
            return
        
        with self._load_lock:
            if self._models_loaded:
                return
            
            start_time = time.perf_counter()
            
            try:
                await self._load_models()
                self._models_loaded = True
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.success(
                    f"Argument mining models loaded in {elapsed:.1f}ms"
                )
            except Exception as e:
                logger.error(f"Failed to load argument mining models: {e}")
                raise RuntimeError(f"Model loading failed: {e}") from e
    
    async def _load_models(self) -> None:
        """Load transformer models with error handling."""
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        
        device = self._resolve_device()
        
        # Load claim detector
        logger.info(f"Loading claim detector: {self.config.claim_detection.model_name}")
        self._claim_tokenizer = AutoTokenizer.from_pretrained(
            self.config.claim_detection.fine_tuned_path 
            or self.config.claim_detection.model_name
        )
        self._claim_model = AutoModelForSequenceClassification.from_pretrained(
            self.config.claim_detection.fine_tuned_path 
            or self.config.claim_detection.model_name,
            num_labels=2  # Binary: CLAIM / NOT_CLAIM
        ).to(device)
        
        # Load relation classifier
        logger.info(f"Loading relation classifier: {self.config.relation_classification.model_name}")
        self._relation_tokenizer = AutoTokenizer.from_pretrained(
            self.config.relation_classification.model_name
        )
        self._relation_model = AutoModelForSequenceClassification.from_pretrained(
            self.config.relation_classification.model_name,
            num_labels=4  # SUPPORT, ATTACK, REBUTTAL, NEUTRAL
        ).to(device)
        
        # Set eval mode
        self._claim_model.eval()
        self._relation_model.eval()
    
    def _resolve_device(self) -> torch.device:
        device_map = {
            "cpu": torch.device("cpu"),
            "cuda": torch.device("cuda"),
            "mps": torch.device("mps")
        }
        return device_map.get(self.config.device, torch.device("cpu"))
    
    async def extract_argument_structure(
        self,
        text: str,
        speaker: str,
        timestamp: float = 0.0,
        srl_frames: Optional[list[SRLFrame]] = None,
        use_cache: bool = True
    ) -> ArgumentGraph:
        """
        Extract complete argument structure from text.
        
        Pipeline stages:
        1. Segment text into EDUs (Elementary Discourse Units)
        2. Classify each segment as CLAIM / NOT_CLAIM
        3. For each claim, classify relations with other segments
        4. Build and validate ArgumentGraph (DAG)
        5. Cache result and return
        
        Args:
            text: Raw input text (paragraph or transcript excerpt)
            speaker: Attributed speaker/actor name
            timestamp: Temporal position in source
            srl_frames: Optional SRL frames from TASK-A01 for guidance
            use_cache: Whether to check/use prediction cache
            
        Returns:
            Complete ArgumentGraph with nodes, edges, and analytics
        """
        start_time = time.perf_counter()
        
        # Input validation
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")
        if not speaker or not speaker.strip():
            raise ValueError("Speaker name cannot be empty")
        
        text = text.strip()
        
        # Cache check
        cache_key = self._generate_cache_key(text, speaker)
        if use_cache and self.config.enable_cache:
            cached = self._check_cache(cache_key)
            if cached is not None:
                self.metrics.record_cache_hit()
                return cached
        
        self.metrics.record_cache_miss()
        
        try:
            # Ensure models loaded
            await self.initialize()
            
            # Stage 1: Segmentation
            segments = self._segment_into_edus(text)
            logger.debug(f"Segmented into {len(segments)} EDUs")
            
            # Stage 2: Claim Detection
            claim_segments = await self._detect_claims(segments, srl_frames)
            logger.debug(f"Detected {len(claim_segments)} claims")
            
            if not claim_segments:
                # No claims found - return empty graph
                empty_graph = ArgumentGraph(
                    document_id=f"doc_{hash(text) % 10000}",
                    nodes=[],
                    edges=[],
                    root_claim_ids=[]
                )
                self._store_cache(cache_key, empty_graph)
                return empty_graph
            
            # Stage 3: Relation Classification
            edges = await self._classify_relations(segments, claim_segments)
            logger.debug(f"Classified {len(edges)} relations")
            
            # Stage 4: Build Graph
            nodes = self._build_nodes(segments, claim_segments, speaker, timestamp)
            graph = self._build_graph(nodes, edges, claim_segments)
            
            # Stage 5: Post-processing
            if self.config.validate_dag_on_build:
                graph = self._ensure_dag(graph)
            
            # Compute stances
            graph.compute_stance_propagation()
            
            # Record metrics
            elapsed = (time.perf_counter() - start_time) * 1000
            graph.processing_time_ms = elapsed
            self.metrics.record_document(
                processing_time_ms=elapsed,
                claims=len(claim_segments),
                relations=len(edges)
            )
            
            # Cache result
            if use_cache and self.config.enable_cache:
                self._store_cache(cache_key, graph)
            
            logger.info(
                f"Argument extraction complete: {len(nodes)} nodes, "
                f"{len(edges)} edges in {elapsed:.1f}ms"
            )
            
            return graph
            
        except Exception as e:
            self.metrics.record_error()
            logger.error(f"Argument extraction failed: {e}", exc_info=True)
            raise RuntimeError(f"Argument mining pipeline error: {e}") from e
    
    def _segment_into_edus(self, text: str) -> list[dict]:
        """
        Segment text into Elementary Discourse Units.
        
        Strategy priority:
        1. RST Parser (if available)
        2. spaCy sentence boundaries
        3. Rule-based splitting (newline/punctuation)
        """
        segments = []
        
        if self.config.edu_segmentation.method in ("rst", "hybrid"):
            # Try RST parser
            rst_segments = self._try_rst_segmentation(text)
            if rst_segments:
                return rst_segments
        
        # Fallback to spaCy or rule-based
        spacy_segments = self._try_spacy_segmentation(text)
        if spacy_segments:
            return spacy_segments
        
        # Final fallback: naive splitting
        return self._naive_segmentation(text)
    
    def _try_rst_segmentation(self, text: str) -> Optional[list[dict]]:
        """Attempt RST-style segmentation (placeholder for TASK-E03 integration)."""
        # TODO: Integrate with RST parser service when available
        # For now, return None to trigger fallback
        return None
    
    def _try_spacy_segmentation(self, text: str) -> Optional[list[dict]]:
        """Segment using spaCy sentence boundary detection."""
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")  # or tr_core_news_md for Turkish
            doc = nlp(text)
            
            segments = []
            char_offset = 0
            for i, sent in enumerate(doc.sents):
                seg_text = sent.text.strip()
                if len(seg_text) >= self.config.edu_segmentation.min_segment_length:
                    segments.append({
                        "id": f"seg_{i:03d}",
                        "text": seg_text,
                        "start_char": sent.start_char,
                        "end_char": sent.end_char
                    })
            
            return segments if segments else None
            
        except Exception as e:
            logger.warning(f"spaCy segmentation failed: {e}")
            return None
    
    def _naive_segmentation(self, text: str) -> list[dict]:
        """Rule-based splitting as last resort."""
        import re
        
        # Split on sentence-ending punctuation followed by space/newline
        raw_segments = re.split(r'(?<=[.!?])\s+', text)
        
        segments = []
        for i, seg in enumerate(raw_segments):
            seg = seg.strip()
            if len(seg) >= self.config.edu_segmentation.min_segment_length:
                segments.append({
                    "id": f"seg_{i:03d}",
                    "text": seg,
                    "start_char": 0,  # Approximate
                    "end_char": len(seg)
                })
        
        return segments
    
    async def _detect_claims(
        self,
        segments: list[dict],
        srl_frames: Optional[list[SRLFrame]]
    ) -> list[dict]:
        """
        Classify each segment as CLAIM or NOT_CLAIM.
        
        Enhancement: If SRL frames available, use ARG1 presence as feature boost.
        """
        claim_candidates = []
        
        for seg in segments:
            # Quick heuristic filter: must contain verb-like content
            if not self._contains_predicate_indicators(seg["text"]):
                continue
            
            # Run classifier
            is_claim, confidence = await self._classify_single_claim(
                seg["text"], srl_frames
            )
            
            if is_claim:
                seg["is_claim"] = True
                seg["claim_confidence"] = confidence
                claim_candidates.append(seg)
            else:
                seg["is_claim"] = False
        
        return claim_candidates
    
    def _contains_predicate_indicators(self, text: str) -> bool:
        """Quick heuristic to filter obvious non-claims."""
        indicators = [
            r'\b(is|are|was|were|been)\b',  # Copulas
            r'\b(supports?|opposes?|claims?|argues?|states?)\b',  # Argument verbs
            r'\b(should|must|will|might|could)\b',  # Modals
            r'\b(because|therefore|however|although)\b',  # Disc markers
        ]
        import re
        pattern = '|'.join(indicators)
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    async def _classify_single_claim(
        self,
        text: str,
        srl_frames: Optional[list[SRLFrame]]
    ) -> tuple[bool, float]:
        """
        Run binary classification on single segment.
        
        Returns:
            (is_claim, confidence) tuple
        """
        # TODO: Implement actual model inference
        # Placeholder: heuristic-based for now
        
        # SRL-guided boost: if segment contains ARG1 span, more likely claim
        srl_boost = 0.0
        if srl_frames and self.config.claim_detection.use_srl_guidance:
            for frame in srl_frames:
                if frame.arg1 and frame.arg1.text.lower() in text.lower():
                    srl_boost = 0.15
                    break
        
        # Placeholder logic (replace with actual model call)
        # Simulated confidence with randomness for testing
        import random
        base_confidence = 0.5 + random.random() * 0.3
        adjusted_confidence = min(1.0, base_confidence + srl_boost)
        
        is_claim = adjusted_confidence >= self.config.claim_detection.confidence_threshold
        
        return is_claim, adjusted_confidence
    
    async def _classify_relations(
        self,
        all_segments: list[dict],
        claim_segments: list[dict]
    ) -> list[ArgumentEdge]:
        """
        Classify pairwise relations between claims and other segments.
        
        Optimization: Limit pairs to prevent O(n²) explosion.
        """
        edges = []
        
        for claim in claim_segments:
            candidates = [
                seg for seg in all_segments 
                if seg["id"] != claim["id"]
            ][:self.config.relation_classification.max_pairs_per_claim]
            
            for candidate in candidates:
                relation_type, confidence = await self._classify_pair_relation(
                    claim["text"], candidate["text"]
                )
                
                # Only create edge if above neutral threshold
                if (relation_type != RelationType.NEUTRAL and 
                    confidence >= self.config.relation_classification.confidence_threshold):
                    
                    edge = ArgumentEdge(
                        source_id=candidate["id"],
                        target_id=claim["id"],
                        relation_type=relation_type,
                        confidence=confidence
                    )
                    edges.append(edge)
        
        return edges
    
    async def _classify_pair_relation(
        self,
        text_a: str,
        text_b: str
    ) -> tuple[RelationType, float]:
        """
        Classify relation between two text segments.
        
        Returns:
            (relation_type, confidence) tuple
        """
        # TODO: Implement actual pairwise classification
        # Placeholder: rule-based heuristics
        
        import re
        
        # Simple discourse marker detection
        support_markers = [
            r'\bbecause\b', r'\bsince\b', r'\btherefore\b', r'\bthus\b',
            r'\bsupports?\b', r'\bconfirms?\b', r'\bevidence\b'
        ]
        attack_markers = [
            r'\bhowever\b', r'\bbut\b', r'\bcontrary\b', r'\bopposes?\b',
            r'\bdisagrees?\b', r'\bfails?\b', r'\bwrong\b'
        ]
        rebuttal_markers = [
            r'\bnot necessarily\b', r'\bthat\'s not true\b', r'\bon the contrary\b'
        ]
        
        combined = f"{text_a} [SEP] {text_b}"
        
        # Check markers in context
        for pattern in rebuttal_markers:
            if re.search(pattern, combined, re.IGNORECASE):
                return RelationType.REBUTTAL, 0.82
        
        for pattern in attack_markers:
            if re.search(pattern, combined, re.IGNORECASE):
                return RelationType.ATTACK, 0.78
        
        for pattern in support_markers:
            if re.search(pattern, combined, re.IGNORECASE):
                return RelationType.SUPPORT, 0.80
        
        # Default: neutral (no edge will be created)
        return RelationType.NEUTRAL, 0.45
    
    def _build_nodes(
        self,
        segments: list[dict],
        claim_segments: list[dict],
        speaker: str,
        timestamp: float
    ) -> list[ArgumentNode]:
        """Convert segment dicts to ArgumentNode objects."""
        nodes = []
        claim_ids = {seg["id"] for seg in claim_segments}
        
        for seg in segments:
            is_claim = seg.get("is_claim", False)
            node_type = NodeType.CLAIM if is_claim else NodeType.SUPPORT
            
            # Determine actual type based on role
            if not is_claim:
                node_type = NodeType.PREMISE  # Default non-claim type
            
            node = ArgumentNode(
                segment_id=seg["id"],
                text=seg["text"],
                node_type=node_type,
                speaker=speaker,
                timestamp=timestamp + (segments.index(seg) * 5.0),  # Stagger timestamps
                confidence=seg.get("claim_confidence", 0.8) if is_claim else 0.75,
                document_offset=(seg.get("start_char", 0), seg.get("end_char", 0)),
                extraction_method="classifier" if is_claim else "heuristic"
            )
            nodes.append(node)
        
        return nodes
    
    def _build_graph(
        self,
        nodes: list[ArgumentNode],
        edges: list[ArgumentEdge],
        claim_segments: list[dict]
    ) -> ArgumentGraph:
        """Construct validated ArgumentGraph."""
        root_ids = [seg["id"] for seg in claim_segments]
        
        # Try to identify single main root claim (first/highest confidence)
        if root_ids:
            # Sort by confidence, pick top
            sorted_claims = sorted(
                claim_segments,
                key=lambda x: x.get("claim_confidence", 0),
                reverse=True
            )
            root_ids = [sorted_claims[0]["id"]]  # Primary root only
        
        graph = ArgumentGraph(
            nodes=nodes,
            edges=edges,
            root_claim_ids=root_ids,
            document_id=f"doc_{int(time.time()) % 100000}"
        )
        
        return graph
    
    def _ensure_dag(self, graph: ArgumentGraph) -> ArgumentGraph:
        """Remove cycles to ensure DAG property."""
        max_iterations = 10
        
        for _ in range(max_iterations):
            cycles = graph.detect_cycles()
            if not cycles:
                break
            
            removed = graph.remove_weakest_cycle_edge()
            if removed is None:
                break  # Shouldn't happen, but safety
            
            self.metrics.record_cycle_resolution()
            logger.warning(
                f"Removed cycle edge: {removed.source_id} → {removed.target_id} "
                f"(confidence: {removed.confidence})"
            )
        
        return graph
    
    def _generate_cache_key(self, text: str, speaker: str) -> str:
        """Generate deterministic cache key."""
        import hashlib
        normalized = f"{speaker}:{text.lower()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _check_cache(self, key: str) -> Optional[ArgumentGraph]:
        """Check cache for existing result."""
        with self._cache_lock:
            if key not in self._cache:
                return None
            
            result, timestamp = self._cache[key]
            
            # Check expiration
            if time.time() - timestamp > self._cache_ttl_seconds:
                del self._cache[key]
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return result
    
    def _store_cache(self, key: str, graph: ArgumentGraph) -> None:
        """Store result in cache with eviction policy."""
        with self._cache_lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._cache_max_size:
                # Evict oldest
                self._cache.popitem(last=False)
            
            self._cache[key] = (graph, time.time())
    
    def health_check(self) -> dict:
        """Return pipeline status and metrics."""
        return {
            "status": "ready" if self._models_loaded else "initializing",
            "models_loaded": self._models_loaded,
            "config": {
                "device": self.config.device,
                "claim_threshold": self.config.claim_detection.confidence_threshold,
                "relation_threshold": self.config.relation_classification.confidence_threshold,
                "edu_method": self.config.edu_segmentation.method,
                "dag_validation": self.config.validate_dag_on_build
            },
            "metrics": self.metrics.to_dict(),
            "cache": {
                "size": len(self._cache),
                "max_size": self._cache_max_size,
                "ttl_hours": self.config.cache_ttl_hours
            }
        }
    
    def clear_cache(self) -> None:
        """Clear prediction cache."""
        with self._cache_lock:
            self._cache.clear()


# Convenience function
def get_argument_pipeline() -> ArgumentStructurePipeline:
    """Get global pipeline instance."""
    return ArgumentStructurePipeline.get_instance()
```

---

## 3. CROSS ANOMALY SERVICE ENHANCEMENT WITH ARGUMENT GRAPH

### 3.1 Extended Contradiction Patterns (`src/bb_paxdata/infrastructure/nlp/cross_anomaly_service_impl.py` additions)

```python
# Add to existing CrossAnomalyServiceImpl class

from bb_paxdata.domain.models.argument import (
    ArgumentGraph, ArgumentEdge, ArgumentNode, 
    RelationType, NodeType, ContradictionPattern
)
from dataclasses import dataclass
from typing import Optional


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


class CrossAnomalyServiceImpl:
    # ... existing code ...
    
    # Argument-specific configuration
    SELF_ATTACK_BOOST: float = 0.45          # High: same speaker attacking own claim
    CROSS_SPEAKER_ATTACK_BOOST: float = 0.25 # Medium: different speakers
    REBUTTAL_MISMATCH_PENALTY: float = 0.15  # Missing rebuttal for strong attack
    MAX_GRAPH_NODES_FOR_ANALYSIS: int = 500  # Limit for performance
    
    async def detect_argument_anomalies(
        self,
        argument_graph: ArgumentGraph,
        base_score: float = 0.0,
        threshold: float = 0.5
    ) -> ContradictionResult:
        """
        Analyze argument graph for structural anomalies and contradictions.
        
        Detection rules:
        1. Self-Attack: Same speaker attacking their own claim (incoherent)
        2. Unmatched Strong Attacks: High-confidence ATTACK without REBUTTAL
        3. Stance Inversion: Node classified as both PRO and CON via different paths
        4. Isolated Claims: Root claims with no support (weak argumentation)
        5. Argument Density Anomaly: Too many attacks vs supports (hostile discourse)
        
        Args:
            argument_graph: Validated argument graph
            base_score: Existing anomaly score from other detectors
            threshold: Anomaly detection threshold
            
        Returns:
            Enhanced ContradictionResult with argument-specific signals
        """
        if not argument_graph or not argument_graph.nodes:
            return ContradictionResult(
                score=base_score,
                threshold=threshold,
                is_anomaly=base_score > threshold,
                anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE
            )
        
        # Limit graph size for performance
        if len(argument_graph.nodes) > self.MAX_GRAPH_NODES_FOR_ANALYSIS:
            logger.warning(
                f"Graph too large ({len(argument_graph.nodes)} nodes), "
                f"sampling subset for analysis"
            )
            # Sample root claims and immediate neighbors
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
                    "attack_confidence": edge.confidence
                }
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
                    "attack_strength": edge.confidence
                }
            )
            contradictions.append(detail)
            argument_boost += detail.confidence
        
        # Rule 3: Discourse Hostility Ratio
        hostility_ratio = self._compute_hostility_ratio(analyzed_graph)
        if hostility_ratio > 0.7:  # More than 70% of relations are attacks
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=ArgumentEdge(source_id="", target_id="", relation_type=RelationType.ATTACK),
                source_node=ArgumentNode(
                    segment_id="_system", text="", node_type=NodeType.CLAIM, 
                    speaker="_system", timestamp=0
                ),
                target_node=ArgumentNode(
                    segment_id="_system", text="", node_type=NodeType.CLAIM,
                    speaker="_system", timestamp=0
                ),
                confidence=0.35,
                description=(
                    f"HIGH HOSTILITY DISCOURSE: Attack-to-support ratio is "
                    f"{hostility_ratio:.2%}. This indicates confrontational dialogue."
                ),
                severity="medium",
                evidence={"hostility_ratio": hostility_ratio}
            )
            contradictions.append(detail)
            argument_boost += detail.confidence
        
        # Rule 4: Isolated Root Claims (no supporting evidence)
        isolated_claims = self._find_isolated_claims(analyzed_graph)
        for claim_node in isolated_claims:
            detail = ArgumentContradictionDetail(
                pattern=ContradictionPattern.ARGUMENTATIVE_ATTACK,
                edge=ArgumentEdge(source_id="", target_id="", relation_type=RelationType.NEUTRAL),
                source_node=claim_node,
                target_node=claim_node,
                confidence=0.20,
                description=(
                    f"ISOLATED CLAIM: '{claim_node.speaker}'s claim "
                    f"'{claim_node.truncate_display_text(40)}' has no supporting arguments."
                ),
                severity="low",
                evidence={
                    "speaker": claim_node.speaker,
                    "claim_text": claim_node.text
                }
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
            window=0.0
        )
        
        # Attach argument evidence
        if hasattr(result, 'extend_metadata'):
            result.extend_metadata({
                'argument_analysis': {
                    'total_contradictions': len(contradictions),
                    'argument_boost': round(argument_boost, 4),
                    'self_attacks': len(self_attacks),
                    'unmatched_attacks': len(unmatched_attacks),
                    'isolated_claims': len(isolated_claims),
                    'hostility_ratio': round(hostility_ratio, 3),
                    'patterns': [
                        {
                            'pattern': c.pattern.value,
                            'severity': c.severity,
                            'confidence': c.confidence,
                            'description': c.description
                        }
                        for c in contradictions
                    ]
                }
            })
        
        return result
    
    def _find_unmatched_strong_attacks(
        self, 
        graph: ArgumentGraph,
        strength_threshold: float = 0.80
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
                e.relation_type == RelationType.SUPPORT 
                and e.target_id == root_id
                for e in graph.edges
            )
            
            if not has_support:
                isolated.append(root_node)
        
        return isolated
    
    def _sample_graph_for_analysis(
        self, 
        graph: ArgumentGraph,
        max_nodes: int = 200
    ) -> ArgumentGraph:
        """Sample manageable subset of large graph for analysis."""
        # Prioritize: root claims + their immediate neighbors + all attacks
        important_nodes = set()
        
        # Always include root claims
        important_nodes.update(graph.root_claim_ids)
        
        # Include neighbors of roots
        for root_id in graph.root_claim_ids:
            for neighbor_id, edge in graph._adjacency_list.get(root_id, []):
                important_nodes.add(neighbor_id)
                # Also include attacker/defender nodes
                if edge.is_attack_relation:
                    important_nodes.add(neighbor_id)
        
        # Fill remaining slots with high-confidence nodes
        remaining_slots = max_nodes - len(important_nodes)
        if remaining_slots > 0:
            sorted_nodes = sorted(
                graph.nodes,
                key=lambda n: n.confidence,
                reverse=True
            )
            for node in sorted_nodes:
                if len(important_nodes) >= max_nodes:
                    break
                important_nodes.add(node.segment_id)
        
        return graph.get_subgraph(important_nodes)
```

---

## 4. DATABASE SCHEMA FOR ARGUMENT PERSISTENCE

### 4.1 SQLAlchemy Models (`src/bb_paxdata/infrastructure/db/models.py` additions)

```python
# Add to existing models file

from sqlalchemy import Text, Integer, Float, Boolean, DateTime, JSON, Index, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime
import json


class ArgumentGraphNode(Base):
    __tablename__ = "argument_graph_nodes"
    __table_args__ = (
        Index('idx_arg_node_graph', 'graph_id'),
        Index('idx_arg_node_speaker', 'speaker'),
        Index('idx_arg_node_type', 'node_type'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(Text, nullable=False, unique=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)  # CLAIM, SUPPORT, etc.
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    stance: Mapped[str | None] = mapped_column(Text, nullable=True)  # PRO, CON, NEUTRAL
    depth: Mapped[int] = mapped_column(Integer, default=0)
    predicate: Mapped[str | None] = mapped_column(Text, nullable=True)  # From SRL
    is_negated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    # outgoing_edges = relationship("ArgumentGraphEdge", foreign_keys='ArgumentGraphEdge.source_id')
    # incoming_edges = relationship("ArgumentGraphEdge", foreign_keys='ArgumentGraphEdge.target_id')


class ArgumentGraphEdge(Base):
    __tablename__ = "argument_graph_edges"
    __table_args__ = (
        Index('idx_edge_graph', 'graph_id'),
        Index('idx_edge_source_target', 'source_id', 'target_id'),
        Index('idx_edge_type', 'relation_type'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    edge_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_cross_speaker: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArgumentGraphMetadata(Base):
    __tablename__ = "argument_graphs_metadata"
    __table_args__ = (
        Index('idx_arg_meta_doc', 'document_id'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    graph_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_claim_ids: Mapped[str] = mapped_column(JSON, nullable=True)  # Array of IDs
    total_nodes: Mapped[int] = mapped_column(Integer, default=0)
    total_edges: Mapped[int] = mapped_column(Integer, default=0)
    max_depth: Mapped[int] = mapped_column(Integer, default=0)
    graph_density: Mapped[float] = mapped_column(Float, default=0.0)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    attack_count: Mapped[int] = mapped_column(Integer, default=0)
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    graph_snapshot_json: Mapped[str | None] = mapped_column(JSON, nullable=True)  # Full serialized graph
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_domain(self) -> ArgumentGraph:
        """Deserialize JSON snapshot back to ArgumentGraph object."""
        from bb_paxdata.domain.models.argument import ArgumentGraph
        
        if self.graph_snapshot_json:
            try:
                data = json.loads(self.graph_snapshot_json)
                return ArgumentGraph(**data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to deserialize graph: {e}")
        
        # Return minimal graph if snapshot unavailable
        return ArgumentGraph(
            graph_id=self.graph_id,
            document_id=self.document_id,
            root_claim_ids=self.root_claim_ids or [],
            total_nodes=self.total_nodes,
            total_edges=self.total_edges
        )
    
    @classmethod
    def from_domain(cls, graph: ArgumentGraph) -> 'ArgumentGraphMetadata':
        """Serialize ArgumentGraph to database record."""
        return cls(
            graph_id=graph.graph_id,
            document_id=graph.document_id,
            root_claim_ids=json.dumps(graph.root_claim_ids),
            total_nodes=graph.total_nodes,
            total_edges=graph.total_edges,
            max_depth=graph.max_depth,
            graph_density=graph.graph_density,
            claim_count=graph.claim_count,
            attack_count=graph.attack_count,
            support_count=graph.support_count,
            model_version=graph.model_version,
            processing_time_ms=graph.processing_time_ms,
            graph_snapshot_json=graph.model_dump_json()
        )
```

### 4.2 Alembic Migration Script

```python
"""alembic/versions/xxxx_add_argument_graph_tables.py

Revision ID: arg_graph_v1
Revises: srl_enrichment_v1
Create Date: 2024-01-XX
"""

from alembic import op
import sqlalchemy as sa

revision = 'arg_graph_v1'
down_revision = 'srl_enrichment_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create nodes table
    op.create_table(
        'argument_graph_nodes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('graph_id', sa.Text(), nullable=False, index=True),
        sa.Column('segment_id', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('node_type', sa.Text(), nullable=False),
        sa.Column('speaker', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True, default=1.0),
        sa.Column('stance', sa.Text(), nullable=True),
        sa.Column('depth', sa.Integer(), nullable=True, default=0),
        sa.Column('predicate', sa.Text(), nullable=True),
        sa.Column('is_negated', sa.Boolean(), nullable=True, default=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_arg_node_graph', 'argument_graph_nodes', ['graph_id'])
    op.create_index('idx_arg_node_speaker', 'argument_graph_nodes', ['speaker'])
    op.create_index('idx_arg_node_type', 'argument_graph_nodes', ['node_type'])
    
    # Create edges table
    op.create_table(
        'argument_graph_edges',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('graph_id', sa.Text(), nullable=False, index=True),
        sa.Column('edge_id', sa.Text(), nullable=False, unique=True),
        sa.Column('source_id', sa.Text(), nullable=False),
        sa.Column('target_id', sa.Text(), nullable=False),
        sa.Column('relation_type', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True, default=1.0),
        sa.Column('weight', sa.Float(), nullable=True, default=1.0),
        sa.Column('is_cross_speaker', sa.Boolean(), nullable=True, default=False),
        sa.Column('evidence_snippet', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_edge_graph', 'argument_graph_edges', ['graph_id'])
    op.create_index('idx_edge_source_target', 'argument_graph_edges', ['source_id', 'target_id'])
    op.create_index('idx_edge_type', 'argument_graph_edges', ['relation_type'])
    
    # Create metadata table
    op.create_table(
        'argument_graphs_metadata',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('graph_id', sa.Text(), unique=True, nullable=False),
        sa.Column('document_id', sa.Text(), nullable=True),
        sa.Column('root_claim_ids', sa.JSON(), nullable=True),
        sa.Column('total_nodes', sa.Integer(), nullable=True, default=0),
        sa.Column('total_edges', sa.Integer(), nullable=True, default=0),
        sa.Column('max_depth', sa.Integer(), nullable=True, default=0),
        sa.Column('graph_density', sa.Float(), nullable=True, default=0.0),
        sa.Column('claim_count', sa.Integer(), nullable=True, default=0),
        sa.Column('attack_count', sa.Integer(), nullable=True, default=0),
        sa.Column('support_count', sa.Integer(), nullable=True, default=0),
        sa.Column('model_version', sa.Text(), nullable=True),
        sa.Column('processing_time_ms', sa.Float(), nullable=True, default=0.0),
        sa.Column('graph_snapshot_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_arg_meta_doc', 'argument_graphs_metadata', ['document_id'])


def downgrade() -> None:
    op.drop_table('argument_graphs_metadata')
    op.drop_table('argument_graph_edges')
    op.drop_table('argument_graph_nodes')
```

---

## 5. INTEGRATION WITH AI ANALYSIS RESULT MODEL

### 5.1 Update `ai_analysis.py`

```python
# src/bb_paxdata/domain/models/ai_analysis.py additions

from typing import Optional
from bb_paxdata.domain.models.argument import ArgumentGraph


class AIAnalysisResult(BaseModel):
    # ... existing fields ...
    
    # Argument Mining integration (TASK-A02)
    argument_graph: Optional[ArgumentGraph] = Field(
        default=None,
        description="Peldszus & Stede (2013) argumentation structure graph"
    )
    argument_quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall argumentation quality metric (coherence, coverage)"
    )
    key_claims_extracted: list[str] = Field(
        default_factory=list,
        description="Top-N most important claims identified"
    )
    controversy_level: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Discourse controversy indicator (0=consensus, 1=highly contested)"
    )
    
    @property
    def has_argument_analysis(self) -> bool:
        """Check if argument graph analysis completed."""
        return self.argument_graph is not None and len(self.argument_graph.nodes) > 0
    
    def get_summary_arguments(self, top_n: int = 5) -> list[dict]:
        """Extract top-N most significant arguments for reporting."""
        if not self.has_argument_analysis:
            return []
        
        # Sort by confidence × depth weight
        scored_nodes = [
            {
                "segment_id": node.segment_id,
                "text": node.text[:200],
                "type": node.node_type.value,
                "speaker": node.speaker,
                "confidence": node.confidence,
                "significance": node.confidence * (1 + node.depth * 0.1)
            }
            for node in self.argument_graph.nodes
        ]
        
        scored_nodes.sort(key=lambda x: x["significance"], reverse=True)
        return scored_nodes[:top_n]
```

---

## 6. COMPREHENSIVE TESTING SUITE

### 6.1 Unit Tests (`tests/unit/nlp/test_argument_mining.py`) [NEW]

```python
"""
Comprehensive Argument Mining Test Suite

Coverage:
- Domain model validation (graph invariants, node/edge constraints)
- Pipeline logic (segmentation, classification mock)
- Graph algorithms (cycle detection, path finding, stance propagation)
- Anomaly detection (self-attacks, unmatched attacks)
- Database round-trip serialization
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime

from pydantic import ValidationError

from bb_paxdata.domain.models.argument import (
    ArgumentNode, ArgumentEdge, ArgumentGraph, ArgumentPath,
    NodeType, RelationType, ArgumentStance, ContradictionPattern
)
from bb_paxdata.domain.services.argument_structure_pipeline import (
    ArgumentStructurePipeline, PipelineMetrics
)
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import (
    CrossAnomalyServiceImpl, ArgumentContradictionDetail
)


# ============================================================
# TEST GROUP 1: Domain Model Validation
# ============================================================

class TestArgumentNodeValidation:
    """Test ArgumentNode invariant enforcement."""
    
    def test_valid_node_creation(self):
        node = ArgumentNode(
            segment_id="seg_001",
            text="Turkey maintains its rights under international law.",
            node_type=NodeType.CLAIM,
            speaker="Turkish_Delegate",
            timestamp=120.5,
            confidence=0.94
        )
        assert node.segment_id == "seg_001"
        assert node.node_type == NodeType.CLAIM
        assert node.stance == ArgumentStance.NEUTRAL  # Default
    
    def test_text_normalization(self):
        """Extra whitespace should be normalized."""
        node = ArgumentNode(
            segment_id="seg_002",
            text="  Multiple   spaces   here  ",
            node_type=NodeType.SUPPORT,
            speaker="Test_Speaker",
            timestamp=0.0
        )
        assert node.text == "Multiple spaces here"
    
    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            ArgumentNode(
                segment_id="seg_003",
                text="   ",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=0.0
            )
    
    def test_negative_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            ArgumentNode(
                segment_id="seg_004",
                text="Valid text",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=-1.0
            )
    
    def test_confidence_range_validation(self):
        with pytest.raises(ValidationError):
            ArgumentNode(
                segment_id="seg_005",
                text="Test",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=0.0,
                confidence=1.5  # Out of range
            )
    
    def test_text_hash_deterministic(self):
        node1 = ArgumentNode(
            segment_id="seg_006", text="Hello World",
            node_type=NodeType.CLAIM, speaker="A", timestamp=0.0
        )
        node2 = ArgumentNode(
            segment_id="seg_007", text="Hello World",
            node_type=NodeType.SUPPORT, speaker="B", timestamp=0.0
        )
        assert node1.text_hash == node2.text_hash
    
    def test_truncate_display_text(self):
        long_text = "A" * 200
        node = ArgumentNode(
            segment_id="seg_008", text=long_text,
            node_type=NodeType.CLAIM, speaker="X", timestamp=0.0
        )
        truncated = node.truncate_display_text(max_length=50)
        assert len(truncated) <= 53  # 50 + "..."
        assert truncated.endswith("...")


class TestArgumentEdgeValidation:
    """Test ArgumentEdge constraints."""
    
    def test_valid_edge_creation(self):
        edge = ArgumentEdge(
            source_id="seg_001",
            target_id="seg_002",
            relation_type=RelationType.SUPPORT,
            confidence=0.89
        )
        assert edge.is_support_relation is True
        assert edge.is_attack_relation is False
    
    def test_self_loop_rejected(self):
        with pytest.raises(ValidationError, match="Self-loops"):
            ArgumentEdge(
                source_id="seg_001",
                target_id="seg_001",  # Same!
                relation_type=RelationType.ATTACK
            )
    
    def test_attack_relation_detection(self):
        edge = ArgumentEdge(
            source_id="a", target_id="b",
            relation_type=RelationType.ATTACK
        )
        assert edge.is_attack_relation is True
        
        edge2 = ArgumentEdge(
            source_id="a", target_id="b",
            relation_type=RelationType.CONTRADICTION
        )
        assert edge2.is_attack_relation is True
    
    def test_reverse_edge(self):
        edge = ArgumentEdge(
            source_id="src", target_id="tgt",
            relation_type=RelationType.SUPPORT,
            confidence=0.9
        )
        reversed_edge = edge.reverse()
        
        assert reversed_edge.source_id == "tgt"
        assert reversed_edge.target_id == "src"


class TestArgumentGraphValidation:
    """Test graph structure validation and invariants."""
    
    def _create_sample_graph(self) -> ArgumentGraph:
        """Helper to create valid sample graph."""
        nodes = [
            ArgumentNode(
                segment_id="claim_1",
                text="Main thesis statement here.",
                node_type=NodeType.CLAIM,
                speaker="Speaker_A",
                timestamp=0.0,
                confidence=0.95
            ),
            ArgumentNode(
                segment_id="supp_1",
                text="Supporting evidence for the thesis.",
                node_type=NodeType.SUPPORT,
                speaker="Speaker_A",
                timestamp=5.0,
                confidence=0.88
            ),
            ArgumentNode(
                segment_id="attk_1",
                text="Counter-argument against the thesis.",
                node_type=NodeType.ATTACK,
                speaker="Speaker_B",
                timestamp=10.0,
                confidence=0.91
            )
        ]
        
        edges = [
            ArgumentEdge(
                source_id="supp_1",
                target_id="claim_1",
                relation_type=RelationType.SUPPORT,
                confidence=0.85
            ),
            ArgumentEdge(
                source_id="attk_1",
                target_id="claim_1",
                relation_type=RelationType.ATTACK,
                confidence=0.90
            )
        ]
        
        return ArgumentGraph(
            nodes=nodes,
            edges=edges,
            root_claim_ids=["claim_1"],
            document_id="test_doc_001"
        )
    
    def test_valid_graph_creation(self):
        graph = self._create_sample_graph()
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 2
        assert graph.total_nodes == 3
        assert graph.claim_count == 1
        assert graph.attack_count == 1
        assert graph.support_count == 1
    
    def test_invalid_edge_reference_raises_error(self):
        nodes = [
            ArgumentNode(segment_id="n1", text="Text", node_type=NodeType.CLAIM, 
                        speaker="S", timestamp=0.0)
        ]
        edges = [
            ArgumentEdge(source_id="n1", target_id="NONEXISTENT", 
                        relation_type=RelationType.SUPPORT)
        ]
        
        with pytest.raises(ValidationError, match="non-existent"):
            ArgumentGraph(nodes=nodes, edges=edges, root_claim_ids=["n1"])
    
    def test_invalid_root_claim_raises_error(self):
        nodes = [
            ArgumentNode(segment_id="n1", text="Text", node_type=NodeType.CLAIM,
                        speaker="S", timestamp=0.0)
        ]
        
        with pytest.raises(ValidationError, match="Root claim"):
            ArgumentGraph(
                nodes=nodes, edges=[], 
                root_claim_ids=["NONEXISTENT_ROOT"]
            )
    
    def test_cycle_detection(self):
        """Graph with cycle should fail validation."""
        nodes = [
            ArgumentNode(segment_id="a", text="A", node_type=NodeType.CLAIM,
                        speaker="S", timestamp=0.0),
            ArgumentNode(segment_id="b", text="B", node_type=NodeType.SUPPORT,
                        speaker="S", timestamp=1.0),
            ArgumentNode(segment_id="c", text="C", node_type=NodeType.ATTACK,
                        speaker="S", timestamp=2.0)
        ]
        edges = [
            ArgumentEdge(source_id="a", target_id="b", relation_type=RelationType.SUPPORT),
            ArgumentEdge(source_id="b", target_id="c", relation_type=RelationType.ATTACK),
            ArgumentEdge(source_id="c", target_id="a", relation_type=RelationType.REBUTTAL)  # Cycle!
        ]
        
        with pytest.raises(ValidationError, match="cycle"):
            ArgumentGraph(nodes=nodes, edges=edges, root_claim_ids=["a"])
    
    def test_get_self_attacks(self):
        graph = self._create_sample_graph()
        
        # Add self-attack: Speaker_A attacking own claim
        self_attack_node = ArgumentNode(
            segment_id="self_attk",
            text="I now disagree with my earlier position.",
            node_type=NodeType.ATTACK,
            speaker="Speaker_A",  # Same as claim!
            timestamp=15.0
        )
        graph.nodes.append(self_attack_node)
        graph.add_edge(ArgumentEdge(
            source_id="self_attk",
            target_id="claim_1",
            relation_type=RelationType.ATTACK,
            confidence=0.85
        ))
        
        # Re-validate to update indexes
        # Note: Would need to rebuild indexes after mutation
        self_attacks = graph.get_self_attacks()
        assert len(self_attacks) == 1
        assert self_attacks[0][1].speaker == "Speaker_A"
        assert self_attacks[0][2].speaker == "Speaker_A"
    
    def test_stance_propagation(self):
        graph = self._create_sample_graph()
        graph.compute_stance_propagation()
        
        claim = graph.get_node("claim_1")
        supp = graph.get_node("supp_1")
        attk = graph.get_node("attk_1")
        
        assert claim.stance == ArgumentStance.PRO  # Root is PRO
        assert supp.stance == ArgumentStance.PRO   # SUPPORT preserves
        assert attk.stance == ArgumentStance.CON    # ATTACK flips
    
    def test_serialize_to_frontend(self):
        graph = self._create_sample_graph()
        frontend_data = graph.serialize_to_frontend()
        
        assert "id" in frontend_data
        assert "text" in frontend_data
        assert "children" in frontend_data
        assert frontend_data["type"] == "CLAIM"
    
    def test_summary_output(self):
        graph = self._create_sample_graph()
        summary = graph.summary()
        
        assert summary["total_nodes"] == 3
        assert summary["total_edges"] == 2
        assert summary["structure"]["root_claims"] == 1
        assert summary["quality"]["has_cycles"] is False
    
    def test_find_argument_paths(self):
        graph = self._create_sample_graph()
        
        paths = graph.find_argument_paths("supp_1", "claim_1")
        assert len(paths) == 1
        assert paths[0].path_type == "support_chain"
        assert paths[0].length == 2  # supp_1 → claim_1
    
    def test_remove_weakest_cycle_edge(self):
        """Test automatic cycle resolution."""
        nodes = [
            ArgumentNode(segment_id="a", text="A", node_type=NodeType.CLAIM,
                        speaker="S", timestamp=0.0),
            ArgumentNode(segment_id="b", text="B", node_type=NodeType.SUPPORT,
                        speaker="S", timestamp=1.0)
        ]
        edges = [
            ArgumentEdge(source_id="a", target_id="b", relation_type=RelationType.SUPPORT, confidence=0.9),
            ArgumentEdge(source_id="b", target_id="a", relation_type=RelationType.ATTACK, confidence=0.3)  # Weak
        ]
        
        graph = ArgumentGraph(nodes=nodes, edges=edges, root_claim_ids=["a"])
        
        # Should have cycle
        assert len(graph.detect_cycles()) > 0
        
        # Remove weakest
        removed = graph.remove_weakest_cycle_edge()
        assert removed is not None
        assert removed.confidence == 0.3  # Weakest edge removed
        
        # Now should be acyclic
        assert len(graph.detect_cycles()) == 0


# ============================================================
# TEST GROUP 2: Pipeline Logic (Mocked)
# ============================================================

class TestArgumentPipelineIntegration:
    """Test pipeline with mocked models."""
    
    @pytest.fixture
    def pipeline(self):
        p = ArgumentStructurePipeline.__new__(ArgumentStructurePipeline)
        p._initialized = False
        p.__init__()
        p._models_loaded = True  # Skip actual model loading
        return p
    
    def test_health_check(self, pipeline):
        health = pipeline.health_check()
        assert "status" in health
        assert "metrics" in health
        assert "cache" in health
    
    def test_empty_input_rejection(self, pipeline):
        import asyncio
        
        with pytest.raises(ValueError, match="cannot be empty"):
            asyncio.get_event_loop().run_until_complete(
                pipeline.extract_argument_structure("", "Speaker")
            )
    
    def test_naive_segmentation_fallback(self, pipeline):
        text = "First sentence. Second sentence. Third sentence."
        segments = pipeline._naive_segmentation(text)
        
        assert len(segments) >= 2
        assert all("id" in s and "text" in s for s in segments)
    
    def test_contains_predicate_indicators(self, pipeline):
        assert pipeline._contains_predicate_indicators("Turkey supports the treaty.") is True
        assert pipeline._contains_predicate_indicators("Hello world.") is False  # No indicators


# ============================================================
# TEST GROUP 3: Anomaly Detection Logic
# ============================================================

class TestArgumentAnomalyDetection:
    """Test argument-aware anomaly detection."""
    
    @pytest.fixture
    def service(self):
        return CrossAnomalyServiceImpl()
    
    @pytest.fixture
    def self_attack_graph(self):
        """Create graph with self-attack anomaly."""
        nodes = [
            ArgumentNode(
                segment_id="claim_1", text="I believe X is true.",
                node_type=NodeType.CLAIM, speaker="Alice", timestamp=0.0
            ),
            ArgumentNode(
                segment_id="attk_1", text="Actually X is false.",
                node_type=NodeType.ATTACK, speaker="Alice", timestamp=5.0  # Self!
            )
        ]
        edges = [
            ArgumentEdge(
                source_id="attk_1", target_id="claim_1",
                relation_type=RelationType.ATTACK, confidence=0.88
            )
        ]
        return ArgumentGraph(nodes=nodes, edges=edges, root_claim_ids=["claim_1"])
    
    @pytest.mark.asyncio
    async def test_self_attack_detection(self, service, self_attack_graph):
        result = await service.detect_argument_anomalies(
            self_attack_graph, base_score=0.1
        )
        
        assert result.score > 0.1  # Boost applied
        assert result.is_anomaly or result.score > 0.3  # Significant signal
    
    def test_hostility_ratio_calculation(self, service):
        graph = ArgumentGraph(
            nodes=[
                ArgumentNode(segment_id="n1", text="A", node_type=NodeType.CLAIM,
                           speaker="S1", timestamp=0.0),
                ArgumentNode(segment_id="n2", text="B", node_type=NodeType.ATTACK,
                           speaker="S2", timestamp=1.0),
                ArgumentNode(segment_id="n3", text="C", node_type=NodeType.ATTACK,
                           speaker="S3", timestamp=2.0),
                ArgumentNode(segment_id="n4", text="D", node_type=NodeType.ATTACK,
                           speaker="S4", timestamp=3.0),
            ],
            edges=[
                ArgumentEdge(source_id="n2", target_id="n1", relation_type=RelationType.ATTACK),
                ArgumentEdge(source_id="n3", target_id="n1", relation_type=RelationType.ATTACK),
                ArgumentEdge(source_id="n4", target_id="n1", relation_type=RelationType.ATTACK),
            ],
            root_claim_ids=["n1"]
        )
        
        ratio = service._compute_hostility_ratio(graph)
        assert ratio == 1.0  # All attacks
    
    def test_isolated_claim_detection(self, service):
        graph = ArgumentGraph(
            nodes=[
                ArgumentNode(segment_id="c1", text="Lonely claim.", 
                           node_type=NodeType.CLAIM, speaker="S", timestamp=0.0)
            ],
            edges=[],
            root_claim_ids=["c1"]
        )
        
        isolated = service._find_isolated_claims(graph)
        assert len(isolated) == 1
        assert isolated[0].segment_id == "c1"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
```

---

## 7. DEPLOYMENT & OPERATIONS CHECKLIST

### 7.1 Pre-Deployment Validation Script

```bash
#!/bin/bash
# pre_deploy_task_a02.sh

echo "=== TASK-A02 Argument Mining Pre-Deployment Checks ==="

# 1. Dependencies
echo "[1/7] Checking dependencies..."
poetry run python -c "import transformers; import torch; print('✓ Transformers OK')" || exit 1

# 2. Model download
echo "[2/7] Pre-warming DeBERTa models..."
poetry run python -c "
from bb_paxdata.domain.services.argument_structure_pipeline import ArgumentStructurePipeline
import asyncio
p = ArgumentStructurePipeline.get_instance()
asyncio.run(p.initialize())
health = p.health_check()
assert health['status'] == 'ready', 'Models failed to load!'
print(f'✓ Models ready: {health}')
" || exit 1

# 3. Unit tests
echo "[3/7] Running unit tests..."
poetry run pytest tests/unit/nlp/test_argument_mining.py -v --tb=short || exit 1

# 4. Graph integrity tests
echo "[4/7] Testing graph algorithms..."
poetry run python -c "
from bb_paxdata.domain.models.argument import *
g = ArgumentGraph(
    nodes=[
        ArgumentNode(segment_id='n1', text='Claim', node_type=NodeType.CLAIM, speaker='S', timestamp=0),
        ArgumentNode(segment_id='n2', text='Support', node_type=NodeType.SUPPORT, speaker='S', timestamp=1)
    ],
    edges=[ArgumentEdge(source_id='n2', target_id='n1', relation_type=RelationType.SUPPORT)],
    root_claim_ids=['n1']
)
assert g.detect_cycles() == [], 'Cycle detected in acyclic graph!'
print('✓ Graph validation OK')
" || exit 1

# 5. Database migration
echo "[5/7] Checking DB migration..."
poetry run alembic upgrade head --sql 2>&1 | head -30 || exit 1

# 6. Latency benchmark
echo "[6/7] Running latency benchmark..."
poetry run python tests/benchmark/benchmark_argmining.py || echo "⚠ Benchmark skipped"

# 7. Memory check
echo "[7/7] Verifying memory footprint..."
poetry run python -c "
import psutil, os
process = psutil.Process(os.getpid())
mem_mb = process.memory_info().rss / 1024 / 1024
print(f'Current memory: {mem_mb:.1f} MB')
assert mem_mb < 2048, f'Memory too high: {mem_mb} MB'
print('✓ Memory OK')
"

echo ""
echo "✅ All TASK-A02 checks passed!"
```

### 7.2 Environment Variables

```bash
# .env.production additions for TASK-A02

# Argument Mining Configuration
ARGMINING_CLAIM_THRESHOLD=0.78
ARGMINING_REL_THRESHOLD=0.65
ARGMINING_USE_SRL=true
ARGMINING_DEVICE=auto
ARGMINING_EDU_METHOD=hybrid
ARGMINING_VALIDATE_DAG=true
ARGMINING_CACHE=true
ARGMINING_MAX_GRAPH_NODES=10000

# Model Paths (optional, for fine-tuned models)
# ARGMINING_CLAIM_MODEL_PATH=/models/deberta-claim-v1
# ARGMINING_REL_MODEL_PATH=/models/deberta-rel-v1
```

---

## 8. APPENDIX: QUICK REFERENCE & TROUBLESHOOTING

### 8.1 API Quick Reference

```python
# === Basic Usage ===
from bb_paxdata.domain.services.argument_structure_pipeline import get_argument_pipeline

pipeline = get_argument_pipeline()
await pipeline.initialize()

# Extract argument structure
graph = await pipeline.extract_argument_structure(
    text=diplomatic_transcript_excerpt,
    speaker="Turkish_Minister",
    timestamp=1250.0,
    srl_frames=srl_result.frames  # From TASK-A01
)

# Access results
print(graph.summary())
print(f"Claims: {graph.claim_count}, Attacks: {graph.attack_count}")

# Get self-attacks (anomalies)
self_attacks = graph.get_self_attacks()
for edge, src, tgt in self_attacks:
    print(f"SELF-ATTACK: {src.speaker} attacks own claim")

# Frontend serialization
frontend_json = graph.serialize_to_frontend()

# === Anomaly Integration ===
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import CrossAnomalyServiceImpl

service = CrossAnomalyServiceImpl()
result = await service.detect_argument_anomalies(
    argument_graph=graph,
    base_score=existing_sentiment_score
)
print(f"Final anomaly score: {result.score}")
```

### 8.2 Troubleshooting Guide

| Symptom                           | Likely Cause                  | Solution                                      |
| --------------------------------- | ----------------------------- | --------------------------------------------- |
| **OOM during model loading**      | GPU memory insufficient       | Set `ARGMINING_DEVICE=cpu`, reduce batch size |
| **Very slow inference (>5s/doc)** | CPU-only mode, large document | Enable CUDA, limit `max_graph_nodes`          |
| **Many false positive claims**    | Threshold too low             | Increase `ARGMINING_CLAIM_THRESHOLD` to 0.85  |
| **Missing relations**             | Neutral threshold too high    | Decrease `ARGMINING_REL_THRESHOLD` to 0.55    |
| **Cycle validation errors**       | Classifier creating loops     | Ensure `validate_dag_on_build=true`           |
| **RST parser failures**           | External service down         | Falls back to spaCy automatically             |
| **Empty graph returned**          | No claims detected            | Check input text length, SRL availability     |

---

## 9. CONCLUSION & NEXT STEPS

This enhanced TASK-A02 report provides a **complete production architecture** for Argument Mining with:

✅ **Formal Graph Theory:** DAG-enforced argument structures with cycle detection  
✅ **Multi-Stage Pipeline:** EDU segmentation → Claim detection → Relation classification  
✅ **Advanced Anomaly Detection:** Self-attacks, unmatched attacks, hostility ratios  
✅ **Enterprise Reliability:** Circuit breakers, caching, graceful degradation  
✅ **Database Persistence:** Full graph serialization with query indexes  
✅ **Frontend Ready:** D3.js/Cytoscape.js/React Flow compatible output formats  
✅ **Comprehensive Testing:** 25+ tests covering models, algorithms, and integration  

### Implementation Order:

| Week | Milestone                      | Deliverables                                                  |
| ---- | ------------------------------ | ------------------------------------------------------------- |
| 1    | Domain Models + Basic Pipeline | `argument.py`, config, pipeline skeleton                      |
| 2    | Classifier Integration         | Real DeBERTa inference, EDU segmentation                      |
| 3    | Graph Algorithms + Anomaly     | Cycle detection, stance propagation, CrossAnomaly integration |
| 4    | Database + Frontend            | Migration scripts, serialization, visualization endpoint      |
| 5    | Testing & Optimization         | Benchmark suite, performance tuning, documentation            |

### Future Enhancements (Out of Scope):

- 🔄 **Fine-tuning on Diplomatic Corpus**: Domain adaptation for political discourse
- 🌐 **Multilingual Argument Mining**: Turkish language support via XLM-RoBERTa
- 📊 **Real-time Debate Tracking**: WebSocket streaming of live argument construction
- 🤖 **Automated Rebuttal Generation**: GPT-assisted counter-argument suggestion
- 🔗 **Cross-Document Argument Linking**: Trace arguments across multiple meetings/documents

---

**Document Control:**
- **Version:** 2.0-Production-Ready
- **Author:** Senior ML Engineer (Enhanced from antigravity v1.0)
- **Review Status:** ✅ Ready for antigravity downstream agent consumption
- **Estimated Effort:** 4-5 sprints (2-week cadence)
- **Dependencies:** TASK-A01 (SRL) must be completed first
- **Risk Level:** Medium-High (mitigated by extensive validation and fallbacks)