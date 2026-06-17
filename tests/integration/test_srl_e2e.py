from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.application.domain.models.segment import Segment
from bb_paxdata.application.domain.models.sentence import Sentence
from bb_paxdata.application.domain.models.srl import ExtractionStatus
from bb_paxdata.application.domain.services.spacy_pipeline import SpacyPipeline
from bb_paxdata.application.pipeline.stages.assemble_network import NetworkAssemblyStage
from bb_paxdata.application.pipeline.stages.finalize_network import NetworkFinalizeStage
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

    # Verify network_repo.save_flow and bilateral_repo.save_dyadic were called
    mock_network_repo.save_flow.assert_called_once_with(
        mock_session, enriched_analysis.discourse_flow
    )
    mock_bilateral_repo.save_dyadic.assert_called_once_with(
        mock_session, mock_maoz_metric
    )
