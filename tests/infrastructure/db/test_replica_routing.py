# tests/infrastructure/db/test_replica_routing.py
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

from bb_paxdata.infrastructure.db.models import OutboxEventORM
from bb_paxdata.infrastructure.db.session import RoutingSession
from sqlalchemy.sql import insert, select


def test_routing_session_get_bind_select_outside_transaction():
    mock_primary_sync = MagicMock()
    mock_replica_sync = MagicMock()

    mock_engine = MagicMock()
    mock_engine.sync_engine = mock_primary_sync

    mock_engine_replica = MagicMock()
    mock_engine_replica.sync_engine = mock_replica_sync

    with patch("bb_paxdata.infrastructure.db.session.engine", mock_engine), patch(
        "bb_paxdata.infrastructure.db.session.engine_replica", mock_engine_replica
    ):

        session = RoutingSession()

        # Simulate a SELECT statement
        clause = select(OutboxEventORM)
        bind = session.get_bind(clause=clause)

        # SELECT statement outside transaction should route to replica
        assert bind == mock_replica_sync


def test_routing_session_get_bind_non_select_outside_transaction():
    mock_primary_sync = MagicMock()
    mock_replica_sync = MagicMock()

    mock_engine = MagicMock()
    mock_engine.sync_engine = mock_primary_sync

    mock_engine_replica = MagicMock()
    mock_engine_replica.sync_engine = mock_replica_sync

    with patch("bb_paxdata.infrastructure.db.session.engine", mock_engine), patch(
        "bb_paxdata.infrastructure.db.session.engine_replica", mock_engine_replica
    ):

        session = RoutingSession()

        # Simulate an INSERT statement
        clause = insert(OutboxEventORM)
        bind = session.get_bind(clause=clause)

        # Non-SELECT statement should route to primary
        assert bind == mock_primary_sync


def test_routing_session_get_bind_inside_transaction():
    mock_primary_sync = MagicMock()
    mock_replica_sync = MagicMock()

    mock_engine = MagicMock()
    mock_engine.sync_engine = mock_primary_sync

    mock_engine_replica = MagicMock()
    mock_engine_replica.sync_engine = mock_replica_sync

    with patch("bb_paxdata.infrastructure.db.session.engine", mock_engine), patch(
        "bb_paxdata.infrastructure.db.session.engine_replica", mock_engine_replica
    ):

        session = RoutingSession()

        # Mock in_transaction to return True
        with patch.object(RoutingSession, "in_transaction", return_value=True):
            clause = select(OutboxEventORM)
            bind = session.get_bind(clause=clause)

            # Even a SELECT inside transaction must route to primary
            assert bind == mock_primary_sync


def test_routing_session_get_bind_with_modified_objects():
    mock_primary_sync = MagicMock()
    mock_replica_sync = MagicMock()

    mock_engine = MagicMock()
    mock_engine.sync_engine = mock_primary_sync

    mock_engine_replica = MagicMock()
    mock_engine_replica.sync_engine = mock_replica_sync

    with patch("bb_paxdata.infrastructure.db.session.engine", mock_engine), patch(
        "bb_paxdata.infrastructure.db.session.engine_replica", mock_engine_replica
    ):

        session = RoutingSession()

        # Mock session to have new objects via PropertyMock
        with patch.object(
            RoutingSession, "new", new_callable=PropertyMock, return_value=[MagicMock()]
        ):
            clause = select(OutboxEventORM)
            bind = session.get_bind(clause=clause)

            # Having dirty/new/deleted objects forces primary routing
            assert bind == mock_primary_sync
