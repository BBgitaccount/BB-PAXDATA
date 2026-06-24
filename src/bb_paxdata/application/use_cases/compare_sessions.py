from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from bb_paxdata.application.domain.models.analysis_delta import (
    AnalysisDelta,
    NarrativeLayerDelta,
    RiskAssessmentLevel,
    SignificantChange,
    SpeechActDistributionDelta,
)
from bb_paxdata.application.domain.models.contrast_report import ContrastReport
from bb_paxdata.infrastructure.observability.metrics import get_metrics

if TYPE_CHECKING:
    from bb_paxdata.application.protocols import LLMServiceProtocol

logger = structlog.get_logger(__name__)
metrics = get_metrics()

# Normalization scale floors — calibrate against production data before release
_SBI_SCALE_FLOOR = 0.10
_DKI_SCALE_FLOOR = 0.10
_HEDGING_SCALE_FLOOR = 0.05
_RISK_SCALE_FLOOR = 0.05


def _normalize(delta: float, baseline: float, floor: float) -> float:
    """Normalize delta relative to baseline, with a minimum denominator floor."""
    return delta / max(abs(baseline), floor)


@dataclass(frozen=True)
class CompareSessionsInput:
    session_a_id: str
    session_b_id: str
    sbi_threshold: float = 0.15
    dki_threshold: float = 0.15
    risk_threshold: float = 0.10
    hedging_threshold: float = 0.10
    include_narrative: bool = True
    narrative_language: str = "en"


@dataclass(frozen=True)
class CompareSessionsOutput:
    success: bool
    contrast_report: ContrastReport | None = None
    analysis_delta: AnalysisDelta | None = None
    errors: tuple[str, ...] = ()  # soft/non-fatal
    fatal_errors: tuple[str, ...] = ()  # hard failures

    @property
    def succeeded(self) -> bool:
        """True if delta was computed, regardless of soft failures."""
        return self.success and len(self.fatal_errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.errors) > 0


