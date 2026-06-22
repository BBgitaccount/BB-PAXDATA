from datetime import datetime

import pytest
from pydantic import ValidationError

from bb_paxdata.application.domain.enums import (
    AnomalySeverity,
    AnomalyType,
)
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.anomaly import (
    Anomaly,
    ContradictionResult,
)
from bb_paxdata.application.domain.models.metadata import Metadata
from bb_paxdata.application.domain.models.validation_result import (
    ValidationResult,
)


def test_metadata_json_validation():
    # Valid metadata
    meta = Metadata(
        id="meta-1",
        entity_id="entity-1",
        entity_type="segment",
        processing_parameters={"param1": "value1", "param2": 123, "param3": True},
        custom_fields={"custom1": [1, 2, 3], "custom2": {"nested": "value"}},
    )
    assert meta.id == "meta-1"

    # Invalid custom_fields (non-string dict keys)
    with pytest.raises(ValidationError) as exc_info:
        Metadata(
            id="meta-2",
            entity_id="entity-1",
            entity_type="segment",
            custom_fields={123: "value"},  # type: ignore  # Integer key
        )
    assert "custom_fields" in str(exc_info.value)

    # Invalid processing_parameters (non-JSON type: datetime)
    with pytest.raises(ValidationError) as exc_info:
        Metadata(
            id="meta-3",
            entity_id="entity-1",
            entity_type="segment",
            processing_parameters={"date": datetime.now()},
        )
    assert "Invalid processing_parameters" in str(exc_info.value)


def test_anomaly_json_validation():
    # Valid anomaly
    anomaly = Anomaly(
        id="anom-1",
        anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
        severity=AnomalySeverity.HIGH,
        confidence_score=0.8,
        metadata={"info": "valid"},
    )
    assert anomaly.id == "anom-1"

    # Invalid metadata (non-JSON type: function)
    with pytest.raises(ValidationError) as exc_info:
        Anomaly(
            id="anom-2",
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            severity=AnomalySeverity.HIGH,
            confidence_score=0.8,
            metadata={"func": lambda: None},
        )
    assert "Invalid metadata" in str(exc_info.value)


def test_contradiction_result_json_validation():
    # Valid
    res = ContradictionResult(
        score=0.9,
        threshold=0.5,
        is_anomaly=True,
        anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
        n_sentences=3,
        m1=0.1,
        m2=0.2,
        theta=0.3,
        window=0.4,
        metadata={"info": "valid"},
    )
    assert res.score == 0.9

    # Invalid
    with pytest.raises(ValidationError) as exc_info:
        ContradictionResult(
            score=0.9,
            threshold=0.5,
            is_anomaly=True,
            anomaly_type=AnomalyType.SENTIMENT_RISK_DIVERGENCE,
            n_sentences=3,
            m1=0.1,
            m2=0.2,
            theta=0.3,
            window=0.4,
            metadata={"func": lambda: None},
        )
    assert "Invalid metadata" in str(exc_info.value)


def test_validation_result_json_validation():
    # Valid
    res = ValidationResult(
        id="val-1",
        entity_id="entity-1",
        entity_type="sentence",
        overall_status="passed",
        total_checks=1,
        passed_checks=1,
        failed_checks=0,
        validation_parameters={"thresh": 0.5},
        debug_info={"debug": [1, 2]},
        metadata={"meta": "valid"},
    )
    assert res.id == "val-1"

    # Invalid debug_info
    with pytest.raises(ValidationError) as exc_info:
        ValidationResult(
            id="val-2",
            entity_id="entity-1",
            entity_type="sentence",
            overall_status="passed",
            total_checks=1,
            passed_checks=1,
            failed_checks=0,
            debug_info={"date": datetime.now()},
        )
    assert "Invalid debug_info" in str(exc_info.value)


def test_analysis_json_validation():
    # Valid
    analysis = Analysis(
        source_text="test text",
        entities=[{"text": "Turkey", "label": "GPE"}],
    )
    assert analysis.source_text == "test text"

    # Invalid entities
    with pytest.raises(ValidationError) as exc_info:
        Analysis(
            source_text="test text",
            entities=[{"text": "Turkey", "func": lambda: None}],
        )
    assert "Invalid entities" in str(exc_info.value)
