import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from bb_paxdata.infrastructure.auth.jwt_auth import create_jwt
from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    FormulaValidationLog,
    ReviewerAssignment,
    Sentence,
)
from bb_paxdata.interfaces.api.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    """Returns authorization headers for an admin reviewer."""
    token = create_jwt("admin@paxdata.local", roles=["admin"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_data(test_db_session):
    """Seeds reviewer assignments, logs, sentences, and queues for endpoints testing."""
    # 1. Reviewer assignment
    assignment = ReviewerAssignment(
        reviewer_id="admin@paxdata.local",
        scope_type="global",
        scope_value="global",
        permission_level="admin",
        is_active=True,
        max_daily_reviews=100,
    )
    test_db_session.add(assignment)

    # 2. Sentences (prev, current, next)
    s_prev = Sentence(
        sent_id="S-1",
        seg_id="SEG-1",
        file_id="FILE-1",
        text="Önceki diplomatik ifade.",
        sent_order=0,
        speaker_name="Speaker A",
        country="Turkiye",
        power_level=8,
    )
    s_curr = Sentence(
        sent_id="S-2",
        seg_id="SEG-1",
        file_id="FILE-1",
        text="İncelenen mevcut diplomatik cümle.",
        sent_order=1,
        speaker_name="Speaker A",
        country="Turkiye",
        power_level=8,
    )
    s_next = Sentence(
        sent_id="S-3",
        seg_id="SEG-1",
        file_id="FILE-1",
        text="Sonraki diplomatik ifade.",
        sent_order=2,
        speaker_name="Speaker A",
        country="Turkiye",
        power_level=8,
    )
    test_db_session.add_all([s_prev, s_curr, s_next])

    # 3. Validation Logs
    log = FormulaValidationLog(
        log_id=1,
        run_id="RUN-1",
        formula_name="risk_score",
        expected_constraint="[0.0, 5.0]",
        actual_value=8.5,
        status="FAIL",
        entity_type="sentence",
        entity_id="S-2",
        log_version=1,
        is_current=True,
    )
    test_db_session.add(log)

    # 4. Review Queue
    queue_item = HumanReviewQueue(
        review_id=1,
        sent_id="S-2",
        sentence_code="CODE-2",
        seg_id="SEG-1",
        file_id="FILE-1",
        speaker_name="Speaker A",
        country="Turkiye",
        trigger_type="HIGH_RISK",
        ai_risk_score=85,
        status="PENDING",
        original_ai_json="{}",
    )
    test_db_session.add(queue_item)

    await test_db_session.commit()


@pytest.mark.asyncio
async def test_get_dashboard_kpis(seed_data, auth_headers):
    """Test retrieving KPI statistics."""
    response = client.get("/api/v1/dashboard/kpis", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_logs"] > 0
    assert data["total_fail"] == 1
    assert data["pending_review"] == 1


@pytest.mark.asyncio
async def test_get_dashboard_distributions(seed_data, auth_headers):
    """Test retrieving dashboard breakdown distributions."""
    # Trends
    r_trends = client.get("/api/v1/dashboard/trends", headers=auth_headers)
    assert r_trends.status_code == 200
    assert len(r_trends.json()) > 0

    # Priorities
    r_pri = client.get("/api/v1/dashboard/priorities", headers=auth_headers)
    assert r_pri.status_code == 200
    assert any(
        item["priority"] == "CRITICAL" and item["count"] == 1 for item in r_pri.json()
    )


@pytest.mark.asyncio
async def test_get_queue_and_context(seed_data, auth_headers):
    """Test retrieving queue list and triplet contexts."""
    # Fail Queue
    r_queue = client.get("/api/v1/queue", headers=auth_headers)
    assert r_queue.status_code == 200
    q_data = r_queue.json()
    assert len(q_data) > 0
    assert q_data[0]["sent_id"] == "S-2"
    assert q_data[0]["formula_name"] == "risk_score"

    # Triplet Context
    r_ctx = client.get("/api/v1/queue/context/S-2", headers=auth_headers)
    assert r_ctx.status_code == 200
    ctx_data = r_ctx.json()
    assert ctx_data["prev"] == "Önceki diplomatik ifade."
    assert ctx_data["current"] == "İncelenen mevcut diplomatik cümle."
    assert ctx_data["next"] == "Sonraki diplomatik ifade."
    assert ctx_data["speaker"]["name"] == "Speaker A"


@pytest.mark.asyncio
async def test_submit_verdict(test_db_session, seed_data, auth_headers):
    """Test submitting atomic verdict and verifying state synchronization."""
    payload = {
        "log_id": 1,
        "verdict": "CONFIRMED_FAIL",
        "note": "Verified AI analysis was accurate.",
        "confidence": "HIGH",
        "reviewer_id": "admin@paxdata.local",
    }
    response = client.post("/api/v1/verdict", json=payload, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "new_log_id" in res_data

    # Check if the queue status synced to REJECTED (confirmed fail)
    q_stmt = select(HumanReviewQueue).where(HumanReviewQueue.sent_id == "S-2")
    q_result = await test_db_session.execute(q_stmt)
    updated_queue = q_result.scalar_one()
    assert updated_queue.status == "REJECTED"


def test_websocket_queue():
    """Verify that a client can connect to the queue WebSocket and exchange messages."""
    with client.websocket_connect("/api/ws/queue") as websocket:
        websocket.send_json({"ping": "hello"})
        data = websocket.receive_json()
        assert data["status"] == "echo"
        assert data["received"] == {"ping": "hello"}


def test_websocket_verdict_broadcast(test_db_session, seed_data, auth_headers):
    """Verify that submitting a verdict broadcasts a queue_updated event to WebSocket clients."""
    with client.websocket_connect("/api/ws/queue") as websocket:
        payload = {
            "log_id": 1,
            "verdict": "CONFIRMED_PASS",
            "note": "Verified pass status.",
            "confidence": "HIGH",
            "reviewer_id": "admin@paxdata.local",
        }
        response = client.post("/api/v1/verdict", json=payload, headers=auth_headers)
        assert response.status_code == 200

        # Read the broadcasted payload from the websocket connection
        broadcast = websocket.receive_json()
        assert broadcast["event"] == "queue_updated"
        assert broadcast["log_id"] == 1
        assert broadcast["verdict"] == "CONFIRMED_PASS"
        assert broadcast["reviewer_id"] == "admin@paxdata.local"


@pytest.mark.asyncio
async def test_get_discourse_network(test_db_session, seed_data, auth_headers):
    """Verify retrieving the discourse network bipartite graph."""
    from bb_paxdata.infrastructure.db.discourse_network_table import (
        DiscourseNetworkEdgeTable,
    )

    edge = DiscourseNetworkEdgeTable(
        session_id="RUN-1",
        actor_id="Turkey",
        concept_id="two_state_solution",
        tf=1.5,
        idf=0.8,
        weight=1.2,
        segment_id="SEG-1",
    )
    test_db_session.add(edge)
    await test_db_session.commit()

    response = client.get("/api/v1/discourse?session_id=RUN-1", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert any(n["id"] == "Turkey" and n["type"] == "actor" for n in data["nodes"])
    assert any(
        n["id"] == "two_state_solution" and n["type"] == "concept"
        for n in data["nodes"]
    )
    assert len(data["edges"]) == 1
    assert data["edges"][0]["source"] == "Turkey"
    assert data["edges"][0]["target"] == "two_state_solution"
    assert data["edges"][0]["weight"] == 1.2


@pytest.mark.asyncio
async def test_get_discourse_sessions(test_db_session, seed_data, auth_headers):
    """Verify retrieving the list of unique discourse session IDs."""
    from bb_paxdata.infrastructure.db.discourse_network_table import (
        DiscourseNetworkEdgeTable,
    )

    edge1 = DiscourseNetworkEdgeTable(
        session_id="RUN-B",
        actor_id="Turkey",
        concept_id="two_state_solution",
        tf=1.5,
        idf=0.8,
        weight=1.2,
        segment_id="SEG-1",
    )
    edge2 = DiscourseNetworkEdgeTable(
        session_id="RUN-A",
        actor_id="Qatar",
        concept_id="ceasefire",
        tf=1.0,
        idf=0.9,
        weight=0.9,
        segment_id="SEG-2",
    )
    test_db_session.add_all([edge1, edge2])
    await test_db_session.commit()

    response = client.get("/api/v1/discourse/sessions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Checks sorting and uniqueness
    assert "RUN-A" in data
    assert "RUN-B" in data
    assert data.index("RUN-A") < data.index("RUN-B")


@pytest.mark.asyncio
async def test_get_dashboard_anomalies(test_db_session, seed_data, auth_headers):
    """Verify retrieving the chronological list of dashboard anomalies."""
    import datetime

    from bb_paxdata.infrastructure.db.models import AIFailAnalysis

    fail = AIFailAnalysis(
        sent_id="S-2",
        check_type="sentiment_contradiction",
        fail_category="contradiction",
        file_id="FILE-1",
        speaker_name="Speaker A",
        country="Turkiye",
        original_sentence="Mevcut cümle.",
        discrepancy_score=0.85,
        processed_at=datetime.datetime.now(datetime.timezone.utc),
    )
    test_db_session.add(fail)
    await test_db_session.commit()

    response = client.get("/api/v1/dashboard/anomalies", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["sent_id"] == "S-2"
    assert data[0]["fail_category"] == "contradiction"
    assert data[0]["discrepancy_score"] == 0.85


@pytest.mark.asyncio
async def test_get_temporal_drift(test_db_session, seed_data, auth_headers):
    """Verify retrieving temporal drift analytics for a speaker."""
    from bb_paxdata.infrastructure.db.dki_table import DKIResultModel
    from bb_paxdata.infrastructure.db.drift_events import DriftEvent
    from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

    s = Sentence(
        sent_id="S-10",
        seg_id="SEG-1",
        file_id="FILE-1",
        text="Örnek cümle.",
        sent_order=3,
        speaker_name="Speaker A",
        country="Turkiye",
    )
    analysis = AISentenceAnalysis(
        sent_id="S-10", sentiment_score=0.45, prompt_version="v1"
    )
    dki = DKIResultModel(
        analysis_id="A-1",
        speaker_id="Speaker A",
        session_id="RUN-1",
        dki_score=0.72,
        velocity=0.15,
        semantic_shift=0.3,
        debate_loading=0.5,
    )
    drift = DriftEvent(
        speaker_id="Speaker A",
        panel_id="FILE-1",
        drift_type="SENTIMENT",
        start_position=0,
        end_position=5,
        severity="MEDIUM",
        confidence=0.85,
        algorithm="CUSUM",
    )
    test_db_session.add_all([s, analysis, dki, drift])
    await test_db_session.commit()

    response = client.get(
        "/api/v1/dashboard/drift?speaker_id=Speaker A", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["selected_speaker"] == "Speaker A"
    assert "garch" in data
    assert "half_life" in data
    assert len(data["dki"]) == 1
    assert data["dki"][0]["dki_score"] == 0.72
    assert len(data["drift_events"]) == 1
    assert data["drift_events"][0]["drift_type"] == "SENTIMENT"


@pytest.mark.asyncio
async def test_get_database_stats(test_db_session, seed_data, auth_headers):
    """Verify retrieving database statistics and table counts."""
    response = client.get("/api/v1/database/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["database_mode"] is not None
    assert "size_bytes" in data
    assert data["status"] == "healthy"
    assert "row_counts" in data
    assert data["row_counts"]["sentences"] == 3
    assert data["row_counts"]["files"] == 0


@pytest.mark.asyncio
async def test_get_calibration_report_and_trend(
    test_db_session, seed_data, auth_headers
):
    """Verify retrieving calibration report and trend metrics."""
    from datetime import datetime, timedelta, timezone

    from bb_paxdata.infrastructure.db.human_review_table import CalibrationReportORM

    now = datetime.now(timezone.utc)
    # Seed 6 reports for trend and latest report retrieval
    reports = []
    for i in range(6):
        report = CalibrationReportORM(
            prompt_version="v3",
            evaluation_period_start=now - timedelta(days=30 * (i + 1)),
            evaluation_period_end=now - timedelta(days=30 * i),
            cohens_kappa_frame=0.72 + 0.01 * i,
            cohens_kappa_risk=0.68,
            ai_human_f1_frame=0.84,
            ai_human_f1_risk=0.79,
            sbi_mae=4.2,
            total_reviews=100,
            total_disagreements=10,
            requires_prompt_update=False,
            requires_weight_update=False,
            alert_message="No alert",
            top_disagreement_patterns=[],
            created_at=now - timedelta(days=30 * i),
        )
        reports.append(report)

    test_db_session.add_all(reports)
    await test_db_session.commit()

    # Test Calibration Report (should get the latest, which is i=0, so cohens_kappa_frame = 0.72)
    response = client.get("/api/v1/dashboard/calibration", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["prompt_version"] == "v3"
    assert data["cohens_kappa_frame"] == 0.72

    # Test Calibration Trend
    response_trend = client.get(
        "/api/v1/dashboard/calibration/trend?months=6", headers=auth_headers
    )
    assert response_trend.status_code == 200
    trend_data = response_trend.json()
    assert isinstance(trend_data, list)
    assert len(trend_data) == 6
    assert trend_data[0]["month"] is not None
    assert trend_data[0]["kappa"] is not None
    assert trend_data[0]["f1"] is not None


@pytest.mark.asyncio
async def test_system_settings_endpoints(test_db_session, seed_data, auth_headers):
    """Verify GET and PUT on /api/v1/settings/system for admin users."""
    # GET — should return defaults when no JSON file exists
    r_get = client.get("/api/v1/settings/system", headers=auth_headers)
    assert r_get.status_code == 200
    data = r_get.json()
    assert "anomaly_soft_log_only" in data
    assert "risk_ai_weight" in data
    assert "formula_tolerance" in data
    assert "risk_threshold" in data

    # PUT — should accept and echo back updated settings
    updated = {**data, "risk_threshold": 80.0, "anomaly_context_window": 7}
    r_put = client.put("/api/v1/settings/system", json=updated, headers=auth_headers)
    assert r_put.status_code == 200
    put_data = r_put.json()
    assert put_data["risk_threshold"] == 80.0
    assert put_data["anomaly_context_window"] == 7


@pytest.mark.asyncio
async def test_settings_permission_denied_for_non_admin(test_db_session, auth_headers):
    """Verify /settings/reviewers and /settings/system require admin permission."""
    from bb_paxdata.infrastructure.auth.jwt_auth import create_jwt

    # Non-admin user token (verdict-level only)
    verdict_token = create_jwt("analyst@paxdata.local", roles=["verdict"])
    verdict_headers = {"Authorization": f"Bearer {verdict_token}"}

    r_reviewers = client.get("/api/v1/settings/reviewers", headers=verdict_headers)
    assert r_reviewers.status_code == 403

    r_system = client.get("/api/v1/settings/system", headers=verdict_headers)
    assert r_system.status_code == 403
