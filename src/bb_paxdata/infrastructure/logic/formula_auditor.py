"""FormulaAuditor class to perform deterministic logic and math checks on pipeline outputs."""

from typing import Any

# Politeness Lexicon from scripts/politeness_signals.txt
POLITENESS_SIGNALS = {
    "face_threat": {
        "direct_criticism": [
            "failed",
            "irresponsible",
            "unacceptable",
            "wrong",
            "mistake",
            "error",
            "negligent",
            "incompetent",
        ],
        "direct_demand": [
            "must",
            "have to",
            "are required",
            "demand",
            "insist",
            "non-negotiable",
            "immediate action",
        ],
        "blame": [
            "caused by",
            "responsible for",
            "due to their",
            "fault of",
            "brought upon",
            "led to",
            "created by",
        ],
    },
    "face_save": {
        "hedging": [
            "perhaps",
            "i believe",
            "in my view",
            "with respect",
            "with due respect",
            "if i may",
            "allow me to",
        ],
        "compliment": [
            "appreciate",
            "commend",
            "value",
            "recognize the efforts",
            "congratulate",
            "thank",
            "acknowledge",
            "excellent",
        ],
        "indirect_request": [
            "would be helpful",
            "it would be beneficial",
            "consider",
            "might want to",
            "could explore",
            "perhaps worth",
        ],
    },
}

# Risk Signals and weights from RiskService
RISK_SIGNALS = [
    "unacceptable",
    "red line",
    "cannot tolerate",
    "will not accept",
    "serious consequences",
    "escalate",
    "retaliate",
    "breakdown",
    "collapse",
    "ultimatum",
    "provocation",
    "violation",
    "condemn",
    "denounce",
    "reject outright",
    "military option",
    "unprovoked war",
    "decisive actions",
    "deep strikes",
    "imposed solutions",
    "dismantlement",
    "zero-sum",
    "paralyze",
    "paralyzed",
    "weaponized",
    "breached",
]

RISK_SIGNAL_WEIGHTS = {
    "red line": 3,
    "ultimatum": 3,
    "unacceptable": 3,
    "military option": 3,
    "unprovoked war": 3,
    "escalate": 2,
    "retaliate": 2,
    "serious consequences": 2,
    "decisive actions": 2,
    "deep strikes": 2,
    "cannot tolerate": 2,
    "will not accept": 2,
    "reject outright": 2,
}


