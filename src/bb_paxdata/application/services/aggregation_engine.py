# src/bb_paxdata/application/services/aggregation_engine.py
import uuid
from datetime import datetime

import numpy as np
from bb_paxdata.infrastructure.db.models import (
    ActorTopicDocument,
    ActorTopicProjection,
    SegmentAnalyzedEvent,
)


class AggregationEngine:
    def __init__(self, n_bootstrap_iterations: int = 100) -> None:
        self.n_bootstrap_iterations = n_bootstrap_iterations

    def calculate_bootstrap_ci(
        self, values: np.ndarray, weights: np.ndarray
    ) -> tuple[float, float, float]:
        if len(values) == 0:
            return 0.0, 0.0, 0.0

        weighted_mean = float(np.average(values, weights=weights))

        if len(values) < 3:
            return weighted_mean, weighted_mean, 0.0

        bootstrap_means = []
        n = len(values)
        for _ in range(self.n_bootstrap_iterations):
            indices = np.random.choice(n, size=n, replace=True)
            bootstrap_means.append(
                np.average(values[indices], weights=weights[indices])
            )

        lower = float(np.percentile(bootstrap_means, 2.5))
        upper = float(np.percentile(bootstrap_means, 97.5))
        std_dev = float(np.std(bootstrap_means))
        return lower, upper, std_dev

    def calculate_entropy(self, probabilities: list[float] | np.ndarray) -> float:
        probs = np.array(probabilities, dtype=float)
        probs = probs[probs > 0]
        if len(probs) == 0:
            return 0.0
        return float(-np.sum(probs * np.log2(probs)))

    def calculate_js_divergence(
        self, p: list[float] | np.ndarray, q: list[float] | np.ndarray
    ) -> float:
        p_arr = np.array(p, dtype=float)
        q_arr = np.array(q, dtype=float)

        if np.sum(p_arr) > 0:
            p_arr = p_arr / np.sum(p_arr)
        if np.sum(q_arr) > 0:
            q_arr = q_arr / np.sum(q_arr)

        m = 0.5 * (p_arr + q_arr)

        def kl_divergence(x: np.ndarray, y: np.ndarray) -> float:
            sim = x * np.log2(x / y, where=(x > 0) & (y > 0), out=np.zeros_like(x))
            return float(np.sum(sim))

        jsd = 0.5 * kl_divergence(p_arr, m) + 0.5 * kl_divergence(q_arr, m)
        return float(jsd)

    def aggregate_events(
        self, events: list[SegmentAnalyzedEvent]
    ) -> tuple[list[ActorTopicProjection], list[ActorTopicDocument]]:
        if not events:
            return [], []

        country_events: dict[str, list[SegmentAnalyzedEvent]] = {}
        for event in events:
            country_events.setdefault(event.country, []).append(event)

        all_topics_set: set[str] = set()
        for event in events:
            all_topics_set.update(event.topic_scores.keys())
        all_topics = sorted(list(all_topics_set))

        country_topic_vectors: dict[str, np.ndarray] = {}
        for country, evs in country_events.items():
            vec = np.zeros(len(all_topics))
            for ev in evs:
                for idx, t in enumerate(all_topics):
                    vec[idx] += ev.topic_scores.get(t, 0.0)
            if len(evs) > 0:
                vec = vec / len(evs)
            country_topic_vectors[country] = vec

        coalitions: dict[str, list[str]] = {}
        for c1, v1 in country_topic_vectors.items():
            coal_list = []
            for c2, v2 in country_topic_vectors.items():
                if c1 == c2:
                    continue
                norm_v1 = np.linalg.norm(v1)
                norm_v2 = np.linalg.norm(v2)
                if norm_v1 > 0 and norm_v2 > 0:
                    similarity = np.dot(v1, v2) / (norm_v1 * norm_v2)
                else:
                    similarity = 0.0
                if similarity >= 0.9:
                    coal_list.append(c2)
            coalitions[c1] = coal_list

        projections: list[ActorTopicProjection] = []
        documents: list[ActorTopicDocument] = []

        for country, evs in country_events.items():
            file_id = evs[0].file_id
            version = evs[0].topic_model_version

            for topic in all_topics:
                topic_scores = [ev.topic_scores.get(topic, 0.0) for ev in evs]
                score = float(np.mean(topic_scores))

                weights = np.array(topic_scores)
                if np.sum(weights) == 0:
                    weights = np.ones(len(evs))

                risk_vals = np.array([ev.risk_score for ev in evs])
                risk_score = float(np.average(risk_vals, weights=weights))

                sentiment_vals = np.array([ev.diplo_compound for ev in evs])
                avg_sentiment = float(np.average(sentiment_vals, weights=weights))

                best_ev = max(evs, key=lambda ev: ev.topic_scores.get(topic, 0.0))
                dominant_emotion = best_ev.emotion_category

                dominant_frame = None
                if best_ev.frame_distribution:
                    dominant_frame = max(
                        best_ev.frame_distribution.items(), key=lambda x: (x[1], x[0])
                    )[0]

                avg_vad = {"V": 0.0, "A": 0.0, "D": 0.0}
                total_weight = 0.0
                for ev, w in zip(evs, weights):
                    if ev.vad_vector:
                        total_weight += w
                        for k in avg_vad:
                            avg_vad[k] += ev.vad_vector.get(k, 0.0) * w
                if total_weight > 0:
                    for k in avg_vad:
                        avg_vad[k] = float(avg_vad[k] / total_weight)
                else:
                    avg_vad = {"V": 0.0, "A": 0.0, "D": 0.0}

                mention_count = len(evs)
                total_word_count = sum(
                    len(ev.text_snippet.split()) if ev.text_snippet else 0 for ev in evs
                )

                sentiment_ci_lower = None
                sentiment_ci_upper = None
                sentiment_std = None
                risk_ci_lower = None
                risk_ci_upper = None

                if len(evs) >= 3:
                    sentiment_ci_lower, sentiment_ci_upper, sentiment_std = (
                        self.calculate_bootstrap_ci(sentiment_vals, weights)
                    )
                    risk_ci_lower, risk_ci_upper, _ = self.calculate_bootstrap_ci(
                        risk_vals, weights
                    )

                proj = ActorTopicProjection(
                    file_id=file_id,
                    country=country,
                    topic=topic,
                    topic_model_version=version,
                    score=score,
                    mention_count=mention_count,
                    fuzzy_mention_mass=float(np.sum(topic_scores)),
                    avg_sentiment=avg_sentiment,
                    sentiment_ci_lower=sentiment_ci_lower,
                    sentiment_ci_upper=sentiment_ci_upper,
                    sentiment_std=sentiment_std,
                    risk_score=risk_score,
                    risk_ci_lower=risk_ci_lower,
                    risk_ci_upper=risk_ci_upper,
                    demand_count=float(sum(ev.demand_count for ev in evs)),
                    avg_vad=avg_vad,
                    dominant_emotion=dominant_emotion,
                    dominant_frame=dominant_frame,
                    top_coalition_actors=coalitions.get(country, []),
                    last_event_id=evs[-1].event_id,
                    segment_count=len(set(ev.segment_id for ev in evs)),
                    total_word_count=total_word_count,
                    updated_at=datetime.now(),
                )
                projections.append(proj)

            topic_details = {
                topic: float(np.mean([ev.topic_scores.get(topic, 0.0) for ev in evs]))
                for topic in all_topics
            }
            diplomatic_tension_index = float(np.mean([ev.risk_score for ev in evs]))

            c_vec = country_topic_vectors[country]
            if np.sum(c_vec) > 0:
                c_vec = c_vec / np.sum(c_vec)
            agenda_diversity_index = self.calculate_entropy(c_vec)

            doc = ActorTopicDocument(
                id=str(uuid.uuid4()),
                file_id=file_id,
                country=country,
                topic_model_version=version,
                topic_details=topic_details,
                network_edges={},
                diplomatic_tension_index=diplomatic_tension_index,
                agenda_diversity_index=agenda_diversity_index,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            documents.append(doc)

        return projections, documents
