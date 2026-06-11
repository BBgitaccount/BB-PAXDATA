import difflib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bb_paxdata.infrastructure.ai.prompt_registry import (
    ALLOWED_ACADEMIC_REFS,
    get_prompt_registry,
)

router = APIRouter(prefix="/prompts", tags=["Prompts"])


class PromptVersionResponse(BaseModel):
    version_id: str
    content: str
    content_hash: str
    academic_ref: str | None = None
    created_at: str


class PromptListResponse(BaseModel):
    prompts: dict[str, list[PromptVersionResponse]]


class PromptDiffResponse(BaseModel):
    name: str
    from_version: str
    to_version: str
    unified_diff: list[str]
    added_lines: int
    removed_lines: int


class RegisterPromptRequest(BaseModel):
    content: str = Field(..., min_length=10)
    academic_ref: str = Field(
        ...,
        description=(
            f"Zorunlu akademik referans anahtarı. "
            f"İzin verilenler: {sorted(ALLOWED_ACADEMIC_REFS)}"
        ),
    )


@router.get("/", response_model=PromptListResponse)
async def list_all_prompts():
    """Tüm promptları ve versiyonlarını listeler."""
    registry = get_prompt_registry()
    if hasattr(registry, "_prompts"):
        all_prompts_data = getattr(registry, "_prompts")
        result = {}
        for name, versions in all_prompts_data.items():
            result[name] = [
                PromptVersionResponse(
                    version_id=v.version_id,
                    content=v.content,
                    content_hash=v.content_hash,
                    academic_ref=v.academic_ref,
                    created_at=v.created_at.isoformat(),
                )
                for v in versions.values()
            ]
        return PromptListResponse(prompts=result)

    return PromptListResponse(prompts={})


@router.get("/{name}/versions", response_model=list[PromptVersionResponse])
async def list_prompt_versions(name: str):
    """Belirli bir promptun tüm versiyonlarını listeler."""
    registry = get_prompt_registry()
    versions = await registry.list_versions(name)
    if not versions:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return [
        PromptVersionResponse(
            version_id=v.version_id,
            content=v.content,
            content_hash=v.content_hash,
            academic_ref=v.academic_ref,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.get("/{name}/diff", response_model=PromptDiffResponse)
async def diff_prompt_versions(name: str, from_version: str, to_version: str):
    """İki prompt versiyonu arasındaki farkı (diff) döner.

    Unified diff formatında, akademik referans izlenebilirliği ile birlikte.
    """
    registry = get_prompt_registry()

    if not hasattr(registry, "_prompts"):
        raise HTTPException(status_code=501, detail="Registry does not support diff")

    all_prompts = getattr(registry, "_prompts")
    if name not in all_prompts:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    versions = all_prompts[name]

    v_from = versions.get(from_version)
    v_to = versions.get(to_version)

    if v_from is None:
        raise HTTPException(
            status_code=404, detail=f"Version '{from_version}' not found"
        )
    if v_to is None:
        raise HTTPException(status_code=404, detail=f"Version '{to_version}' not found")

    from_lines = v_from.content.splitlines(keepends=True)
    to_lines = v_to.content.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=f"{name}/{from_version}",
            tofile=f"{name}/{to_version}",
            lineterm="",
        )
    )

    added = sum(
        1 for line in diff if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1 for line in diff if line.startswith("-") and not line.startswith("---")
    )

    return PromptDiffResponse(
        name=name,
        from_version=from_version,
        to_version=to_version,
        unified_diff=diff,
        added_lines=added,
        removed_lines=removed,
    )


@router.post("/{name}/register", response_model=PromptVersionResponse, status_code=201)
async def register_new_prompt_version(name: str, payload: RegisterPromptRequest):
    """Yeni bir prompt versiyonu kaydeder.

    Akademik referans zinciri zorunludur. İzin verilen referans anahtarları:
    Grimmer2013, SalagerMeyer1997, Hyland1998, Iyengar1991, Entman1993
    """
    if payload.academic_ref not in ALLOWED_ACADEMIC_REFS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Geçersiz akademik referans: '{payload.academic_ref}'. "
                f"İzin verilenler: {sorted(ALLOWED_ACADEMIC_REFS)}"
            ),
        )

    registry = get_prompt_registry()
    version = await registry.register(
        name=name,
        content=payload.content,
        academic_ref=payload.academic_ref,
    )

    return PromptVersionResponse(
        version_id=version.version_id,
        content=version.content,
        content_hash=version.content_hash,
        academic_ref=version.academic_ref,
        created_at=version.created_at.isoformat(),
    )
