import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.models.sentence import Sentence
from bb_paxdata.application.domain.models.srl import ExtractionStatus, SRLFrame, SRLSpan
from bb_paxdata.application.domain.services.spacy_pipeline import SpacyPipeline
from bb_paxdata.application.pipeline.stages.assemble_network import NetworkAssemblyStage
from bb_paxdata.application.pipeline.stages.finalize_network import NetworkFinalizeStage
from bb_paxdata.infrastructure.db.models import DiscourseNetworkEdge
from bb_paxdata.infrastructure.nlp.fischer_dna_service import FischerDNAService
from bb_paxdata.infrastructure.nlp.maoz_dyadic_service import MaozDyadicService
from bb_paxdata.infrastructure.nlp.srl_pipeline import SRLPipeline
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@patch("bb_paxdata.infrastructure.nlp.srl_pipeline.pipeline")
async def test_srl_pipeline_e2e_flow(mock_pipeline_fn):
    """
    E2E integration test:
    1. Parse text using SpaCy + SRL (mocked model pipeline).
    2. Build analysis object with sentences containing SRL frames.
    3. Run NetworkAssemblyStage to aggregate triplets and enrich BilateralSentiment.
    4. Run NetworkFinalizeStage to verify DB edge persistence.
    """
    # -------------------------------------------------------------
    # 1. Mocking HuggingFace Transformers pipeline output
    # -------------------------------------------------------------
    mock_pipe = MagicMock()
    mock_pipe.return_value = [
        # Sentence 1: "Turkey strongly rejected proposal."
        # Word spans: "Turkey" (0-6), "rejected" (16-24), "proposal" (25-33)
        {
            "entity_group": "V",
            "word": "rejected",
            "start": 16,
            "end": 24,
            "score": 0.99,
        },
        {"entity_group": "ARG0", "word": "Turkey", "start": 0, "end": 6, "score": 0.95},
        {
            "entity_group": "ARG1",
            "word": "proposal",
            "start": 25,
            "end": 33,
            "score": 0.92,
        },
    ]
    mock_pipeline_fn.return_value = mock_pipe

    # Reset/Pre-warm SRL pipeline singleton
    srl_pipeline = SRLPipeline.get_instance()
    srl_pipeline._pipeline = mock_pipe
    srl_pipeline._model_loaded = True
    srl_pipeline.clear_cache()

    # -------------------------------------------------------------
    # 2. SpaCy processing + SRL extraction
    # -------------------------------------------------------------
    sample_text = "Turkey strongly rejected proposal."
    # Using process_text helper
    doc = SpacyPipeline.process_text(sample_text, lang="en")
    srl_result = SpacyPipeline.extract_semantic_roles_enhanced(doc)

    assert len(srl_result.frames) == 1
    frame = srl_result.frames[0]
    assert frame.verb == "rejected"
    assert frame.actor_text == "Turkey"
    assert frame.target_text == "proposal"
    assert frame.has_complete_triplet is True

    # -------------------------------------------------------------
    # 3. Setup Domain Models (Segment, Sentence, Analysis)
    # -------------------------------------------------------------
    # Build sentence with the extracted SRL frames
    sentence = Sentence(
        id="sent-01",
        text=sample_text,
        start_char=0,
        end_char=len(sample_text),
        srl_frames=[frame],
        srl_extraction_status=ExtractionStatus.COMPLETED,
    )

    segment = Segment(
        id="seg-01",
        primary_speaker_id="Turkey",
        sentences=[sentence],
        tokens=["Turkey", "strongly", "rejected", "the", "proposal", "."],
        key_concepts=["proposal"],
    )

    # Initial bilateral metric
    bilateral = BilateralSentiment(
        panel_id="analysis-01",
        from_country="Turkey",
        to_country="proposal",  # In this simplified case, proposal is target
        avg_sentiment=-0.8,
        total_mentions=1,
    )

    analysis = Analysis(
        id="analysis-01", segments=[segment], bilateral_metrics=[bilateral]
    )

    # -------------------------------------------------------------
    # 4. Network Assembly Stage
    # -------------------------------------------------------------
    # Mock dependency services for assembly stage
    mock_fischer = MagicMock(spec=FischerDNAService)
    mock_fischer.build_network.return_value = MagicMock(
        actor_ids=["Turkey", "proposal"], edge_count=1
    )

    mock_maoz = MagicMock(spec=MaozDyadicService)
    mock_maoz_metric = MagicMock()
    mock_maoz_metric.actor_a_id = "Turkey"
    mock_maoz_metric.actor_b_id = "proposal"
    mock_maoz_metric.diplomatic_distance = 0.5
    mock_maoz_metric.affinity_score = -0.4
    mock_maoz.calculate_all_pairs.return_value = [mock_maoz_metric]

    assembly_stage = NetworkAssemblyStage(
        fischer_service=mock_fischer, maoz_service=mock_maoz
    )

    enriched_analysis = await assembly_stage.process(analysis)

    # Verify SRL fields were correctly aggregated and attached to BilateralSentiment
    assert len(enriched_analysis.bilateral_metrics) == 1
    enriched_sentiment = enriched_analysis.bilateral_metrics[0]

    assert enriched_sentiment.srl_predicate == "rejected"
    assert enriched_sentiment.srl_arg0_entity == "Turkey"
    assert enriched_sentiment.srl_arg1_entity == "proposal"
    assert enriched_sentiment.srl_is_negated is False
    assert enriched_sentiment.srl_confidence == 0.99

    # -------------------------------------------------------------
    # 5. Network Finalization (DB Persistence) Stage
    # -------------------------------------------------------------
    mock_network_repo = MagicMock()
    mock_network_repo.save_flow = AsyncMock()
    mock_bilateral_repo = MagicMock()
    mock_bilateral_repo.save_dyadic = AsyncMock()

    finalize_stage = NetworkFinalizeStage(
        network_repo=mock_network_repo, bilateral_repo=mock_bilateral_repo
    )

    # Setup mock DB session
    mock_session = MagicMock(spec=AsyncSession)

    finalized_analysis = await finalize_stage.process(mock_session, enriched_analysis)
    assert finalized_analysis is not None

    # Verify session.add was called with a DiscourseNetworkEdge containing the correct columns
    assert mock_session.add.call_count == 1
    db_edge = mock_session.add.call_args[0][0]

    assert isinstance(db_edge, DiscourseNetworkEdge)
    assert db_edge.from_country == "Turkey"
    assert db_edge.to_country == "proposal"
    assert db_edge.predicate == "rejected"
    assert db_edge.arg0_entity == "Turkey"
    assert db_edge.arg1_entity == "proposal"
    assert db_edge.is_negated is False
    assert db_edge.srl_confidence == 0.99

    # Verify frame JSON content
    srl_frame_json = db_edge.srl_frame_json
    assert srl_frame_json is not None
    frame_json = json.loads(srl_frame_json)
    assert frame_json["predicate"] == "rejected"
    assert frame_json["arg0"] == "Turkey"
    assert frame_json["arg1"] == "proposal"
    assert frame_json["confidence"] == 0.99


