"""
Weight Calibration Workflow Service

Manages the HITL workflow for weight update proposals.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.weight_calibration import (
    CalibratableParameter,
    ProposalStatus,
    WeightUpdateProposal,
    WeightVersionHistory,
)
from bb_paxdata.infrastructure.db.repositories.weight_calibration_repository import (
    WeightCalibrationRepository,
)

logger = structlog.get_logger(__name__)


class WeightCalibrationWorkflow:
    """
    Manages the HITL workflow for weight calibration.

    Workflow:
    1. Automatic proposal generation (by WeightCalibrator)
    2. Human review and approval (via dashboard)
    3. Activation of approved proposals
    4. Rollback support if correction rate degrades
    """

    def __init__(
        self,
        db: AsyncSession,
        repo: WeightCalibrationRepository,
    ) -> None:
        self._db = db
        self._repo = repo

    async def create_and_save_proposal(
        self,
        proposal: WeightUpdateProposal,
    ) -> WeightUpdateProposal:
        """
        Create and save a weight update proposal.

        Args:
            proposal: The proposal to save

        Returns:
            Saved proposal with ID
        """
        saved = await self._repo.save_proposal(proposal)
        logger.info(
            "weight_proposal_saved",
            proposal_id=saved.id,
            parameter=saved.parameter_name,
            old_value=saved.old_value,
            proposed_value=saved.proposed_value,
        )
        return saved

    async def approve_proposal(
        self,
        proposal_id: str,
        approver_id: str,
    ) -> WeightUpdateProposal | None:
        """
        Approve a weight update proposal.

        Args:
            proposal_id: ID of the proposal to approve
            approver_id: ID of the human approver

        Returns:
            Updated proposal, or None if not found
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            logger.warning("proposal_not_found", proposal_id=proposal_id)
            return None

        if proposal.status != ProposalStatus.PENDING:
            logger.warning(
                "proposal_not_pending",
                proposal_id=proposal_id,
                current_status=proposal.status,
            )
            return proposal

        updated = await self._repo.update_proposal_status(
            proposal_id=proposal_id,
            status=ProposalStatus.APPROVED,
            approved_by=approver_id,
        )

        logger.info(
            "weight_proposal_approved",
            proposal_id=proposal_id,
            approver=approver_id,
        )

        return updated

    async def reject_proposal(
        self,
        proposal_id: str,
        approver_id: str,
        reason: str | None = None,
    ) -> WeightUpdateProposal | None:
        """
        Reject a weight update proposal.

        Args:
            proposal_id: ID of the proposal to reject
            approver_id: ID of the human approver
            reason: Optional rejection reason

        Returns:
            Updated proposal, or None if not found
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            logger.warning("proposal_not_found", proposal_id=proposal_id)
            return None

        if proposal.status != ProposalStatus.PENDING:
            logger.warning(
                "proposal_not_pending",
                proposal_id=proposal_id,
                current_status=proposal.status,
            )
            return proposal

        updated = await self._repo.update_proposal_status(
            proposal_id=proposal_id,
            status=ProposalStatus.REJECTED,
            approved_by=approver_id,
        )

        logger.info(
            "weight_proposal_rejected",
            proposal_id=proposal_id,
            approver=approver_id,
            reason=reason,
        )

        return updated

    async def activate_proposal(
        self,
        proposal_id: str,
    ) -> tuple[CalibratableParameter, WeightVersionHistory] | None:
        """
        Activate an approved proposal.

        This applies the weight update and creates a version history entry.

        Args:
            proposal_id: ID of the proposal to activate

        Returns:
            Tuple of (updated parameter, version history), or None if failed
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            logger.warning("proposal_not_found", proposal_id=proposal_id)
            return None

        if proposal.status != ProposalStatus.APPROVED:
            logger.warning(
                "proposal_not_approved",
                proposal_id=proposal_id,
                current_status=proposal.status,
            )
            return None

        # Get current parameter
        parameter = await self._repo.get_parameter(proposal.parameter_id)
        if not parameter:
            logger.warning(
                "parameter_not_found",
                parameter_id=proposal.parameter_id,
            )
            return None

        # Save version history before updating
        history = WeightVersionHistory(
            id=str(uuid.uuid4()),
            parameter_id=parameter.id,
            version=parameter.version,
            value=parameter.current_value,
            created_at=datetime.utcnow(),
            created_by="system",
            reason=f"Before activation of proposal {proposal_id}",
            proposal_id=proposal.id,
        )
        await self._repo.save_version_history(history)

        # Update parameter with new value
        updated_parameter = CalibratableParameter(
            id=parameter.id,
            name=parameter.name,
            parameter_type=parameter.parameter_type,
            current_value=proposal.proposed_value,
            min_value=parameter.min_value,
            max_value=parameter.max_value,
            description=parameter.description,
            last_updated=datetime.utcnow(),
            version=parameter.version + 1,
        )
        saved = await self._repo.save_parameter(updated_parameter)

        # Update proposal status to activated
        await self._repo.update_proposal_status(
            proposal_id=proposal_id,
            status=ProposalStatus.ACTIVATED,
        )

        logger.info(
            "weight_proposal_activated",
            proposal_id=proposal_id,
            parameter=parameter.name,
            old_value=parameter.current_value,
            new_value=proposal.proposed_value,
            new_version=saved.version,
        )

        return saved, history

    async def rollback_parameter(
        self,
        parameter_id: str,
        target_version: int | None = None,
        reason: str = "Manual rollback",
        operator_id: str = "system",
    ) -> CalibratableParameter | None:
        """
        Rollback a parameter to a previous version.

        Args:
            parameter_id: ID of the parameter to rollback
            target_version: Target version (None for previous version)
            reason: Reason for rollback
            operator_id: ID of the operator performing rollback

        Returns:
            Updated parameter, or None if failed
        """
        parameter = await self._repo.get_parameter(parameter_id)
        if not parameter:
            logger.warning("parameter_not_found", parameter_id=parameter_id)
            return None

        # Get version history
        history = await self._repo.get_parameter_history(parameter_id)

        if not history:
            logger.warning("no_version_history", parameter_id=parameter_id)
            return None

        # Find target version
        if target_version is None:
            # Rollback to previous version
            target_version = parameter.version - 1

        target_entry = None
        for entry in history:
            if entry.version == target_version:
                target_entry = entry
                break

        if not target_entry:
            logger.warning(
                "target_version_not_found",
                parameter_id=parameter_id,
                target_version=target_version,
            )
            return None

        # Save current version to history
        current_history = WeightVersionHistory(
            id=str(uuid.uuid4()),
            parameter_id=parameter.id,
            version=parameter.version,
            value=parameter.current_value,
            created_at=datetime.utcnow(),
            created_by=operator_id,
            reason=f"Before rollback to version {target_version}: {reason}",
        )
        await self._repo.save_version_history(current_history)

        # Update parameter to target version value
        updated_parameter = CalibratableParameter(
            id=parameter.id,
            name=parameter.name,
            parameter_type=parameter.parameter_type,
            current_value=target_entry.value,
            min_value=parameter.min_value,
            max_value=parameter.max_value,
            description=parameter.description,
            last_updated=datetime.utcnow(),
            version=target_version,
        )
        saved = await self._repo.save_parameter(updated_parameter)

        # Mark associated proposal as rolled back
        if target_entry.proposal_id:
            await self._repo.update_proposal_status(
                proposal_id=target_entry.proposal_id,
                status=ProposalStatus.ROLLED_BACK,
            )

        logger.info(
            "parameter_rolled_back",
            parameter_id=parameter_id,
            from_version=parameter.version,
            to_version=target_version,
            reason=reason,
        )

        return saved

    async def get_pending_proposals(
        self,
        limit: int = 100,
    ) -> list[WeightUpdateProposal]:
        """Get all pending proposals awaiting review."""
        return await self._repo.list_proposals(
            status=ProposalStatus.PENDING,
            limit=limit,
        )

    async def get_active_parameters(self) -> list[CalibratableParameter]:
        """Get all active calibratable parameters."""
        return await self._repo.list_parameters()
