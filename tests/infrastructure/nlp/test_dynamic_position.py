from datetime import datetime, timedelta, timezone

import pytest
from bb_paxdata.domain.models.dki import SpeakerTrajectory
from bb_paxdata.infrastructure.nlp.dynamic_position import PooleRosenthalPositionTracker


@pytest.mark.asyncio
async def test_dynamic_position_velocity():
    tracker = PooleRosenthalPositionTracker()

    now = datetime.now(timezone.utc)
    trajectory = SpeakerTrajectory(
        speaker_id="speaker1",
        positions=[
            {"theta": 0.2, "timestamp": now - timedelta(days=10)},
            {"theta": 0.25, "timestamp": now - timedelta(days=5)},
            {"theta": 0.5, "timestamp": now},
        ],
    )

    result = await tracker.compute_velocity(trajectory)

    assert result.current_velocity > 0
    assert result.session_count == 3
    assert len(result.raw_velocities) == 2
    assert result.calculation_method.startswith("poole_rosenthal_1997")


@pytest.mark.asyncio
async def test_dynamic_position_acceleration():
    tracker = PooleRosenthalPositionTracker()

    now = datetime.now(timezone.utc)
    # Trajectory: [0.2, 0.25, 0.5, 0.48]
    trajectory = SpeakerTrajectory(
        speaker_id="speaker1",
        positions=[
            {"theta": 0.2, "timestamp": now - timedelta(days=15)},
            {"theta": 0.25, "timestamp": now - timedelta(days=10)},
            {"theta": 0.5, "timestamp": now - timedelta(days=5)},
            {"theta": 0.48, "timestamp": now},
        ],
    )

    result = await tracker.compute_velocity(trajectory)

    # Positive then negative acceleration expected
    assert result.current_acceleration < 0  # 0.5 -> 0.48 is a decrease
    assert result.current_velocity != 0
