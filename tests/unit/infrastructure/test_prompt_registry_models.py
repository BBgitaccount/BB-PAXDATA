from uuid import uuid4

from bb_paxdata.domain.enums import PipelineStage
from bb_paxdata.infrastructure.ai.prompt_registry import AcademicRefTrace, PromptVersion


def test_prompt_version_hash():
    content = "Test prompt content"
    hash_val = PromptVersion.compute_hash(content)

    version = PromptVersion(
        version_id="test@v1.0",
        content=content,
        content_hash=hash_val,
        academic_ref="Entman1993",
    )
    assert version.content_hash == hash_val
    assert version.academic_ref == "Entman1993"


def test_academic_ref_trace():
    analysis_id = uuid4()
    trace = AcademicRefTrace(
        analysis_id=analysis_id,
        prompt_version_id="diplomatic@v1.0",
        prompt_content_hash="hash123",
        academic_ref="Grimmer2013",
        pipeline_stage=PipelineStage.DETECT,
    )
    assert trace.pipeline_stage == PipelineStage.DETECT
    assert trace.academic_ref == "Grimmer2013"
