import json
from unittest.mock import MagicMock, patch

import pytest
from bb_paxdata.application.domain.models.srl import (
    SRLDocumentResult,
    SRLFrame,
    SRLSpan,
)
from bb_paxdata.infrastructure.nlp.cross_anomaly_service_impl import (
    ContradictionPattern,
    CrossAnomalyServiceImpl,
)
from bb_paxdata.infrastructure.nlp.srl_pipeline import (
    CircuitBreakerState,
    LRUCacheWithTTL,
    SRLPipeline,
)
from pydantic import ValidationError

# ============================================================
# TEST GROUP 1: Domain Model Validation
# ============================================================


class TestSRLSpanValidation:
    """Test SRLSpan invariant enforcement."""

    def test_valid_span_creation(self):
        """Valid span should instantiate correctly."""
        span = SRLSpan(text="Turkey", start_char=0, end_char=6)
        assert span.text == "Turkey"
        assert span.char_span == (0, 6)

    def test_reject_inverted_offsets(self):
        """Start > end should raise ValidationError."""
        with pytest.raises(ValidationError, match="Span invariant violated"):
            SRLSpan(text="test", start_char=5, end_char=2)

    def test_reject_length_mismatch(self):
        """Text length != offset range should fail."""
        with pytest.raises(ValidationError, match="Span text length mismatch"):
            SRLSpan(text="Turkey", start_char=0, end_char=10)  # "Turkey" is 6 chars

    def test_whitespace_sanitization(self):
        """Extra whitespace should be normalized."""
        span = SRLSpan(text="  Turkey   ", start_char=2, end_char=8)
        assert span.text == "Turkey"

    def test_empty_text_rejected(self):
        """Empty string should fail validation."""
        with pytest.raises(ValidationError):
            SRLSpan(text="", start_char=0, end_char=0)


class TestSRLFrameValidation:
    """Test SRLFrame business logic."""

    def test_complete_triplet_detection(self):
        """Frame with ARG0+ARG1 should report complete triplet."""
        frame = SRLFrame(
            verb="reject",
            arg0=SRLSpan(text="Turkey", start_char=0, end_char=6),
            arg1=SRLSpan(text="proposal", start_char=16, end_char=24),
        )
        assert frame.has_complete_triplet is True
        assert frame.to_triplet() == ("Turkey", "reject", "proposal")

    def test_incomplete_triplet(self):
        """Missing ARG1 should yield incomplete triplet."""
        frame = SRLFrame(
            verb="reject",
            arg0=SRLSpan(text="Turkey", start_char=0, end_char=6),
            arg1=None,
        )
        assert frame.has_complete_triplet is False
        assert frame.to_triplet() is None

    def test_verb_normalization(self):
        """Verb should be lowercased automatically."""
        frame = SRLFrame(verb="REJECT", arg0=None, arg1=None)
        assert frame.verb == "reject"

    def test_negation_alias(self):
        """is_negated property should mirror argm_neg."""
        frame = SRLFrame(verb="test", argm_neg=True)
        assert frame.is_negated is True

    def test_serialization_for_database(self):
        """to_dict_for_db should produce JSON-serializable dict."""
        frame = SRLFrame(
            verb="support",
            arg0=SRLSpan(text="USA", start_char=0, end_char=3),
            arg1=SRLSpan(text="treaty", start_char=12, end_char=18),
            argm_mod="might",
            argm_neg=False,
            frame_confidence=0.94,
        )

        db_dict = frame.to_dict_for_db()

        assert db_dict["predicate"] == "support"
        assert db_dict["arg0_entity"] == "USA"
        assert db_dict["arg1_entity"] == "treaty"
        assert db_dict["argm_mod"] == "might"
        assert db_dict["confidence"] == 0.94

        # Should be JSON serializable
        json_str = json.dumps(db_dict)
        assert isinstance(json_str, str)