class FormulaAuditor:
    """Audits mathematical and logical constraints of PAXDATA metrics."""

    def __init__(self, tolerance: float = 0.01) -> None:
        self.tolerance = tolerance

    def _create_log(
        self,
        run_id: str,
        entity_type: str,
        entity_id: str,
        formula_name: str,
        expected_constraint: str,
        actual_value: float,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "formula_name": formula_name,
            "expected_constraint": expected_constraint,
            "actual_value": actual_value,
            "status": status,
            "details": details,
        }

    def audit_sentence(self, run_id: str, sentence: Any) -> list[dict[str, Any]]:
        """Audits a single sentence ORM model or domain model."""
        logs = []
        text = getattr(sentence, "text", "") or ""
        text_lower = text.lower()

        sent_id = str(
            getattr(sentence, "sent_id", None)
            or getattr(sentence, "id", "unknown_sent")
        )

        # 1. VADER Compound Score bounds check [-1.0, 1.0]
        vader_compound = float(getattr(sentence, "vader_compound", 0.0) or 0.0)
        status_vader = "PASS" if -1.0 <= vader_compound <= 1.0 else "FAIL"
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="sentence",
                entity_id=sent_id,
                formula_name="vader_compound",
                expected_constraint="[-1.0, 1.0]",
                actual_value=vader_compound,
                status=status_vader,
                details={"msg": "VADER compound bounds check"},
            )
        )

        # 2. Negation Aware Diplo bounds check [-1.0, 1.0]
        # In DB, it is negation_aware_diplo or diplo_compound
        neg_diplo_val = getattr(sentence, "negation_aware_diplo", None)
        if neg_diplo_val is None:
            neg_diplo_val = getattr(sentence, "diplo_compound", 0.0)
        neg_diplo = float(neg_diplo_val or 0.0)
        status_neg = "PASS" if -1.0 <= neg_diplo <= 1.0 else "FAIL"
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="sentence",
                entity_id=sent_id,
                formula_name="negation_aware_diplo",
                expected_constraint="[-1.0, 1.0]",
                actual_value=neg_diplo,
                status=status_neg,
                details={"msg": "Negation-aware Diplo bounds check"},
            )
        )

        # 3. Emotion Category Threshold Check
        emotion_cat = getattr(sentence, "emotion_category", None) or getattr(
            sentence, "sentiment", None
        )
        if emotion_cat:
            # Normalize enum to string
            if hasattr(emotion_cat, "value"):
                emotion_str = emotion_cat.value
            else:
                emotion_str = str(emotion_cat)

            expected_cat = "neutral_cautious"
            if neg_diplo <= -0.40:
                expected_cat = "confrontational"
            elif neg_diplo <= -0.10:
                expected_cat = "concerned"
            elif neg_diplo < 0.10:
                expected_cat = "neutral_cautious"
            elif neg_diplo < 0.35:
                expected_cat = "constructive"
            else:
                expected_cat = "cooperative"

            status_emo = "PASS" if emotion_str == expected_cat else "FAIL"
            logs.append(
                self._create_log(
                    run_id=run_id,
                    entity_type="sentence",
                    entity_id=sent_id,
                    formula_name="emotion_category_alignment",
                    expected_constraint=f"== '{expected_cat}' based on score {neg_diplo}",
                    actual_value=0.0,
                    status=status_emo,
                    details={
                        "actual_category": emotion_str,
                        "expected_category": expected_cat,
                    },
                )
            )

        # 4. Hedging Score Verification
        # In build.py:
        # _hedging_keywords = count words in text
        # _hedging_score = min(1.0, _hedging_keywords * 0.25)
        # Note: If there's a bug in build.py where it checked _risk_sigs, we compare against the CORRECT calculation.
        hedging_keywords_correct = sum(
            1
            for kw in [
                "perhaps",
                "maybe",
                "might",
                "could",
                "possibly",
                "belki",
                "muhtemelen",
                "olabilir",
                "sanırım",
            ]
            if kw in text_lower
        )
        expected_hedge = min(1.0, hedging_keywords_correct * 0.25)
        actual_hedge = float(getattr(sentence, "hedging_score", 0.0) or 0.0)

        status_hedge = (
            "PASS" if abs(expected_hedge - actual_hedge) < self.tolerance else "FAIL"
        )
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="sentence",
                entity_id=sent_id,
                formula_name="hedging_score",
                expected_constraint=f"== {expected_hedge:.3f}",
                actual_value=actual_hedge,
                status=status_hedge,
                details={
                    "recalculated_hedge": expected_hedge,
                    "actual_hedge": actual_hedge,
                    "detected_keyword_count": hedging_keywords_correct,
                },
            )
        )

        # 5. Politeness Ratio Verification
        # fta = face_threat_count, fts = face_save_count
        # politeness_ratio = fts / (fts + fta + 1) OR 0.5 if both 0 (depending on script/build implementation)
        # In build.py, it is face_save / (face_save + face_threat + 1).
        face_save_correct = sum(
            1
            for k in [
                "please",
                "lütfen",
                "thank",
                "teşekkür",
                "respectfully",
                "saygıyla",
            ]
            if k in text_lower
        )
        face_threat_correct = sum(
            1
            for k in ["demand", "threat", "ultimatum", "warn", "tehdit", "talep"]
            if k in text_lower
        )
        expected_polit = face_save_correct / (
            face_save_correct + face_threat_correct + 1
        )
        actual_polit = float(getattr(sentence, "politeness_ratio", 0.0) or 0.0)

        status_polit = (
            "PASS" if abs(expected_polit - actual_polit) < self.tolerance else "FAIL"
        )
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="sentence",
                entity_id=sent_id,
                formula_name="politeness_ratio",
                expected_constraint=f"== {expected_polit:.3f}",
                actual_value=actual_polit,
                status=status_polit,
                details={
                    "recalculated_politeness": expected_polit,
                    "actual_politeness": actual_polit,
                    "recalculated_face_save": face_save_correct,
                    "recalculated_face_threat": face_threat_correct,
                    "actual_face_save": getattr(sentence, "face_save_count", 0),
                    "actual_face_threat": getattr(sentence, "face_threat_count", 0),
                },
            )
        )

        return logs

    def audit_segment(
        self, run_id: str, segment: Any, sentences: list[Any]
    ) -> list[dict[str, Any]]:
        """Audits segment level aggregates (SBI, DKI, Risk)."""
        logs: list[dict[str, Any]] = []
        seg_id = str(
            getattr(segment, "seg_id", None) or getattr(segment, "id", "unknown_seg")
        )

        if not sentences:
            return logs

        # 1. SBI Verification
        # avg_power = average of power level of speaker or segment sentences
        # avg_demand_weight = average of demand weights
        # avg_risk = average of sentence risk scores
        power_levels = []
        demand_weights = []
        risk_scores = []

        # Find power level of segment speaker
        speaker_power = 5.0
        if (
            hasattr(segment, "power_level")
            and segment.power_level is not None
            and segment.power_level != 0
        ):
            speaker_power = float(segment.power_level)
        else:
            # Avoid triggering lazy load if not loaded
            try:
                from sqlalchemy import inspect

                state = inspect(segment)
                if "speaker" in state.unloaded:
                    speaker = None
                else:
                    speaker = getattr(segment, "speaker", None)
            except Exception:
                speaker = getattr(segment, "speaker", None)

            if speaker is not None and hasattr(speaker, "power_level"):
                speaker_power = float(speaker.power_level)
            elif hasattr(segment, "power_level") and segment.power_level is not None:
                speaker_power = float(segment.power_level)

        for sent in sentences:
            # Estimate demand weight
            stxt = getattr(sent, "text", "").lower()
            d_weight = 0.5
            if any(w in stxt for w in ["must", "require", "demand", "insist"]):
                d_weight = 0.9
            elif any(w in stxt for w in ["should", "ought", "recommend"]):
                d_weight = 0.7
            elif any(w in stxt for w in ["suggest", "propose", "consider"]):
                d_weight = 0.5
            demand_weights.append(d_weight)

            # Recalculate risk score for sentence
            detected_signals = [sig for sig in RISK_SIGNALS if sig in stxt]
            risk_val = float(
                min(
                    10.0,
                    sum(RISK_SIGNAL_WEIGHTS.get(sig, 1) for sig in detected_signals),
                )
            )
            risk_scores.append(risk_val)
            power_levels.append(speaker_power)

        avg_power = sum(power_levels) / len(power_levels)
        avg_demand = sum(demand_weights) / len(demand_weights)
        avg_risk = sum(risk_scores) / len(risk_scores)

        # Expected SBI = (avg_power * avg_demand) / 2.0 + avg_risk
        expected_sbi = (avg_power * avg_demand) / 2.0 + avg_risk
        actual_sbi = float(getattr(segment, "sbi_score", 0.0) or 0.0)

        status_sbi = (
            "PASS" if abs(expected_sbi - actual_sbi) < self.tolerance else "FAIL"
        )
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="segment",
                entity_id=seg_id,
                formula_name="sbi_score",
                expected_constraint=f"== {expected_sbi:.3f}",
                actual_value=actual_sbi,
                status=status_sbi,
                details={
                    "recalculated_sbi": expected_sbi,
                    "actual_sbi": actual_sbi,
                    "avg_power": avg_power,
                    "avg_demand": avg_demand,
                    "avg_risk": avg_risk,
                },
            )
        )

        # 2. DKI Verification
        # norm_diplo = max(0, min(1, (5.0 - avg_risk) / 5.0)) or equivalent normalization in RiskService
        # Let's mirror RiskService._normalize_value: max(0.0, min(1.0, (val - min) / (max - min)))
        def norm_val(val: float, min_v: float = 0.0, max_v: float = 10.0) -> float:
            if max_v <= min_v:
                return 0.0
            return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))

        norm_diplo = norm_val(5.0 - avg_risk)
        norm_risk = norm_val(avg_risk)
        norm_demand = min(avg_demand, 1.0)
        norm_manip = min(1.0, max(0.0, (avg_demand - 0.5) * 2.0))

        base_dki = (
            norm_diplo * 0.4
            + (1.0 - norm_risk) * 0.3
            + norm_demand * 0.2
            + (1.0 - norm_manip) * 0.1
        )
        expected_dki = (base_dki * 2.0) - 1.0
        actual_dki = float(getattr(segment, "dki_score", 0.0) or 0.0)

        status_dki = (
            "PASS" if abs(expected_dki - actual_dki) < self.tolerance else "FAIL"
        )
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="segment",
                entity_id=seg_id,
                formula_name="dki_score",
                expected_constraint=f"== {expected_dki:.3f}",
                actual_value=actual_dki,
                status=status_dki,
                details={
                    "recalculated_dki": expected_dki,
                    "actual_dki": actual_dki,
                    "norm_diplo": norm_diplo,
                    "norm_risk": norm_risk,
                    "norm_demand": norm_demand,
                    "norm_manip": norm_manip,
                },
            )
        )

        # 3. Segment Risk Score Recalculation Check
        # final_risk_score = avg_risk * 0.4 + contextual_risk * 0.3 + (sbi / 10) * 0.3
        # Let's recalculate contextual_risk
        # base_score from risk_detect on full text
        full_text = " ".join([getattr(s, "text", "") for s in sentences])
        full_text_lower = full_text.lower()
        detected_signals_full = [sig for sig in RISK_SIGNALS if sig in full_text_lower]
        base_score_full = float(
            min(
                10,
                sum(RISK_SIGNAL_WEIGHTS.get(sig, 1) for sig in detected_signals_full),
            )
        )

        # NER multiplier:
        # Check if there are ORG, GPE, PERSON entities in sentences
        has_gpe_org = False
        has_person = False
        for sent in sentences:
            gpe = getattr(sent, "entities_gpe", None)
            org = getattr(sent, "entities_org", None)
            person = getattr(sent, "entities_person", None)
            if gpe or org:
                has_gpe_org = True
            if person:
                has_person = True

        multiplier = 1.0
        if detected_signals_full:
            if has_gpe_org:
                multiplier = 1.5
            elif has_person:
                multiplier = 1.2

        contextual_risk = min(10.0, round(base_score_full * multiplier))
        expected_risk = (
            avg_risk * 0.4 + contextual_risk * 0.3 + (actual_sbi / 10.0) * 0.3
        )
        actual_risk = float(getattr(segment, "risk_score", 0.0) or 0.0)

        # In DB, segment.risk_score is integer
        status_risk = (
            "PASS" if abs(expected_risk - actual_risk) < 1.0 else "FAIL"
        )  # Allow 1.0 tolerance due to rounding/clamping differences
        logs.append(
            self._create_log(
                run_id=run_id,
                entity_type="segment",
                entity_id=seg_id,
                formula_name="risk_score",
                expected_constraint=f"== {expected_risk:.3f}",
                actual_value=actual_risk,
                status=status_risk,
                details={
                    "recalculated_risk": expected_risk,
                    "actual_risk": actual_risk,
                    "contextual_risk": contextual_risk,
                    "avg_risk": avg_risk,
                },
            )
        )

        return logs