class CompareSessionsUseCase:
    def __init__(
        self,
        sbi_repository: Any,
        dki_repository: Any,
        analysis_repository: Any,
        bilateral_repository: Any,  # retained for future bilateral delta
        discourse_repository: Any,
        llm_service: LLMServiceProtocol | None = None,
    ) -> None:
        self._sbi_repo = sbi_repository
        self._dki_repo = dki_repository
        self._analysis_repo = analysis_repository
        self._bilateral_repo = bilateral_repository
        self._discourse_repo = discourse_repository
        self._llm_service = llm_service
        self._narrative_cache: dict[tuple[str, str], str] = {}

    async def execute(self, input_data: CompareSessionsInput) -> CompareSessionsOutput:
        session_a, session_b = input_data.session_a_id, input_data.session_b_id
        soft_errors: list[str] = []
        start_time = time.monotonic()

        logger.info(
            "compare_sessions.started",
            session_a=session_a,
            session_b=session_b,
        )

        # Pre-fetch analyses once per session (covers risk, hedging, speech act)
        try:
            analyses_a, analyses_b = await asyncio.gather(
                self._analysis_repo.get_by_session(session_a),
                self._analysis_repo.get_by_session(session_b),
            )
        except Exception as exc:
            return CompareSessionsOutput(
                success=False,
                fatal_errors=(f"Analysis pre-fetch failed: {exc}",),
            )

        # Parallel fetch of all remaining data sources
        fetch_results = await asyncio.gather(
            self._fetch_sbi_data(session_a),
            self._fetch_sbi_data(session_b),
            self._fetch_dki_data(session_a),
            self._fetch_dki_data(session_b),
            self._fetch_narrative_data(session_a),
            self._fetch_narrative_data(session_b),
            return_exceptions=True,
        )

        def _unwrap(result: Any, name: str, default: Any) -> Any:
            if isinstance(result, Exception):
                soft_errors.append(f"{name} fetch failed: {result}")
                return default
            return result

        sbi_a = _unwrap(fetch_results[0], "SBI(A)", {})
        sbi_b = _unwrap(fetch_results[1], "SBI(B)", {})
        dki_a = _unwrap(fetch_results[2], "DKI(A)", {})
        dki_b = _unwrap(fetch_results[3], "DKI(B)", {})
        narr_a = _unwrap(fetch_results[4], "Narrative(A)", {})
        narr_b = _unwrap(fetch_results[5], "Narrative(B)", {})

        # Derive analysis-backed metrics from pre-fetched analyses (no extra queries)
        risk_a = self._fetch_risk_from_analyses(analyses_a)
        risk_b = self._fetch_risk_from_analyses(analyses_b)
        hedging_a = self._fetch_hedging_from_analyses(analyses_a)
        hedging_b = self._fetch_hedging_from_analyses(analyses_b)
        speech_a = self._fetch_speech_act_from_analyses(analyses_a)
        speech_b = self._fetch_speech_act_from_analyses(analyses_b)

        # Compute delta
        delta_start_time = time.monotonic()
        try:
            delta = self._calculate_delta(
                session_a=session_a,
                session_b=session_b,
                sbi_a=sbi_a,
                sbi_b=sbi_b,
                dki_a=dki_a,
                dki_b=dki_b,
                risk_a=risk_a,
                risk_b=risk_b,
                hedging_a=hedging_a,
                hedging_b=hedging_b,
                speech_act_a=speech_a,
                speech_act_b=speech_b,
                narrative_a=narr_a,
                narrative_b=narr_b,
                input_data=input_data,
            )
        except Exception as exc:
            total_duration = time.monotonic() - start_time
            metrics.record_comparison_total_duration(total_duration, "failed")
            metrics.record_comparison_session_compared("failed")
            return CompareSessionsOutput(
                success=False,
                fatal_errors=(f"Delta calculation failed: {exc}",),
                errors=tuple(soft_errors),
            )

        delta_duration = time.monotonic() - delta_start_time
        metrics.record_comparison_delta_duration(delta_duration)

        # Generate narrative (soft failure — delta is still returned)
        narrative_summary: str | None = None
        narrative_failed = False
        narrative_skipped = not input_data.include_narrative or not self._llm_service
        narrative_start_time = time.monotonic()
        if not narrative_skipped:
            try:
                narrative_summary = await self._get_cached_narrative(
                    delta, input_data.narrative_language
                )
                narrative_duration = time.monotonic() - narrative_start_time
                metrics.record_comparison_narrative_duration(
                    narrative_duration, "success"
                )
                metrics.record_comparison_llm_request()
            except Exception as exc:
                soft_errors.append(f"Narrative generation failed: {exc}")
                narrative_failed = True
                narrative_duration = time.monotonic() - narrative_start_time
                metrics.record_comparison_narrative_duration(
                    narrative_duration, "failed"
                )
                metrics.record_comparison_llm_failure()

        contrast_report = ContrastReport(
            delta=delta,
            narrative_summary=narrative_summary,
            narrative_summary_skipped=narrative_skipped,
            narrative_summary_failed=narrative_failed,
            narrative_summary_model=(
                getattr(self._llm_service, "model_name", "")
                if self._llm_service
                else ""
            ),
            narrative_summary_timestamp=(
                datetime.now(UTC) if narrative_summary else None
            ),
            key_insights=self._extract_key_insights(delta),
            risk_assessment=self._assess_risk(delta),
            risk_level_changed=delta.delta_risk_significant,
            recommendation=self._generate_recommendation(delta),
        )

        logger.info(
            "compare_sessions.completed",
            session_a=session_a,
            session_b=session_b,
            significant_changes=delta.total_significant_changes,
            most_drifted_speaker=delta.most_drifted_speaker,
            soft_error_count=len(soft_errors),
        )

        total_duration = time.monotonic() - start_time
        metrics.record_comparison_total_duration(total_duration, "success")
        metrics.record_comparison_session_compared("success")
        metrics.record_comparison_significant_changes(delta.total_significant_changes)

        return CompareSessionsOutput(
            success=True,
            contrast_report=contrast_report,
            analysis_delta=delta,
            errors=tuple(soft_errors),
        )

    async def _fetch_sbi_data(self, session_id: str) -> dict:
        positions = await self._sbi_repo.get_by_session(session_id)
        return {p.speaker_id: p for p in positions}

    async def _fetch_dki_data(self, session_id: str) -> dict:
        results = await self._dki_repo.get_by_session(session_id)
        return {r.speaker_id: r for r in results}

    def _fetch_risk_from_analyses(self, analyses: list) -> float | None:
        risk_scores = [a.ai_risk_score for a in analyses if a.ai_risk_score is not None]
        return sum(risk_scores) / len(risk_scores) if risk_scores else None

    def _fetch_hedging_from_analyses(self, analyses: list) -> dict:
        speaker_hedging: dict = {}
        for a in analyses:
            if a.hedging_result and a.speaker_id:
                speaker_hedging.setdefault(a.speaker_id, []).append(
                    a.hedging_result.score
                )
        return {s: sum(v) / len(v) for s, v in speaker_hedging.items()}

    def _fetch_speech_act_from_analyses(self, analyses: list) -> dict:
        dist: dict = {}
        for a in analyses:
            if a.speech_act and a.speaker_id:
                d = dist.setdefault(a.speaker_id, {})
                act_type = a.speech_act.primary_type.value
                d[act_type] = d.get(act_type, 0.0) + 1.0
        for speaker, value in dist.items():
            total = sum(value.values())
            if total > 0:
                dist[speaker] = {k: v / total for k, v in dist[speaker].items()}
        return dist

    async def _fetch_narrative_data(self, session_id: str) -> dict:
        flows = await self._discourse_repo.get_by_session(session_id)
        speaker_layers: dict = {}
        for flow in flows:
            speaker = getattr(flow, "speaker_id", "__session__")
            speaker_layers.setdefault(speaker, {}).setdefault(
                flow.narrative_layer, []
            ).append(flow.narrative_salience)
        return {
            speaker: {layer: sum(vals) / len(vals) for layer, vals in layers.items()}
            for speaker, layers in speaker_layers.items()
        }

    def _calculate_delta(
        self,
        session_a: str,
        session_b: str,
        sbi_a: dict,
        sbi_b: dict,
        dki_a: dict,
        dki_b: dict,
        risk_a: float | None,
        risk_b: float | None,
        hedging_a: dict,
        hedging_b: dict,
        speech_act_a: dict,
        speech_act_b: dict,
        narrative_a: dict,
        narrative_b: dict,
        input_data: CompareSessionsInput,
    ) -> AnalysisDelta:
        speakers_a = set(sbi_a.keys()) | set(dki_a.keys()) | set(hedging_a.keys())
        speakers_b = set(sbi_b.keys()) | set(dki_b.keys()) | set(hedging_b.keys())
        common_speakers = speakers_a & speakers_b
        speakers_only_in_a = speakers_a - speakers_b
        speakers_only_in_b = speakers_b - speakers_a

        # SBI deltas
        delta_sbi: dict = {}
        delta_sbi_normalized: dict = {}
        delta_sbi_significant: dict = {}

        for speaker in common_speakers:
            pos_a = sbi_a.get(speaker)
            pos_b = sbi_b.get(speaker)

            if pos_a and pos_b:
                delta = pos_b.sbi - pos_a.sbi
                normalized = _normalize(delta, pos_a.sbi, _SBI_SCALE_FLOOR)
                significant = abs(normalized) >= input_data.sbi_threshold

                delta_sbi[speaker] = delta
                delta_sbi_normalized[speaker] = normalized
                delta_sbi_significant[speaker] = significant

        # DKI deltas
        delta_dki: dict = {}
        delta_dki_normalized: dict = {}
        delta_dki_significant: dict = {}

        for speaker in common_speakers:
            res_a = dki_a.get(speaker)
            res_b = dki_b.get(speaker)

            if res_a and res_b:
                delta = res_b.dki_score - res_a.dki_score
                normalized = _normalize(delta, res_a.dki_score, _DKI_SCALE_FLOOR)
                significant = abs(normalized) >= input_data.dki_threshold

                delta_dki[speaker] = delta
                delta_dki_normalized[speaker] = normalized
                delta_dki_significant[speaker] = significant

        # Risk delta
        delta_risk: float | None = None
        delta_risk_normalized: float | None = None
        delta_risk_significant = False

        if risk_a is not None and risk_b is not None:
            delta_risk = risk_b - risk_a
            delta_risk_normalized = _normalize(delta_risk, risk_a, _RISK_SCALE_FLOOR)
            delta_risk_significant = (
                abs(delta_risk_normalized) >= input_data.risk_threshold
            )

        # Hedging deltas
        delta_hedging: dict = {}
        delta_hedging_normalized: dict = {}
        delta_hedging_significant: dict = {}

        for speaker in common_speakers:
            rate_a = hedging_a.get(speaker, 0.0)
            rate_b = hedging_b.get(speaker, 0.0)

            delta = rate_b - rate_a
            normalized = _normalize(delta, rate_a, _HEDGING_SCALE_FLOOR)
            significant = abs(normalized) >= input_data.hedging_threshold

            delta_hedging[speaker] = delta
            delta_hedging_normalized[speaker] = normalized
            delta_hedging_significant[speaker] = significant

        # Speech act distribution deltas
        delta_speech_act: dict = {}
        for speaker in common_speakers:
            dist_a = speech_act_a.get(speaker, {})
            dist_b = speech_act_b.get(speaker, {})

            all_types = set(dist_a.keys()) | set(dist_b.keys())
            delta_dist: dict = {}

            for act_type in all_types:
                delta_dist[act_type] = dist_b.get(act_type, 0.0) - dist_a.get(
                    act_type, 0.0
                )

            # Fixed: Use abs() for magnitude
            most_changed = (
                max(delta_dist, key=lambda k: abs(delta_dist[k]))
                if delta_dist
                else None
            )
            change_mag = abs(delta_dist[most_changed]) if most_changed else 0.0

            delta_speech_act[speaker] = SpeechActDistributionDelta(
                speaker_id=speaker,
                distribution_a=dist_a,
                distribution_b=dist_b,
                delta_distribution=delta_dist,
                most_changed_type=most_changed,
                change_magnitude=change_mag,
            )

        # Narrative layer deltas
        delta_narrative: dict = {}
        for speaker in common_speakers:
            weights_a = narrative_a.get(speaker, {})
            weights_b = narrative_b.get(speaker, {})

            all_layers = set(weights_a.keys()) | set(weights_b.keys())
            delta_weights: dict = {}

            for layer in all_layers:
                delta_weights[layer] = weights_b.get(layer, 0.0) - weights_a.get(
                    layer, 0.0
                )

            # Fixed: Use abs() for magnitude
            max_layer = (
                max(delta_weights, key=lambda k: abs(delta_weights[k]))
                if delta_weights
                else None
            )
            dominant_change = (
                (max_layer, delta_weights[max_layer]) if max_layer else None
            )

            delta_narrative[speaker] = NarrativeLayerDelta(
                speaker_id=speaker,
                layer_weights_a=weights_a,
                layer_weights_b=weights_b,
                delta_weights=delta_weights,
                dominant_layer_change=dominant_change,
            )

        # Build significant changes list
        significant_changes: list[SignificantChange] = []

        for speaker, is_sig in delta_sbi_significant.items():
            if is_sig:
                significant_changes.append(
                    SignificantChange(
                        dimension="SBI",
                        speaker_id=speaker,
                        raw_delta=delta_sbi.get(speaker),
                        normalized_delta=delta_sbi_normalized.get(speaker),
                    )
                )

        for speaker, is_sig in delta_dki_significant.items():
            if is_sig:
                significant_changes.append(
                    SignificantChange(
                        dimension="DKI",
                        speaker_id=speaker,
                        raw_delta=delta_dki.get(speaker),
                        normalized_delta=delta_dki_normalized.get(speaker),
                    )
                )

        if delta_risk_significant:
            significant_changes.append(
                SignificantChange(
                    dimension="Risk",
                    speaker_id=None,
                    raw_delta=delta_risk,
                    normalized_delta=delta_risk_normalized,
                )
            )

        for speaker, is_sig in delta_hedging_significant.items():
            if is_sig:
                significant_changes.append(
                    SignificantChange(
                        dimension="Hedging",
                        speaker_id=speaker,
                        raw_delta=delta_hedging.get(speaker),
                        normalized_delta=delta_hedging_normalized.get(speaker),
                    )
                )

        return AnalysisDelta(
            session_a_id=session_a,
            session_b_id=session_b,
            delta_sbi=delta_sbi,
            delta_sbi_normalized=delta_sbi_normalized,
            delta_sbi_significant=delta_sbi_significant,
            delta_dki=delta_dki,
            delta_dki_normalized=delta_dki_normalized,
            delta_dki_significant=delta_dki_significant,
            delta_risk=delta_risk,
            delta_risk_normalized=delta_risk_normalized,
            delta_risk_significant=delta_risk_significant,
            delta_hedging=delta_hedging,
            delta_hedging_normalized=delta_hedging_normalized,
            delta_hedging_significant=delta_hedging_significant,
            delta_speech_act=delta_speech_act,
            delta_narrative=delta_narrative,
            significant_changes=significant_changes,
            speakers_in_a=frozenset(speakers_a),
            speakers_in_b=frozenset(speakers_b),
            common_speakers=frozenset(common_speakers),
            speakers_only_in_a=frozenset(speakers_only_in_a),
            speakers_only_in_b=frozenset(speakers_only_in_b),
        )

    async def _get_cached_narrative(self, delta: AnalysisDelta, language: str) -> str:
        import hashlib
        import json

        delta_key = hashlib.sha256(
            json.dumps(
                {
                    "a": delta.session_a_id,
                    "b": delta.session_b_id,
                    "changes": sorted([str(c) for c in delta.significant_changes]),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        cache_key = (delta_key, language)
        if cache_key not in self._narrative_cache:
            self._narrative_cache[cache_key] = await self._generate_narrative(
                delta, language
            )
        return self._narrative_cache[cache_key]

    async def _generate_narrative(self, delta: AnalysisDelta, language: str) -> str:
        prompt = self._build_narrative_prompt(delta, language)
        response = await self._llm_service.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000,
        )
        return response.strip()

    def _build_narrative_prompt(self, delta: AnalysisDelta, language: str) -> str:
        base_prompt = f"""You are an expert diplomatic analyst. Compare two diplomatic sessions and summarize the key changes.

Session A ID: {delta.session_a_id}
Session B ID: {delta.session_b_id}

"""

        if delta.common_speakers:
            base_prompt += (
                f"Common Speakers: {', '.join(sorted(delta.common_speakers))}\n"
            )

        if delta.speakers_only_in_a:
            base_prompt += f"Speakers only in Session A: {', '.join(sorted(delta.speakers_only_in_a))}\n"

        if delta.speakers_only_in_b:
            base_prompt += f"Speakers only in Session B: {', '.join(sorted(delta.speakers_only_in_b))}\n"

        base_prompt += "\n=== SIGNIFICANT CHANGES ===\n"

        if delta.significant_changes:
            for change in delta.significant_changes:
                base_prompt += f"- {change.dimension}"
                if change.speaker_id:
                    base_prompt += f" ({change.speaker_id})"
                if change.raw_delta is not None:
                    base_prompt += f": {change.raw_delta:.3f}"
                if change.normalized_delta is not None:
                    base_prompt += f" (normalized: {change.normalized_delta:.3f})"
                base_prompt += "\n"
        else:
            base_prompt += "No significant changes detected.\n"

        base_prompt += (
            f"\nMost Drifted Speaker: {delta.most_drifted_speaker or 'N/A'}\n"
        )
        base_prompt += f"Most Drifted Dimension: {delta.most_drifted_dimension}\n"

        base_prompt += f"""
Provide a concise 3-4 paragraph summary in {language} that:
1. Highlights the most important changes
2. Identifies which speaker(s) shifted the most
3. Explains what dimensions changed most significantly
4. Provides context on whether these changes represent escalation or de-escalation

Focus on actionable insights for diplomatic analysts.
"""
        return base_prompt

    def _extract_key_insights(self, delta: AnalysisDelta) -> list[str]:
        insights: list[str] = []

        if delta.most_drifted_speaker:
            insights.append(
                f"Speaker '{delta.most_drifted_speaker}' shows the highest aggregate drift"
            )

        insights.append(
            f"'{delta.most_drifted_dimension}' dimension shows the highest aggregate change"
        )

        if delta.delta_risk_significant:
            direction = (
                "increased"
                if delta.delta_risk and delta.delta_risk > 0
                else "decreased"
            )
            insights.append(f"Overall risk score {direction} significantly")

        if delta.speakers_only_in_a:
            insights.append(
                f"Speakers exited: {', '.join(sorted(delta.speakers_only_in_a))}"
            )
        if delta.speakers_only_in_b:
            insights.append(
                f"Speakers entered: {', '.join(sorted(delta.speakers_only_in_b))}"
            )

        # Fixed: Use .get() to avoid KeyError
        sbi_changes = [
            (speaker, norm_delta)
            for speaker, is_sig in delta.delta_sbi_significant.items()
            if is_sig
            if (norm_delta := delta.delta_sbi_normalized.get(speaker)) is not None
        ]
        sbi_changes.sort(key=lambda x: abs(x[1]), reverse=True)

        if sbi_changes:
            top_sbi = sbi_changes[0]
            insights.append(
                f"Largest SBI shift: {top_sbi[0]} ({top_sbi[1]:.3f} normalized)"
            )

        return insights[:5]

    def _assess_risk(self, delta: AnalysisDelta) -> RiskAssessmentLevel:
        if delta.delta_risk_significant:
            if delta.delta_risk and delta.delta_risk > 0:
                return RiskAssessmentLevel.HIGH_RISK_ESCALATION
            return RiskAssessmentLevel.RISK_DEESCALATION
        if delta.total_significant_changes > 5:
            return RiskAssessmentLevel.MODERATE_CONCERN
        return RiskAssessmentLevel.STABLE

    def _generate_recommendation(self, delta: AnalysisDelta) -> str:
        if delta.delta_risk_significant and delta.delta_risk and delta.delta_risk > 0:
            return "Monitor closely for escalation signals. Consider immediate diplomatic engagement."

        if delta.total_significant_changes == 0:
            return "No immediate action required. Continue routine monitoring."

        if delta.most_drifted_speaker:
            return f"Focus diplomatic attention on {delta.most_drifted_speaker} due to significant position shift."

        return "Review detailed delta metrics for specific areas of concern."
