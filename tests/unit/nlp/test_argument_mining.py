"""
Comprehensive Argument Mining Test Suite
"""

import pytest
from pydantic import ValidationError

from bb_paxdata.application.domain.models.argument import (
    ArgumentEdge,
    ArgumentGraph,
    ArgumentNode,
    ArgumentStance,
    NodeType,
    RelationType,
)
from bb_paxdata.application.domain.services.argument_structure_pipeline import (
    ArgumentStructurePipeline,
)
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import (
    CrossAnomalyServiceImpl,
)

# ============================================================
# TEST GROUP 1: Domain Model Validation
# ============================================================


class TestArgumentNodeValidation:
    def test_valid_node_creation(self):
        node = ArgumentNode(
            segment_id="seg_001",
            text="Turkey maintains its rights under international law.",
            node_type=NodeType.CLAIM,
            speaker="Turkish_Delegate",
            timestamp=120.5,
            confidence=0.94,
        )
        assert node.segment_id == "seg_001"
        assert node.node_type == NodeType.CLAIM
        assert node.stance == ArgumentStance.NEUTRAL

    def test_text_normalization(self):
        node = ArgumentNode(
            segment_id="seg_002",
            text="  Multiple   spaces   here  ",
            node_type=NodeType.SUPPORT,
            speaker="Test_Speaker",
            timestamp=0.0,
        )
        assert node.text == "Multiple spaces here"

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            ArgumentNode(
                segment_id="seg_003",
                text="   ",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=0.0,
            )

    def test_negative_timestamp_rejected(self):
        with pytest.raises(ValidationError):
            ArgumentNode(
                segment_id="seg_004",
                text="Valid text",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=-1.0,
            )

    def test_confidence_range_validation(self):
        with pytest.raises(ValidationError):
            ArgumentNode(
                segment_id="seg_005",
                text="Test",
                node_type=NodeType.CLAIM,
                speaker="X",
                timestamp=0.0,
                confidence=1.5,
            )

    def test_text_hash_deterministic(self):
        node1 = ArgumentNode(
            segment_id="seg_006",
            text="Hello World",
            node_type=NodeType.CLAIM,
            speaker="A",
            timestamp=0.0,
        )
        node2 = ArgumentNode(
            segment_id="seg_007",
            text="Hello World",
            node_type=NodeType.SUPPORT,
            speaker="B",
            timestamp=0.0,
        )
        assert node1.text_hash == node2.text_hash

    def test_truncate_display_text(self):
        long_text = "A" * 200
        node = ArgumentNode(
            segment_id="seg_008",
            text=long_text,
            node_type=NodeType.CLAIM,
            speaker="X",
            timestamp=0.0,
        )
        truncated = node.truncate_display_text(max_length=50)
        assert len(truncated) <= 53
        assert truncated.endswith("...")


class TestArgumentEdgeValidation:
    def test_valid_edge_creation(self):
        edge = ArgumentEdge(
            source_id="seg_001",
            target_id="seg_002",
            relation_type=RelationType.SUPPORT,
            confidence=0.89,
        )
        assert edge.is_support_relation is True
        assert edge.is_attack_relation is False

    def test_self_loop_rejected(self):
        with pytest.raises(ValidationError, match="Self-loops"):
            ArgumentEdge(
                source_id="seg_001",
                target_id="seg_001",
                relation_type=RelationType.ATTACK,
            )

    def test_attack_relation_detection(self):
        edge = ArgumentEdge(
            source_id="a", target_id="b", relation_type=RelationType.ATTACK
        )
        assert edge.is_attack_relation is True

        edge2 = ArgumentEdge(
            source_id="a", target_id="b", relation_type=RelationType.CONTRADICTION
        )
        assert edge2.is_attack_relation is True

    def test_reverse_edge(self):
        edge = ArgumentEdge(
            source_id="src",
            target_id="tgt",
            relation_type=RelationType.SUPPORT,
            confidence=0.9,
        )
        reversed_edge = edge.reverse()
        assert reversed_edge.source_id == "tgt"
        assert reversed_edge.target_id == "src"


