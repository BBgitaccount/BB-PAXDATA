"""Repository for weight calibration models."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.weight_calibration import (
    CalibratableParameter,
    ProposalStatus,
    WeightUpdateProposal,
    WeightVersionHistory,
)
from bb_paxdata.infrastructure.db.weight_calibration_table import (
    CalibratableParameterORM,
    WeightUpdateProposalORM,
    WeightVersionHistoryORM,
)


class WeightCalibrationRepository:
    """Repository for weight calibration operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # CalibratableParameter operations
    async def save_parameter(
        self, parameter: CalibratableParameter
    ) -> CalibratableParameter:
        """Save or update a calibratable parameter."""
        orm = CalibratableParameterORM(
            id=parameter.id,
            name=parameter.name,
            parameter_type=parameter.parameter_type.value,
            current_value=parameter.current_value,
            min_value=parameter.min_value,
            max_value=parameter.max_value,
            description=parameter.description,
            last_updated=parameter.last_updated,
            version=parameter.version,
        )

        self._session.merge(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_domain_model()

    async def get_parameter(self, parameter_id: str) -> CalibratableParameter | None:
        """Get a parameter by ID."""
        stmt = select(CalibratableParameterORM).where(
            CalibratableParameterORM.id == parameter_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain_model() if orm else None

    async def get_parameter_by_name(self, name: str) -> CalibratableParameter | None:
        """Get a parameter by name."""
        stmt = select(CalibratableParameterORM).where(
            CalibratableParameterORM.name == name
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain_model() if orm else None

    async def list_parameters(
        self, parameter_type: str | None = None
    ) -> Sequence[CalibratableParameter]:
        """List all parameters, optionally filtered by type."""
        conditions = []
        if parameter_type:
            conditions.append(CalibratableParameterORM.parameter_type == parameter_type)

        stmt = select(CalibratableParameterORM).where(
            and_(*conditions) if conditions else True
        )
        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return [orm.to_domain_model() for orm in orms]

    # WeightUpdateProposal operations
    async def save_proposal(
        self, proposal: WeightUpdateProposal
    ) -> WeightUpdateProposal:
        """Save a weight update proposal."""
        orm = WeightUpdateProposalORM(
            id=proposal.id,
            parameter_id=proposal.parameter_id,
            parameter_name=proposal.parameter_name,
            old_value=proposal.old_value,
            proposed_value=proposal.proposed_value,
            correction_signal=proposal.correction_signal,
            learning_rate=proposal.learning_rate,
            confidence=proposal.confidence,
            reason=proposal.reason,
            created_at=proposal.created_at,
            status=proposal.status.value,
            approved_by=proposal.approved_by,
            approved_at=proposal.approved_at,
            activated_at=proposal.activated_at,
            rollback_version=proposal.rollback_version,
        )

        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_domain_model()

    async def get_proposal(self, proposal_id: str) -> WeightUpdateProposal | None:
        """Get a proposal by ID."""
        stmt = select(WeightUpdateProposalORM).where(
            WeightUpdateProposalORM.id == proposal_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_domain_model() if orm else None

    async def list_proposals(
        self,
        status: ProposalStatus | None = None,
        parameter_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[WeightUpdateProposal]:
        """List proposals with optional filters."""
        conditions = []
        if status:
            conditions.append(WeightUpdateProposalORM.status == status.value)
        if parameter_id:
            conditions.append(WeightUpdateProposalORM.parameter_id == parameter_id)

        stmt = (
            select(WeightUpdateProposalORM)
            .where(and_(*conditions) if conditions else True)
            .order_by(WeightUpdateProposalORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return [orm.to_domain_model() for orm in orms]

    async def update_proposal_status(
        self,
        proposal_id: str,
        status: ProposalStatus,
        approved_by: str | None = None,
    ) -> WeightUpdateProposal | None:
        """Update proposal status."""
        stmt = select(WeightUpdateProposalORM).where(
            WeightUpdateProposalORM.id == proposal_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        orm.status = status.value
        if approved_by:
            orm.approved_by = approved_by
        if status == ProposalStatus.APPROVED:
            orm.approved_at = datetime.utcnow()
        if status == ProposalStatus.ACTIVATED:
            orm.activated_at = datetime.utcnow()

        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_domain_model()

    # WeightVersionHistory operations
    async def save_version_history(
        self, history: WeightVersionHistory
    ) -> WeightVersionHistory:
        """Save a version history entry."""
        orm = WeightVersionHistoryORM(
            id=history.id,
            parameter_id=history.parameter_id,
            version=history.version,
            value=history.value,
            created_at=history.created_at,
            created_by=history.created_by,
            reason=history.reason,
            proposal_id=history.proposal_id,
        )

        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return history

    async def get_parameter_history(
        self, parameter_id: str, limit: int = 50
    ) -> Sequence[WeightVersionHistory]:
        """Get version history for a parameter."""
        stmt = (
            select(WeightVersionHistoryORM)
            .where(WeightVersionHistoryORM.parameter_id == parameter_id)
            .order_by(WeightVersionHistoryORM.version.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        orms = result.scalars().all()

        return [
            WeightVersionHistory(
                id=orm.id,
                parameter_id=orm.parameter_id,
                version=orm.version,
                value=orm.value,
                created_at=orm.created_at,
                created_by=orm.created_by,
                reason=orm.reason,
                proposal_id=orm.proposal_id,
            )
            for orm in orms
        ]

    async def get_latest_version(
        self, parameter_id: str
    ) -> WeightVersionHistory | None:
        """Get the latest version for a parameter."""
        stmt = (
            select(WeightVersionHistoryORM)
            .where(WeightVersionHistoryORM.parameter_id == parameter_id)
            .order_by(WeightVersionHistoryORM.version.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()

        if not orm:
            return None

        return WeightVersionHistory(
            id=orm.id,
            parameter_id=orm.parameter_id,
            version=orm.version,
            value=orm.value,
            created_at=orm.created_at,
            created_by=orm.created_by,
            reason=orm.reason,
            proposal_id=orm.proposal_id,
        )