class TestSRLDocumentResultAggregation:
    """Test document-level aggregation features."""

    def test_empty_document(self):
        """Empty frames should yield safe defaults."""
        result = SRLDocumentResult(frames=[])
        assert result.complete_triplets == []
        assert result.unique_predicates == set()
        assert result.frame_density == 0.0

    def test_multiple_frames_aggregation(self):
        """Should aggregate across multiple frames correctly."""
        frames = [
            SRLFrame(
                verb="reject",
                arg0=SRLSpan(text="A", start_char=0, end_char=1),
                arg1=SRLSpan(text="B", start_char=2, end_char=3),
            ),
            SRLFrame(
                verb="support",
                arg0=SRLSpan(text="C", start_char=4, end_char=5),
                arg1=SRLSpan(text="D", start_char=6, end_char=7),
            ),
            SRLFrame(
                verb="reject",
                arg0=SRLSpan(text="E", start_char=8, end_char=9),
                arg1=SRLSpan(text="F", start_char=10, end_char=11),
            ),
        ]

        result = SRLDocumentResult(
            frames=frames,
            total_sentences_processed=3,
            total_frames_extracted=len(frames),
        )

        assert len(result.complete_triplets) == 3
        assert result.unique_predicates == {"reject", "support"}
        assert abs(result.frame_density - 1.0) < 0.01  # 3 frames / 3 sentences

    def test_filter_by_verb(self):
        """get_frames_by_verb should filter case-insensitively."""
        frames = [
            SRLFrame(verb="reject"),
            SRLFrame(verb="support"),
            SRLFrame(verb="Reject"),  # Different casing
        ]
        result = SRLDocumentResult(frames=frames)

        reject_frames = result.get_frames_by_verb("reject")
        assert len(reject_frames) == 2  # Case-insensitive match


# ============================================================
# TEST GROUP 2: Pipeline Infrastructure (Mocked)
# ============================================================


class TestLRUCacheBehavior:
    """Test LRU cache with TTL functionality."""

    def test_put_and_get(self):
        """Basic cache operations."""
        cache = LRUCacheWithTTL(max_size=10, ttl_seconds=60)

        frames = [SRLFrame(verb="test")]
        cache.put("key1", frames)

        retrieved = cache.get("key1")
        assert retrieved is not None
        assert len(retrieved) == 1

    def test_expired_entry_returns_none(self):
        """Expired entries should be evicted on access."""
        cache = LRUCacheWithTTL(max_size=10, ttl_seconds=-1)  # Already expired

        frames = [SRLFrame(verb="test")]
        cache.put("key1", frames)

        assert cache.get("key1") is None
        assert cache.size == 0

    def test_eviction_policy(self):
        """Oldest entries should be evicted when max_size reached."""
        cache = LRUCacheWithTTL(max_size=2, ttl_seconds=3600)

        cache.put("key1", [SRLFrame(verb="a")])
        cache.put("key2", [SRLFrame(verb="b")])
        cache.put("key3", [SRLFrame(verb="c")])  # Should evict key1

        assert cache.size == 2
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None


class TestCircuitBreakerState:
    """Test circuit breaker state machine."""

    def test_initially_closed(self):
        """New circuit breaker should be CLOSED."""
        cb = CircuitBreakerState()
        assert cb.state == "CLOSED"
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        """Should open after too many failures."""
        cb = CircuitBreakerState()

        # Simulate failures (threshold = 20% of 100 = 20 failures)
        for _ in range(25):
            cb.record_failure()

        assert cb.state == "OPEN"
        assert cb.allow_request() is False

    def test_recovers_on_success(self):
        """Should close again after successful requests in HALF_OPEN."""
        cb = CircuitBreakerState()
        cb.state = "OPEN"
        cb.last_failure_time = 0  # Force immediate HALF_OPEN

        assert cb.allow_request() is True  # Transitions to HALF_OPEN
        assert cb.state == "HALF_OPEN"

        cb.record_success()
        assert cb.state == "CLOSED"


class TestSRLPipelineIntegration:
    """Test pipeline with mocked transformer (no real model loading)."""

    @patch("bb_paxdata.infrastructure.nlp.srl_pipeline.pipeline")
    def test_successful_extraction(self, mock_pipeline_fn):
        """Should parse mock predictions into SRL frames."""
        # Setup mock pipeline response
        mock_pipe = MagicMock()
        mock_pipe.return_value = [
            {
                "entity_group": "V",
                "word": "rejected",
                "start": 7,
                "end": 15,
                "score": 0.98,
            },
            {
                "entity_group": "ARG0",
                "word": "Turkey",
                "start": 0,
                "end": 6,
                "score": 0.95,
            },
            {
                "entity_group": "ARG1",
                "word": "proposal",
                "start": 16,
                "end": 24,
                "score": 0.92,
            },
        ]
        mock_pipeline_fn.return_value = mock_pipe

        # Bypass singleton for testing
        pipeline = SRLPipeline.__new__(SRLPipeline)
        pipeline._initialized = False
        pipeline.__init__()
        pipeline._pipeline = mock_pipe
        pipeline._model_loaded = True

        result = pipeline.extract_from_text(
            "Turkey rejected proposal.", use_cache=False
        )

        assert len(result.frames) >= 1
        assert result.frames[0].verb == "rejected"
        assert result.frames[0].actor_text == "Turkey"
        assert result.frames[0].target_text == "proposal"

    @patch("bb_paxdata.infrastructure.nlp.srl_pipeline.pipeline")
    def test_empty_input_validation(self, mock_pipeline_fn):
        """Empty text should raise ValueError before model call."""
        pipeline = SRLPipeline.__new__(SRLPipeline)
        pipeline._initialized = False
        pipeline.__init__()

        with pytest.raises(ValueError, match="cannot be empty"):
            pipeline.extract_from_text("")

        with pytest.raises(ValueError, match="cannot be empty"):
            pipeline.extract_from_text("   ")

    def test_health_check_returns_structure(self):
        """Health check should return comprehensive status dict."""
        pipeline = SRLPipeline.__new__(SRLPipeline)
        pipeline._initialized = False
        pipeline.__init__()

        health = pipeline.health_check()
        assert "status" in health
        assert "model_loaded" in health
        assert "circuit_breaker_state" in health
        assert "cache_stats" in health
        assert "performance_metrics" in health