class TestArgumentGraphValidation:
    def _create_sample_graph(self) -> ArgumentGraph:
        nodes = [
            ArgumentNode(
                segment_id="claim_1",
                text="Main thesis statement here.",
                node_type=NodeType.CLAIM,
                speaker="Speaker_A",
                timestamp=0.0,
                confidence=0.95,
            ),
            ArgumentNode(
                segment_id="supp_1",
                text="Supporting evidence for the thesis.",
                node_type=NodeType.SUPPORT,
                speaker="Speaker_A",
                timestamp=5.0,
                confidence=0.88,
            ),
            ArgumentNode(
                segment_id="attk_1",
                text="Counter-argument against the thesis.",
                node_type=NodeType.ATTACK,
                speaker="Speaker_B",
                timestamp=10.0,
                confidence=0.91,
            ),
        ]
        edges = [
            ArgumentEdge(
                source_id="claim_1",
                target_id="supp_1",
                relation_type=RelationType.SUPPORT,
                confidence=0.85,
            ),
            ArgumentEdge(
                source_id="claim_1",
                target_id="attk_1",
                relation_type=RelationType.ATTACK,
                confidence=0.90,
            ),
        ]
        return ArgumentGraph(
            nodes=nodes,
            edges=edges,
            root_claim_ids=["claim_1"],
            document_id="test_doc_001",
        ).validate_graph()

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
            ArgumentNode(
                segment_id="n1",
                text="Text",
                node_type=NodeType.CLAIM,
                speaker="S",
                timestamp=0.0,
            )
        ]
        edges = [
            ArgumentEdge(
                source_id="n1",
                target_id="NONEXISTENT",
                relation_type=RelationType.SUPPORT,
            )
        ]
        with pytest.raises(ValueError, match="non-existent"):
            ArgumentGraph(
                nodes=nodes, edges=edges, root_claim_ids=["n1"]
            ).validate_graph()

    def test_invalid_root_claim_raises_error(self):
        nodes = [
            ArgumentNode(
                segment_id="n1",
                text="Text",
                node_type=NodeType.CLAIM,
                speaker="S",
                timestamp=0.0,
            )
        ]
        with pytest.raises(ValueError, match="Root claim"):
            ArgumentGraph(
                nodes=nodes, edges=[], root_claim_ids=["NONEXISTENT_ROOT"]
            ).validate_graph()

    def test_cycle_detection(self):
        nodes = [
            ArgumentNode(
                segment_id="a",
                text="A",
                node_type=NodeType.CLAIM,
                speaker="S",
                timestamp=0.0,
            ),
            ArgumentNode(
                segment_id="b",
                text="B",
                node_type=NodeType.SUPPORT,
                speaker="S",
                timestamp=1.0,
            ),
            ArgumentNode(
                segment_id="c",
                text="C",
                node_type=NodeType.ATTACK,
                speaker="S",
                timestamp=2.0,
            ),
        ]
        edges = [
            ArgumentEdge(
                source_id="a", target_id="b", relation_type=RelationType.SUPPORT
            ),
            ArgumentEdge(
                source_id="b", target_id="c", relation_type=RelationType.ATTACK
            ),
            ArgumentEdge(
                source_id="c", target_id="a", relation_type=RelationType.REBUTTAL
            ),
        ]
        with pytest.raises(ValueError, match="cycle"):
            ArgumentGraph(
                nodes=nodes, edges=edges, root_claim_ids=["a"]
            ).validate_graph()

    def test_get_self_attacks(self):
        graph = self._create_sample_graph()
        self_attack_node = ArgumentNode(
            segment_id="self_attk",
            text="I now disagree with my earlier position.",
            node_type=NodeType.ATTACK,
            speaker="Speaker_A",
            timestamp=15.0,
        )
        graph.add_node(self_attack_node)
        graph.add_edge(
            ArgumentEdge(
                source_id="self_attk",
                target_id="claim_1",
                relation_type=RelationType.ATTACK,
                confidence=0.85,
            )
        )
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
        assert claim.stance == ArgumentStance.PRO
        assert supp.stance == ArgumentStance.PRO
        assert attk.stance == ArgumentStance.CON

    def test_serialize_to_frontend(self):
        graph = self._create_sample_graph()
        frontend_data = graph.serialize_to_frontend()
        assert "id" in frontend_data
        assert "text" in frontend_data
        assert "children" in frontend_data
        assert frontend_data["type"] == "CLAIM"

    def test_remove_weakest_cycle_edge(self):
        nodes = [
            ArgumentNode(
                segment_id="a",
                text="A",
                node_type=NodeType.CLAIM,
                speaker="S",
                timestamp=0.0,
            ),
            ArgumentNode(
                segment_id="b",
                text="B",
                node_type=NodeType.SUPPORT,
                speaker="S",
                timestamp=1.0,
            ),
        ]
        edges = [
            ArgumentEdge(
                source_id="a",
                target_id="b",
                relation_type=RelationType.SUPPORT,
                confidence=0.9,
            ),
            ArgumentEdge(
                source_id="b",
                target_id="a",
                relation_type=RelationType.ATTACK,
                confidence=0.3,
            ),
        ]
        graph = ArgumentGraph.create_with_cycles_allowed(
            nodes=nodes, edges=edges, root_claim_ids=["a"]
        )
        assert len(graph.detect_cycles()) > 0
        removed = graph.remove_weakest_cycle_edge()
        assert removed is not None
        assert removed.confidence == 0.3
        assert len(graph.detect_cycles()) == 0


