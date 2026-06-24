"""Weight Calibration API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.weight_calibration import (
    ProposalStatus,
)
from bb_paxdata.application.services.weight_calibration_workflow import (
    WeightCalibrationWorkflow,
)
from bb_paxdata.infrastructure.db.repositories.weight_calibration_repository import (
    WeightCalibrationRepository,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(
    prefix="/weight-calibration",
    tags=["Weight Calibration"],
)


def get_calibration_repository(db: AsyncSession = Depends(get_db)):
    """Dependency injection for WeightCalibrationRepository."""
    return WeightCalibrationRepository(db)


def get_calibration_workflow(
    repo=Depends(get_calibration_repository),
):
    """Dependency injection for WeightCalibrationWorkflow."""
    return WeightCalibrationWorkflow(db=repo._session, repo=repo)


class CalibratableParameterSchema(BaseModel):
    """Schema for calibratable parameter."""

    id: str
    name: str
    parameter_type: str
    current_value: float
    min_value: float
    max_value: float
    description: str
    last_updated: datetime
    version: int

    class Config:
        from_attributes = True


class WeightUpdateProposalSchema(BaseModel):
    """Schema for weight update proposal."""

    id: str
    parameter_id: str
    parameter_name: str
    old_value: float
    proposed_value: float
    correction_signal: float
    learning_rate: float
    confidence: float
    reason: str
    created_at: datetime
    status: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    activated_at: datetime | None = None
    rollback_version: int | None = None

    class Config:
        from_attributes = True


class ApproveProposalRequest(BaseModel):
    """Request to approve a proposal."""

    approver_id: str = Field(..., description="ID of the approver")


class RejectProposalRequest(BaseModel):
    """Request to reject a proposal."""

    approver_id: str = Field(..., description="ID of the approver")
    reason: str | None = Field(None, description="Optional rejection reason")


class RollbackRequest(BaseModel):
    """Request to rollback a parameter."""

    target_version: int | None = Field(
        None, description="Target version (None for previous)"
    )
    reason: str = Field("Manual rollback", description="Reason for rollback")
    operator_id: str = Field("system", description="ID of the operator")


@router.get("/parameters", response_model=list[CalibratableParameterSchema])
async def list_parameters(
    parameter_type: Annotated[str | None, Query()] = None,
    workflow=Depends(get_calibration_workflow),
):
    """List all calibratable parameters."""
    parameters = await workflow.get_active_parameters()
    return [CalibratableParameterSchema.model_validate(p) for p in parameters]


@router.get("/proposals", response_model=list[WeightUpdateProposalSchema])
async def list_proposals(
    status: Annotated[str | None, Query()] = None,
    parameter_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    repo=Depends(get_calibration_repository),
):
    """List weight update proposals with optional filters."""
    proposal_status = ProposalStatus(status) if status else None
    proposals = await repo.list_proposals(
        status=proposal_status,
        parameter_id=parameter_id,
        limit=limit,
        offset=offset,
    )
    return [WeightUpdateProposalSchema.model_validate(p) for p in proposals]


@router.get("/proposals/pending", response_model=list[WeightUpdateProposalSchema])
async def get_pending_proposals(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    workflow=Depends(get_calibration_workflow),
):
    """Get all pending proposals awaiting review."""
    proposals = await workflow.get_pending_proposals(limit=limit)
    return [WeightUpdateProposalSchema.model_validate(p) for p in proposals]


@router.get("/proposals/{proposal_id}", response_model=WeightUpdateProposalSchema)
async def get_proposal(
    proposal_id: str,
    repo=Depends(get_calibration_repository),
):
    """Get a specific proposal by ID."""
    proposal = await repo.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return WeightUpdateProposalSchema.model_validate(proposal)


@router.post(
    "/proposals/{proposal_id}/approve", response_model=WeightUpdateProposalSchema
)
async def approve_proposal(
    proposal_id: str,
    request: ApproveProposalRequest,
    workflow=Depends(get_calibration_workflow),
):
    """Approve a weight update proposal."""
    proposal = await workflow.approve_proposal(
        proposal_id=proposal_id,
        approver_id=request.approver_id,
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return WeightUpdateProposalSchema.model_validate(proposal)


@router.post(
    "/proposals/{proposal_id}/reject", response_model=WeightUpdateProposalSchema
)
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequest,
    workflow=Depends(get_calibration_workflow),
):
    """Reject a weight update proposal."""
    proposal = await workflow.reject_proposal(
        proposal_id=proposal_id,
        approver_id=request.approver_id,
        reason=request.reason,
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return WeightUpdateProposalSchema.model_validate(proposal)


@router.post("/proposals/{proposal_id}/activate")
async def activate_proposal(
    proposal_id: str,
    workflow=Depends(get_calibration_workflow),
):
    """Activate an approved proposal."""
    result = await workflow.activate_proposal(proposal_id=proposal_id)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Failed to activate proposal (not found or not approved)",
        )
    parameter, history = result
    return {
        "message": "Proposal activated successfully",
        "parameter": CalibratableParameterSchema.model_validate(parameter),
        "version_history": {
            "version": history.version,
            "value": history.value,
            "created_at": history.created_at,
        },
    }


@router.post(
    "/parameters/{parameter_id}/rollback", response_model=CalibratableParameterSchema
)
async def rollback_parameter(
    parameter_id: str,
    request: RollbackRequest,
    workflow=Depends(get_calibration_workflow),
):
    """Rollback a parameter to a previous version."""
    parameter = await workflow.rollback_parameter(
        parameter_id=parameter_id,
        target_version=request.target_version,
        reason=request.reason,
        operator_id=request.operator_id,
    )
    if not parameter:
        raise HTTPException(
            status_code=404, detail="Parameter not found or rollback failed"
        )
    return CalibratableParameterSchema.model_validate(parameter)
