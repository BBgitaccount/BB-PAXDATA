"""Topic analysis service with TF-IDF enhancement.

This service analyzes topics in diplomatic discourse using keyword matching
and optional TF-IDF enhancement. It calculates topic scores, identifies the
dominant topic, and measures topic specificity using Shannon entropy.
"""

import math
from collections import defaultdict
from typing import Any, ClassVar

from ...application.protocols import BaseService, TopicAnalysis, TopicServiceProtocol
from ...domain.enums import TopicCategory


class TopicService(BaseService, TopicServiceProtocol):
    """Service for topic analysis with TF-IDF enhancement."""

    # Topic keyword sets (from DatabaseBuilder_v5_8.py)
    TOPICS: ClassVar[dict[str, list[str]]] = {
        "BM_Reformu": [
            "united nations",
            "security council",
            "reform",
            "veto",
            "charter",
            "secretary-general",
            "general assembly",
            "multilateral",
            "league of nations",
            "representation gap",
            "world is bigger than five",
            "resolution",
            "chapter 7",
            "unifil",
            "osce",
            "international legitimacy",
            "systemic crisis",
        ],
        "Güvenlik_Çatışma": [
            "war",
            "conflict",
            "military",
            "aggression",
            "nuclear",
            "attack",
            "threat",
            "tension",
            "weapons",
            "ceasefire",
            "hostilities",
            "proxy war",
            "cyberattack",
            "drone",
            "ballistic",
            "bombing",
            "atrocity",
            "escalation",
            "armed forces",
            "shadow fleet",
            "strikes",
            "capabilities",
        ],
        "Ekonomi_Ticaret_Enerji": [
            "trade",
            "economic",
            "economy",
            "growth",
            "connectivity",
            "investment",
            "infrastructure",
            "sanction",
            "financial",
            "supply chain",
            "corridor",
            "oil",
            "gas",
            "pipeline",
            "lng",
            "macrofinancial",
            "prosperity",
            "welfare",
            "production",
            "development road",
            "energy security",
            "eurobond",
            "dedollarization",
        ],
        "Liderlik_Yönetim": [
            "leadership",
            "governance",
            "democracy",
            "rule of law",
            "authoritarianism",
            "accountability",
            "institution",
            "integrity",
            "transparency",
            "proactive",
            "anticipatory",
            "decision-makers",
            "regime",
            "constitution",
            "elections",
            "parliament",
            "sovereign",
            "political will",
            "radical inclusion",
        ],
        "Diplomatik_Çözüm": [
            "diplomacy",
            "negotiation",
            "dialogue",
            "preventive",
            "peace",
            "cooperation",
            "bridge",
            "multilateralism",
            "inclusive",
            "mediation",
            "reconciliation",
            "consensus",
            "non-aggression",
            "truce",
            "normalization",
            "de-escalation",
            "trust building",
            "strategic restraint",
            "regional ownership",
            "partnership",
            "shared responsibility",
            "win-win",
            "peaceful coexistence",
        ],
        "AB_NATO_Genişleme": [
            "european union",
            "eu",
            "nato",
            "enlargement",
            "balkans",
            "candidate",
            "copenhagen",
            "accession",
            "membership",
            "strategic autonomy",
            "transatlantic",
            "western balkans",
            "euro-atlantic",
            "collective defense",
            "burden sharing",
            "deterrence",
        ],
        "Yapay_Zeka_Teknoloji": [
            "artificial intelligence",
            "technology",
            "digital",
            "cyber",
            "disinformation",
            "hybrid",
            "data",
            "innovation",
            "tech",
            "digitalization",
            "drone wall",
            "network",
            "algorithms",
            "automation",
            "surveillance",
        ],
        "Orta_Güçler_Bölgesel": [
            "middle power",
            "türkiye",
            "turkey",
            "kazakhstan",
            "georgia",
            "caucasus",
            "regional",
            "medium-sized",
            "global south",
            "brics",
            "eaeu",
            "sco",
            "central asia",
            "asean",
            "organization of turkic states",
        ],
        "Gazze_Filistin_İsrail": [
            "gaza",
            "palestine",
            "palestinian",
            "ceasefire",
            "occupation",
            "humanitarian",
            "siege",
            "west bank",
            "two-state",
            "board of peace",
            "unrwa",
            "hamas",
            "israel",
            "apartheid",
            "genocide",
            "settlements",
            "arab peace initiative",
        ],
        "Ukrayna_Rusya": [
            "ukraine",
            "russia",
            "ukrainian",
            "russian",
            "donbas",
            "crimea",
            "sovereignty",
            "territorial",
            "special military operation",
            "kyiv",
            "moscow",
            "patriot",
            "zelenskyy",
            "putin",
            "black sea",
            "druzhba",
        ],
        "Suriye_Geçiş": [
            "syria",
            "syrian",
            "sdf",
            "transition",
            "demography",
            "return",
            "reconstruction",
            "damascus",
            "al-assad",
            "constitutional",
            "integration",
            "four seas project",
        ],
        "Afrika_Ortadoğu": [
            "yemen",
            "houthis",
            "somalia",
            "ethiopia",
            "sierra leone",
            "lebanon",
            "hezbollah",
            "iran",
            "gulf",
            "red sea",
            "ecowas",
            "au",
            "african union",
            "litani river",
            "strait of hormuz",
            "abraham accords",
            "sudan",
        ],
        "İnsani_Yardım_Haklar": [
            "humanitarian",
            "refugee",
            "displacement",
            "aid",
            "civilian",
            "famine",
            "relief",
            "migration",
            "asylum",
            "malnutrition",
            "human rights",
            "minority rights",
            "dignity",
            "justice",
            "equality",
            "orphans",
            "starvation",
            "wfp",
            "unicef",
        ],
        "Çok_Kutupluluk_Düzen": [
            "multipolarity",
            "polycentric",
            "global order",
            "rules-based",
            "hegemon",
            "unipolar",
            "bipolar",
            "hegemony",
            "international law",
            "world order",
            "diversity",
            "global majority",
            "status quo",
            "imperial",
        ],
        "Risk_Kırılım": [
            "crisis",
            "escalation",
            "breakdown",
            "collapse",
            "failed",
            "fragile",
            "rupture",
            "deterioration",
            "instability",
            "red line",
            "unacceptable",
            "ultimatum",
            "provocation",
            "violation",
            "retaliate",
            "condemn",
            "denounce",
        ],
    }

    # Keyword weights for TF-IDF calculation
    KW_WEIGHTS: ClassVar[dict[str, float]] = {}

    # TF-IDF availability flag
    HAS_TFIDF: ClassVar[bool] = True

    def __init__(self) -> None:
        """Initialize the topic service and calculate keyword weights."""
        super().__init__()
        self._calculate_keyword_weights()

    def analyze(self, text: str, **kwargs: Any) -> Any:
        """Analyze topics in text.

        Args:
            text: The text to analyze
            **kwargs: Additional analysis parameters

        Returns:
            TopicAnalysis containing topic scores and dominant topic
        """
        tfidf_keywords = kwargs.get("tfidf_keywords")
        return self.analyze_topics(text, tfidf_keywords)

    def _calculate_keyword_weights(self) -> None:
        """Calculate keyword weights using smoothed IDF."""
        n_topics = len(self.TOPICS)

        # Count keyword frequency across topics
        kw_doc_freq: dict[str, int] = defaultdict(int)
        for keywords in self.TOPICS.values():
            for kw in keywords:
                kw_doc_freq[kw] += 1

        # Calculate weights
        for keywords in self.TOPICS.values():
            for kw in keywords:
                # Smoothed IDF: log(1 + (N_topics / doc_freq))
                idf = math.log(1 + (n_topics / kw_doc_freq[kw]))
                # Phrase bonus for multi-word terms
                phrase_bonus = 1 + 0.35 * (len(kw.split()) - 1)
                self.KW_WEIGHTS[kw] = idf * phrase_bonus

    def weighted_topic_score(
        self, text: str, tfidf_keywords: list[str] | None = None
    ) -> dict[str, float]:
        """Calculate weighted topic scores for text.

        Args:
            text: Text to analyze
            tfidf_keywords: Optional TF-IDF keywords for enhancement

        Returns:
            Dictionary mapping topic names to scores
        """
        text_lower = text.lower()
        topic_scores = {}

        for topic_name, keywords in self.TOPICS.items():
            score = 0.0
            matched_keywords = []

            for kw in keywords:
                if kw in text_lower:
                    # Base weighted score
                    weight = self.KW_WEIGHTS.get(kw, 1.0)
                    score += weight
                    matched_keywords.append(kw)

            # TF-IDF bonus if provided
            if tfidf_keywords:
                tfidf_bonus = 0.0
                for kw in matched_keywords:
                    if kw in tfidf_keywords:
                        tfidf_bonus += 2.0  # Bonus for TF-IDF keywords

                if tfidf_bonus > 0:
                    # Apply TF-IDF bonus: base + tfidf_bonus / sqrt(len(kws))
                    tfidf_factor = tfidf_bonus / math.sqrt(len(matched_keywords))
                    score += tfidf_factor

            topic_scores[topic_name] = score

        return topic_scores

    def topic_specificity(self, topic_scores: dict[str, float]) -> float:
        """Calculate topic specificity using Shannon entropy.

        Args:
            topic_scores: Dictionary of topic scores

        Returns:
            Specificity score (0-1, higher = more specific)
        """
        # Remove zero scores
        non_zero_scores = [score for score in topic_scores.values() if score > 0]

        if not non_zero_scores:
            return 0.0

        if len(non_zero_scores) == 1:
            return 1.0  # Perfect specificity

        # Calculate total score
        total_score = sum(non_zero_scores)

        # Calculate probabilities
        probabilities = [score / total_score for score in non_zero_scores]

        # Calculate Shannon entropy
        entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)

        # Maximum possible entropy (log2 of number of topics with scores)
        max_entropy = math.log2(len(non_zero_scores))

        if max_entropy == 0:
            return 1.0

        # Convert to specificity (1 - normalized_entropy)
        specificity = 1 - (entropy / max_entropy)
        return specificity

    def get_dominant_topic(self, topic_scores: dict[str, float]) -> TopicCategory:
        """Get the dominant topic from scores.

        Args:
            topic_scores: Dictionary of topic scores

        Returns:
            Dominant topic category
        """
        if not topic_scores or all(score == 0 for score in topic_scores.values()):
            return TopicCategory.NONE

        # Find topic with highest score
        dominant_topic_name = max(topic_scores, key=lambda k: float(topic_scores[k]))

        # Map topic names to TopicCategory enum
        topic_mapping = {
            "BM_Reformu": TopicCategory.BM_REFORUMU,
            "Güvenlik_Çatışma": TopicCategory.GUVENLIK_CATISMA,
            "Ekonomi_Ticaret_Enerji": TopicCategory.EKONOMI_TICARET_ENERJI,
            "Liderlik_Yönetim": TopicCategory.LIDERLIK_YONETIM,
            "Diplomatik_Çözüm": TopicCategory.DIPLOMATIK_COZUM,
            "AB_NATO_Genişleme": TopicCategory.AB_NATO_GENISLEME,
            "Yapay_Zeka_Teknoloji": TopicCategory.YAPAY_ZEKA_TEKNOLOJI,
            "Orta_Güçler_Bölgesel": TopicCategory.ORTA_GUCLER_BOLGESEL,
            "Gazze_Filistin_İsrail": TopicCategory.GAZZE_FILISTIN_ISRAIL,
            "Ukrayna_Rusya": TopicCategory.UKRAYNA_RUSYA,
            "Suriye_Geçiş": TopicCategory.SURIYE_GECIS,
            "Afrika_Ortadoğu": TopicCategory.AFRIKA_ORTADOGU,
            "İnsani_Yardım_Haklar": TopicCategory.INSANI_YARDIM_HAKLAR,
            "Çok_Kutupluluk_Düzen": TopicCategory.COK_KUTUPLULUK_DUZEN,
            "Risk_Kırılım": TopicCategory.RISK_KIRILIM,
        }

        return topic_mapping.get(dominant_topic_name, TopicCategory.BM_REFORUMU)

    def tfidf_batch(self, texts: list[str]) -> list[list[str]]:
        """Perform TF-IDF analysis on a batch of texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of TF-IDF keywords for each text
        """
        if not self.HAS_TFIDF:
            return [[] for _ in texts]

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            # Custom tokenizer that preserves our keyword phrases
            def custom_tokenizer(text: str) -> list[str]:
                tokens = []
                text_lower = text.lower()

                # Check for multi-word phrases first
                for topic_keywords in self.TOPICS.values():
                    for kw in topic_keywords:
                        if " " in kw and kw in text_lower:
                            tokens.append(kw)

                # Then single words
                for word in text_lower.split():
                    if len(word) > 2:  # Skip very short words
                        tokens.append(word)

                return tokens

            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(
                tokenizer=custom_tokenizer,
                lowercase=True,
                max_features=1000,
                ngram_range=(1, 3),
            )

            # Fit and transform
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()

            # Extract top keywords for each text
            results = []
            for i in range(len(texts)):
                # Get TF-IDF scores for this document
                scores = tfidf_matrix[i].toarray()[0]

                # Get top keywords (score > 0)
                top_keywords = [
                    feature_names[j]
                    for j in range(len(scores))
                    if scores[j] > 0.1  # Threshold for relevance
                ]

                results.append(top_keywords)

            return results

        except ImportError:
            # scikit-learn not available
            TopicService.HAS_TFIDF = False
            return [[] for _ in texts]
        except Exception:
            # Any other error, fallback to empty lists
            return [[] for _ in texts]

    def analyze_topics(
        self, text: str, tfidf_keywords: list[str] | None = None
    ) -> TopicAnalysis:
        """Analyze topics in text.

        Args:
            text: The text to analyze
            tfidf_keywords: Optional TF-IDF keywords for enhanced analysis

        Returns:
            TopicAnalysis containing topic scores and dominant topic
        """
        # Calculate weighted topic scores
        topic_scores = self.weighted_topic_score(text, tfidf_keywords)

        # Get dominant topic
        dominant_topic = self.get_dominant_topic(topic_scores)

        # Calculate specificity
        specificity = self.topic_specificity(topic_scores)

        # Calculate confidence based on score distribution
        total_score = sum(topic_scores.values())
        max_score = max(topic_scores.values()) if topic_scores else 0.0
        confidence = (max_score / total_score) if total_score > 0 else 0.0
        confidence = min(1.0, confidence * 2)  # Scale up confidence

        return TopicAnalysis(
            topic_scores=topic_scores,
            dominant_topic=dominant_topic,
            specificity=specificity,
            confidence=confidence,
        )
