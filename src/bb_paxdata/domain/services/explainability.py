from __future__ import annotations

from typing import cast

from bb_paxdata.domain.models.dependency import DependencyTriple
from bb_paxdata.domain.models.explanation import SentenceExplanation, TokenContribution
from bb_paxdata.domain.services.explanation_templates import TEMPLATES
from bb_paxdata.domain.services.sentiment_service import SentimentService
from bb_paxdata.domain.services.token_attribution import token_level_attribution


class ExplainabilityService:
    """
    Generates automated, reason-based explanations for analytical scores.
    """

    def __init__(self, sentiment_service: SentimentService | None = None):
        self.sentiment_service = sentiment_service or SentimentService()

    def explain_sentence(
        self,
        sent_id: str,
        text: str,
        sentiment_score: float,
        risk_score: int,
        triples: list[DependencyTriple] | None = None,
        ai_score: float | None = None,
        power_level: int = 5,
    ) -> SentenceExplanation:
        """
        Generate a comprehensive explanation for a single sentence.
        """

        # 1. Token Level Attribution
        attributions = token_level_attribution(text, self.sentiment_service)

        # 2. Sentiment Explanation
        sentiment_exp = self._generate_sentiment_explanation(
            text, sentiment_score, attributions
        )

        # 3. Risk Explanation
        risk_exp = self._generate_risk_explanation(
            risk_score, power_level, attributions
        )

        # 4. Grammatical Explanation (if triples provided)
        gram_exp = self._generate_grammatical_explanation(triples)

        # 5. Discrepancy Explanation (if AI score provided)
        disc_exp = None
        if ai_score is not None:
            disc_exp = self._generate_discrepancy_explanation(sentiment_score, ai_score)

        # 6. Executive Summary
        exec_summary = (
            f"Bu cumle {sentiment_score:.2f} duygu ve {risk_score} risk puanina "
            f"sahiptir. "
        )
        if risk_score > 7:
            exec_summary += "Yuksek riskli bir diplomatik sinyal icermektedir."
        elif sentiment_score < -0.4:
            exec_summary += "Belirgin bir olumsuz tutum sergilemektedir."
        else:
            exec_summary += "Genel olarak dengeli bir yapidadir."

        return SentenceExplanation(
            sent_id=sent_id,
            sentiment_explanation=sentiment_exp,
            risk_explanation=risk_exp,
            grammatical_explanation=gram_exp,
            discrepancy_explanation=disc_exp,
            executive_summary=exec_summary,
            token_attributions=attributions,
        )

    def _generate_sentiment_explanation(
        self, text: str, score: float, attributions: list[TokenContribution]
    ) -> str:
        """Generate explanation for the sentiment score."""
        top_contribs = sorted(
            attributions, key=lambda x: abs(x.sentiment_contrib), reverse=True
        )
        THRESHOLD = 0.05
        significant = [c for c in top_contribs if abs(c.sentiment_contrib) > THRESHOLD]

        if not significant:
            return "Cumlede belirgin bir duygusal yuklu kelime bulunamadi."

        primary = significant[0]
        if "olumsuzlandigi" in primary.explanation:
            return cast(str, TEMPLATES["sentiment_negation"]).format(
                keyword=primary.token,
                negation="olumsuzluk eki/kelimesi",  # Simplified
                score=score,
            )


        return cast(str, TEMPLATES["lexicon_match"]).format(
            token=primary.token, score=primary.sentiment_contrib, category="Duygu"
        )

    def _generate_risk_explanation(
        self, risk_score: int, power_level: int, attributions: list[TokenContribution]
    ) -> str:
        """Generate explanation for the risk score."""
        RISK_THRESHOLD = 7
        if risk_score > RISK_THRESHOLD:
            return cast(str, TEMPLATES["risk_high_power"]).format(
                power=power_level, signal="yüksek riskli kelimeler", severity="kritik"
            )
        if power_level > RISK_THRESHOLD:
            return cast(str, TEMPLATES["power_level_impact"]).format(power=power_level)

        return "Belirgin bir diplomatik risk tespit edilmedi."

    def _generate_grammatical_explanation(
        self, triples: list[DependencyTriple] | None
    ) -> str | None:
        """Generate explanation based on SVO triples."""
        if not triples:
            return None

        t = triples[0]
        return cast(str, TEMPLATES["dependency_actor_action"]).format(
            subject=t.subject_resolved or t.subject_raw,
            verb=t.verb_lemma,
            object=t.object_resolved or t.object_raw,
        )

    def _generate_discrepancy_explanation(
        self, formula_score: float, ai_score: float
    ) -> str:
        """Generate explanation for difference between AI and Formula."""
        diff = abs(formula_score - ai_score)
        return cast(str, TEMPLATES["discrepancy_sentiment"]).format(
            ai=ai_score, formula=formula_score, diff=diff
        )
