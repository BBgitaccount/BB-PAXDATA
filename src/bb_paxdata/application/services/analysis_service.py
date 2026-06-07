"""Application service for running sentence analysis."""

from typing import Any

from bb_paxdata.infrastructure.container.service_container import ServiceContainer


async def run_sentence_analysis(
    sent_id: str, text: str, context: dict[str, Any]
) -> dict[str, Any]:
    """Runs NLP/LLM analysis on a sentence using the pipeline, returning serializable results."""
    container = ServiceContainer.get_instance()
    pipeline = container.pipeline

    file_id = context.get("file_id", "unknown")
    country = context.get("country", "unknown")
    power_level = float(context.get("power_level", 5)) / 10.0
    speaker_id = context.get("speaker_id", "unknown")
    sent_idx = context.get("sentence_index", 1)

    pipeline_res = await pipeline.run(
        text=text,
        file_id=file_id,
        speaker_country=country,
        speaker_power_level=power_level,
        metadata={
            "file_id": file_id,
            "speaker_id": speaker_id,
            "speaker_country": country,
            "id": sent_id,
        },
        session=None,
        speaker_id=speaker_id,
        sentence_index=sent_idx,
    )

    # Extract fields from the pipeline result
    analysis = pipeline_res.analysis

    return {
        "sent_id": sent_id,
        "ai_sentiment_label": getattr(
            analysis, "ai_sentiment_label", "neutral_cautious"
        ),
        "ai_sentiment_score": getattr(analysis, "ai_sentiment_score", 0.0),
        "ai_risk_score": getattr(analysis, "ai_risk_score", 0.0),
        "ai_primary_topic": getattr(analysis, "ai_primary_topic", None)
        or (
            analysis.topic_synthesis.topic_label
            if getattr(analysis, "topic_synthesis", None)
            else None
        ),
        "ai_diplomatic_tone": getattr(analysis, "ai_diplomatic_tone", "neutral"),
        "coherence_score": getattr(analysis, "coherence_score", 1.0),
        "framing": (analysis.framing if getattr(analysis, "framing", None) else None),
        "logic_result": "FAIL" if getattr(analysis, "anomaly_flags", None) else "PASS",
    }