def test_database_model_round_trip():
    """
    Test conversion logic in DiscourseNetworkEdge:
    Domain (SRLFrame) -> DB Model -> Domain (Metadata / Custom Fields).
    """
    frame = SRLFrame(
        verb="support",
        arg0=SRLSpan(text="USA", start_char=0, end_char=3),
        arg1=SRLSpan(text="treaty", start_char=10, end_char=16),
        argm_neg=False,
        argm_mod="should",
        frame_confidence=0.88,
    )

    # 1. Convert from Domain to DB
    from bb_paxdata.application.domain.models.metadata import Metadata

    metadata_mock = Metadata(
        id="discourse_edge:101",
        entity_id="101",
        entity_type="discourse_network_edge",
        title="USA → treaty: support",
        description="Bilateral edge",
        custom_fields={
            "from_country": "USA",
            "to_country": "treaty",
            "weight": 1.0,
            "edge_type": "supportive",
            "predicate": "support",
            "arg0_entity": "USA",
            "arg1_entity": "treaty",
            "is_negated": False,
            "srl_confidence": 0.88,
            "srl_frame": frame.to_dict_for_db(),
        },
    )

    db_edge = DiscourseNetworkEdge.from_domain(metadata_mock)

    assert db_edge.from_country == "USA"
    assert db_edge.to_country == "treaty"
    assert db_edge.predicate == "support"
    assert db_edge.arg0_entity == "USA"
    assert db_edge.arg1_entity == "treaty"
    assert db_edge.is_negated is False
    assert db_edge.srl_confidence == 0.88
    srl_frame_json = db_edge.srl_frame_json
    assert srl_frame_json is not None

    frame_json = json.loads(srl_frame_json)
    assert frame_json["predicate"] == "support"
    assert frame_json["arg0_entity"] == "USA"
    assert frame_json["arg1_entity"] == "treaty"
    assert frame_json["argm_mod"] == "should"

    # 2. Convert from DB back to Domain
    db_edge.edge_id = 101  # Mock generated primary key
    domain_metadata = db_edge.to_domain()

    assert domain_metadata.id == "discourse_edge:101"
    cf = domain_metadata.custom_fields
    assert cf["from_country"] == "USA"
    assert cf["to_country"] == "treaty"
    assert cf["predicate"] == "support"
    assert cf["arg0_entity"] == "USA"
    assert cf["arg1_entity"] == "treaty"
    assert cf["is_negated"] is False
    assert cf["srl_confidence"] == 0.88
    assert cf["srl_frame"]["predicate"] == "support"
    assert cf["srl_frame"]["argm_mod"] == "should"
