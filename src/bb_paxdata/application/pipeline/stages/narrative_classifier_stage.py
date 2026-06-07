# src/bb_paxdata/application/pipeline/stages/narrative_classifier_stage.py
from typing import Any, Dict, List, Optional

import structlog
from bb_paxdata.application.domain.enums.country_enums import NarrativeLayer
from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.services.narrative_salience_tracker import (
    NarrativeSalienceTracker,
)

logger = structlog.get_logger(__name__)


class NarrativeClassifierStage:
    """Performs Narrative Layer Classification & Salience Tracking on analyzed segments."""

    def __init__(self, tracker: NarrativeSalienceTracker) -> None:
        self.tracker = tracker
        self._log = logger.bind(stage="narrative_classification")

        # Rule-based vocabulary hooks (FINDING A-04 baseline)
        self.narrative_keywords = {
            NarrativeLayer.SYSTEM: [
                "world order",
                "international community",
                "multipolar",
                "unipolar",
                "rules-based",
                "hegemony",
                "global governance",
                "united nations",
                "sovereign equality",
                "coalition",
            ],
            NarrativeLayer.IDENTITY: [
                "national interest",
                "historic duty",
                "defender",
                "mediator",
                "reliable partner",
                "sovereignty",
                "our nation",
                "peace-loving",
                "aggressor state",
                "colonial legacy",
            ],
            NarrativeLayer.ISSUE: [
                "border conflict",
                "ceasefire violation",
                "humanitarian passage",
                "gas pipeline",
                "grain corridor",
                "terrorist threat",
                "bilateral trade",
                "customs dispute",
                "sanctions",
            ],
        }

    def classify_segment_layer(self, text: str) -> Optional[NarrativeLayer]:
        """Returns None if no narrative layer signal is detected (FINDING P-06)."""
        normalized_text = text.lower()
        scores = {layer: 0 for layer in NarrativeLayer}

        for layer, keywords in self.narrative_keywords.items():
            for kw in keywords:
                if kw in normalized_text:
                    scores[layer] += 1

        if sum(scores.values()) == 0:
            return None  # No narrative signal

        return max(scores, key=lambda k: scores[k])

    def extract_narrative_target(
        self, text: str, entities: List[Dict[str, Any]], self_actor: str
    ) -> Optional[str]:
        """Resolves target of the narrative, prioritizing named entities (GPE/ORG) from NER."""
        for ent in entities:
            ent_label = ent.get("label", "")
            ent_text = ent.get("text", "")
            if ent_label in ("GPE", "ORG") and ent_text.lower() != self_actor.lower():
                return ent_text
        return None

    def process_analysis(self, analysis: Analysis) -> Analysis:
        """Enriches the incoming Analysis object with narrative layers."""
        if not analysis.source_text:
            return analysis

        # 1. Classify Narrative Layer
        predicted_layer = self.classify_segment_layer(analysis.source_text)
        if predicted_layer is None:
            return analysis  # Skip enrichment when predicted_layer is None

        # 2. Extract Narrative Target
        self_actor = analysis.speaker_id or "unknown"
        target_actor = self.extract_narrative_target(
            analysis.source_text, analysis.entities, self_actor
        )

        # 3. Calculate Base Frequency heuristic
        kw_hits = sum(
            1
            for kw in self.narrative_keywords[predicted_layer]
            if kw in analysis.source_text.lower()
        )
        base_frequency = 1 + kw_hits

        # 4. Compute Salience utilizing A03 & A04 inputs
        salience = self.tracker.compute_salience(
            base_frequency=base_frequency,
            frame_salience=analysis.frame_salience,
            speech_act=analysis.speech_act,
        )

        # 5. Pack into Analysis model bilateral_metrics list
        updated_bilateral = []
        for sentiment in analysis.bilateral_metrics or []:
            # Resolve target mapping: check if Greece/Turkey/etc matches the target actor
            if target_actor and sentiment.to_country.lower() == target_actor.lower():
                updated_bilateral.append(
                    sentiment.model_copy(
                        update={
                            "narrative_layer": predicted_layer,
                            "narrative_target_actor": target_actor,
                            "narrative_salience": salience,
                        }
                    )
                )
            else:
                updated_bilateral.append(sentiment)

        return analysis.model_copy(update={"bilateral_metrics": updated_bilateral})