# ============================================================
# TEST GROUP 3: Contradiction Detection Logic
# ============================================================


class TestContradictionDetection:
    """Test SRL-aware contradiction detection algorithms."""

    @pytest.fixture
    def service(self):
        """Create CrossAnomalyService instance."""
        return CrossAnomalyServiceImpl()

    def test_exact_negation_mismatch(self, service):
        """Same verb with different negation should trigger contradiction."""
        frame_pos = SRLFrame(
            verb="support",
            arg0=SRLSpan(text="Turkey", start_char=0, end_char=6),
            arg1=SRLSpan(text="treaty", start_char=15, end_char=21),
            argm_neg=False,
        )
        frame_neg = SRLFrame(
            verb="support",
            arg0=SRLSpan(text="Turkey", start_char=30, end_char=36),
            arg1=SRLSpan(text="treaty", start_char=45, end_char=51),
            argm_neg=True,
        )

        result = service._detect_frame_contradiction(
            frame_a=frame_pos,
            frame_b=frame_neg,
            sent_idx_a=0,
            sent_idx_b=1,
            polarity_a=0.8,
            polarity_b=-0.3,
        )

        assert result is not None
        assert result.pattern == ContradictionPattern.EXACT_NEGATION_MISMATCH
        assert result.confidence > 0

    def test_sentiment_polarity_flip(self, service):
        """Opposite sentiments on same triplet should trigger."""
        frame_a = SRLFrame(
            verb="criticize",
            arg0=SRLSpan(text="CountryA", start_char=0, end_char=8),
            arg1=SRLSpan(text="CountryB", start_char=17, end_char=25),
        )
        frame_b = SRLFrame(
            verb="praise",
            arg0=SRLSpan(text="CountryA", start_char=35, end_char=43),
            arg1=SRLSpan(text="CountryB", start_char=52, end_char=60),
        )

        result = service._detect_frame_contradiction(
            frame_a=frame_a,
            frame_b=frame_b,
            sent_idx_a=0,
            sent_idx_b=1,
            polarity_a=0.9,  # Positive
            polarity_b=-0.8,  # Negative
        )

        assert result is not None
        assert result.pattern == ContradictionPattern.SENTIMENT_POLARITY_FLIP

    def test_no_contradiction_different_targets(self, service):
        """Different ARG1 should not trigger contradiction."""
        frame_a = SRLFrame(
            verb="support",
            arg0=SRLSpan(text="X", start_char=0, end_char=1),
            arg1=SRLSpan(text="TargetA", start_char=3, end_char=10),
        )
        frame_b = SRLFrame(
            verb="support",
            arg0=SRLSpan(text="X", start_char=14, end_char=15),
            arg1=SRLSpan(text="TargetB", start_char=17, end_char=24),  # Different!
        )

        result = service._detect_frame_contradiction(
            frame_a=frame_a,
            frame_b=frame_b,
            sent_idx_a=0,
            sent_idx_b=1,
            polarity_a=0.5,
            polarity_b=0.5,
        )

        assert result is None  # No contradiction

    def test_modal_conflict_detection(self, service):
        """Might vs should should trigger modal conflict."""
        frame_low = SRLFrame(
            verb="sign",
            arg0=SRLSpan(text="A", start_char=0, end_char=1),
            arg1=SRLSpan(text="treaty", start_char=3, end_char=9),
            argm_mod="might",
        )
        frame_high = SRLFrame(
            verb="sign",
            arg0=SRLSpan(text="A", start_char=13, end_char=14),
            arg1=SRLSpan(text="treaty", start_char=16, end_char=22),
            argm_mod="must",
        )

        conflict = service._check_modal_conflict(frame_low, frame_high)
        assert conflict is not None
        assert "might" in conflict and "must" in conflict
