# src/bb_paxdata/interfaces/api/routers/v1/templates.py
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.template_table import (
    OutputFormat,
    ReportTemplate,
    ReportTemplateVersion,
)
from bb_paxdata.infrastructure.templates_engine.context_builder import (
    TemplateContextBuilder,
)
from bb_paxdata.infrastructure.templates_engine.engine import (
    SafeTemplateEngine,
    TemplateSecurityError,
)
from bb_paxdata.infrastructure.templates_engine.variable_registry import (
    list_all_variables,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter()
engine = SafeTemplateEngine()


# Request/Response Schemas
class TemplateCreateRequest(BaseModel):
    name: str = Field(..., description="Template name")
    description: str | None = Field(None, description="Template description")
    category: str = Field(..., description="Template category")
    content: str = Field(..., description="Jinja2 template content")
    output_format: str = Field(OutputFormat.HTML.value, description="Output format")


class TemplateUpdateRequest(BaseModel):
    name: str | None = Field(None, description="Template name")
    description: str | None = Field(None, description="Template description")
    content: str | None = Field(None, description="Jinja2 template content")


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    category: str
    output_format: str
    variables_used: list[str]
    is_published: bool
    is_system: bool
    created_at: str
    updated_at: str


class PreviewRequest(BaseModel):
    file_id: str = Field(..., description="File ID for preview context")


class PreviewResponse(BaseModel):
    html: str
    errors: list[dict]


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = None,
    is_published: bool | None = None,
    is_system: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[TemplateResponse]:
    """List templates with optional filters."""
    stmt = select(ReportTemplate)

    if category:
        stmt = stmt.where(ReportTemplate.category == category)
    if is_published is not None:
        stmt = stmt.where(ReportTemplate.is_published == is_published)
    if is_system is not None:
        stmt = stmt.where(ReportTemplate.is_system == is_system)

    stmt = stmt.order_by(ReportTemplate.created_at.desc()).limit(limit).offset(offset)

    result = await db.scalars(stmt)
    templates = result.all()

    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            category=t.category,
            output_format=t.output_format,
            variables_used=json.loads(t.variables_used) if t.variables_used else [],
            is_published=t.is_published,
            is_system=t.is_system,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
        )
        for t in templates
    ]


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_req: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Create a new template."""
    # Validate syntax
    errors = engine.validate_syntax(template_req.content)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Template syntax errors", "errors": errors},
        )

    # Extract variables
    variables = engine.extract_variables(template_req.content)

    # Create template
    template_id = str(uuid.uuid4())
    template = ReportTemplate(
        id=template_id,
        name=template_req.name,
        description=template_req.description,
        category=template_req.category,
        content=template_req.content,
        output_format=template_req.output_format,
        variables_used=json.dumps(variables),
        is_published=False,
        is_system=False,
        created_by=None,  # Would come from auth
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_format=template.output_format,
        variables_used=variables,
        is_published=template.is_published,
        is_system=template.is_system,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else "",
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Get a single template by ID."""
    stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
    template = await db.scalar(stmt)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_format=template.output_format,
        variables_used=(
            json.loads(template.variables_used) if template.variables_used else []
        ),
        is_published=template.is_published,
        is_system=template.is_system,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else "",
    )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_req: TemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Update a template (creates new version)."""
    stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
    template = await db.scalar(stmt)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update system templates",
        )

    # Validate new content if provided
    if template_req.content:
        errors = engine.validate_syntax(template_req.content)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Template syntax errors", "errors": errors},
            )

    # Create version snapshot
    latest_version = await db.scalar(
        select(ReportTemplateVersion)
        .where(ReportTemplateVersion.template_id == template_id)
        .order_by(ReportTemplateVersion.version_number.desc())
    )
    new_version_num = (latest_version.version_number + 1) if latest_version else 1

    version = ReportTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=template_id,
        version_number=new_version_num,
        content=template.content,
        change_summary="Update via API",
        created_by=None,
    )
    db.add(version)

    # Update template
    update_data = {}
    if template_req.name:
        update_data["name"] = template_req.name
    if template_req.description is not None:
        update_data["description"] = template_req.description
    if template_req.content:
        update_data["content"] = template_req.content
        update_data["variables_used"] = json.dumps(
            engine.extract_variables(template_req.content)
        )

    if update_data:
        await db.execute(
            update(ReportTemplate)
            .where(ReportTemplate.id == template_id)
            .values(**update_data)
        )

    await db.commit()
    await db.refresh(template)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_format=template.output_format,
        variables_used=(
            json.loads(template.variables_used) if template.variables_used else []
        ),
        is_published=template.is_published,
        is_system=template.is_system,
        created_at=template.created_at.isoformat() if template.created_at else "",
        updated_at=template.updated_at.isoformat() if template.updated_at else "",
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a template."""
    stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
    template = await db.scalar(stmt)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system templates",
        )

    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/preview", response_model=PreviewResponse)
async def preview_template(
    template_id: str,
    preview_req: PreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """Preview template with actual data."""
    stmt = select(ReportTemplate).where(ReportTemplate.id == template_id)
    template = await db.scalar(stmt)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    # Build context
    try:
        context = TemplateContextBuilder.build_context(preview_req.file_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Render template
    errors = []
    html = ""
    try:
        html = engine.render(template.content, context)
    except TemplateSecurityError as e:
        errors.append({"type": "security", "message": str(e)})
    except Exception as e:
        errors.append({"type": "render", "message": str(e)})

    return PreviewResponse(html=html, errors=errors)


@router.get("/{template_id}/versions")
async def list_template_versions(
    template_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List template version history."""
    stmt = (
        select(ReportTemplateVersion)
        .where(ReportTemplateVersion.template_id == template_id)
        .order_by(ReportTemplateVersion.version_number.desc())
    )

    result = await db.scalars(stmt)
    versions = result.all()

    return {
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "change_summary": v.change_summary,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "total": len(versions),
    }


@router.get("/variables/registry")
async def get_variable_registry() -> dict:
    """Get available template variables."""
    return list_all_variables()