# ============================================================
# TEST GROUP 2: Pipeline Logic (Mocked)
# ============================================================


class TestArgumentPipelineIntegration:
    @pytest.fixture
    def pipeline(self):
        p = ArgumentStructurePipeline.__new__(ArgumentStructurePipeline)
        p._initialized = False
        p.__init__()
        p._models_loaded = True
        return p

    def test_health_check(self, pipeline):
        health = pipeline.health_check()
        assert "status" in health
        assert "metrics" in health
        assert "cache" in health

    @pytest.mark.asyncio
    async def test_empty_input_rejection(self, pipeline):
        with pytest.raises(ValueError, match="cannot be empty"):
            await pipeline.extract_argument_structure("", "Speaker")

    def test_naive_segmentation_fallback(self, pipeline):
        text = "First sentence. Second sentence. Third sentence."
        segments = pipeline._naive_segmentation(text)
        assert len(segments) >= 2
        assert all("id" in s and "text" in s for s in segments)


# ============================================================
# TEST GROUP 3: Anomaly Detection Logic
# ============================================================


class TestArgumentAnomalyDetection:
    @pytest.fixture
    def service(self):
        return CrossAnomalyServiceImpl()

    @pytest.fixture
    def self_attack_graph(self):
        nodes = [
            ArgumentNode(
                segment_id="claim_1",
                text="I believe X is true.",
                node_type=NodeType.CLAIM,
                speaker="Alice",
                timestamp=0.0,
            ),
            ArgumentNode(
                segment_id="attk_1",
                text="Actually X is false.",
                node_type=NodeType.ATTACK,
                speaker="Alice",
                timestamp=5.0,
            ),
        ]
        edges = [
            ArgumentEdge(
                source_id="attk_1",
                target_id="claim_1",
                relation_type=RelationType.ATTACK,
                confidence=0.88,
            )
        ]
        return ArgumentGraph(
            nodes=nodes, edges=edges, root_claim_ids=["claim_1"]
        ).validate_graph()

    @pytest.mark.asyncio
    async def test_self_attack_detection(self, service, self_attack_graph):
        result = await service.detect_argument_anomalies(
            self_attack_graph, base_score=0.1
        )
        assert result.score > 0.1
        assert result.score > 0.3

    def test_hostility_ratio_calculation(self, service):
        graph = ArgumentGraph(
            nodes=[
                ArgumentNode(
                    segment_id="n1",
                    text="A",
                    node_type=NodeType.CLAIM,
                    speaker="S1",
                    timestamp=0.0,
                ),
                ArgumentNode(
                    segment_id="n2",
                    text="B",
                    node_type=NodeType.ATTACK,
                    speaker="S2",
                    timestamp=1.0,
                ),
            ],
            edges=[
                ArgumentEdge(
                    source_id="n2", target_id="n1", relation_type=RelationType.ATTACK
                ),
            ],
            root_claim_ids=["n1"],
        ).validate_graph()
        ratio = service._compute_hostility_ratio(graph)
        assert ratio == 1.0
