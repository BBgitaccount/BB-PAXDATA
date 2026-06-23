import json
from collections import defaultdict

import numpy as np
from sqlalchemy import create_engine, select, text
from tqdm import tqdm

from bb_paxdata.application.domain.enums.action_type import map_frame_to_actions
from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.db.models import ActorTopicProjection, Sentence


def main():
    settings = get_settings()
    db_url = settings.database_url or "sqlite+aiosqlite:///paxdata.db"
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace(
        "postgresql+asyncpg", "postgresql"
    )

    print("Connecting to:", sync_url)
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        # 1. Fetch all sentences
        print("Fetching all sentences...")
        res_sents = conn.execute(
            select(
                Sentence.sent_id,
                Sentence.seg_id,
                Sentence.file_id,
                Sentence.country,
                Sentence.word_count,
                Sentence.hedging_score,
                Sentence.face_save_count,
                Sentence.face_threat_count,
                Sentence.power_level,
                Sentence.risk_score,
                Sentence.demand_type,
                Sentence.dominant_frame,
                Sentence.topic_scores,
            )
        )
        all_sentences = res_sents.fetchall()
        print(f"Fetched {len(all_sentences)} sentences.")

        # 2. Fetch all projection rows
        print("Fetching actor_topic_projection rows...")
        res_projs = conn.execute(
            select(
                ActorTopicProjection.file_id,
                ActorTopicProjection.country,
                ActorTopicProjection.topic,
                ActorTopicProjection.topic_model_version,
            )
        )
        projs = res_projs.fetchall()
        print(f"Fetched {len(projs)} projection rows.")

        if not projs:
            print("No projection rows to recalculate.")
            return

        # 3. Organize sentences by (file_id, country)
        sents_by_actor = defaultdict(list)
        for s in all_sentences:
            actor_key = (s.file_id, s.country)
            sents_by_actor[actor_key].append(s)

        # 4. Determine distinct topics across corpus
        all_topics = set()
        corpus_topic_sums = defaultdict(float)
        for s in all_sentences:
            if s.topic_scores:
                scores = s.topic_scores
                if isinstance(scores, str):
                    try:
                        scores = json.loads(scores)
                    except Exception:
                        scores = {}
                if isinstance(scores, dict):
                    for t, val in scores.items():
                        if val is not None:
                            try:
                                val_f = float(val)
                                corpus_topic_sums[t] += val_f
                                all_topics.add(t)
                            except (ValueError, TypeError):
                                pass

        total_corpus_sum = sum(corpus_topic_sums.values())
        corpus_probs = {
            t: (
                corpus_topic_sums[t] / total_corpus_sum if total_corpus_sum > 0 else 0.0
            )
            for t in all_topics
        }

        # 5. Precompute actor-level topic probabilities & entropy
        actor_topic_metrics = {}
        for actor_key, sents in sents_by_actor.items():
            actor_topic_sums = defaultdict(float)
            for s in sents:
                scores = s.topic_scores
                if isinstance(scores, str):
                    try:
                        scores = json.loads(scores)
                    except Exception:
                        scores = {}
                if isinstance(scores, dict):
                    for t, val in scores.items():
                        if val is not None:
                            try:
                                actor_topic_sums[t] += float(val)
                            except (ValueError, TypeError):
                                pass

            total_actor_sum = sum(actor_topic_sums.values())
            actor_probs = {
                t: (
                    actor_topic_sums[t] / total_actor_sum
                    if total_actor_sum > 0
                    else 0.0
                )
                for t in all_topics
            }

            # Entropy
            probs_list = list(actor_probs.values())
            entropy = (
                float(-sum(p * np.log2(p) for p in probs_list if p > 0))
                if probs_list
                else 0.0
            )

            # JS Divergence
            P_vec = np.array([actor_probs[t] for t in all_topics])
            Q_vec = np.array([corpus_probs[t] for t in all_topics])
            M = 0.5 * (P_vec + Q_vec)

            def kl_div(x, y):
                with np.errstate(divide="ignore", invalid="ignore"):
                    sim = x * np.log2(x / y)
                    sim[~np.isfinite(sim)] = 0.0
                return float(np.sum(sim))

            jsd = 0.5 * kl_div(P_vec, M) + 0.5 * kl_div(Q_vec, M)

            actor_topic_metrics[actor_key] = {"entropy": entropy, "jsd": jsd}

        # 6. Recalculate each projection row's raw values
        raw_results = []
        raw_politeness_vals = []
        raw_risk_vals = []

        print("Recalculating projection rows...")
        for proj in tqdm(projs):
            file_id, country, topic, version = proj
            actor_key = (file_id, country)
            sents = sents_by_actor.get(actor_key, [])

            if not sents:
                raw_results.append(
                    {
                        "key": (file_id, country, topic, version),
                        "demand_count": 0.0,
                        "demand_density_per_1k": 0.0,
                        "speech_act_distribution": {},
                        "frame_competition_index": 0.0,
                        "avg_hedging": 0.0,
                        "raw_politeness": 0.0,
                        "diplomatic_signal_index_raw": 0.0,
                        "topic_entropy": 0.0,
                        "js_divergence": 0.0,
                        "segment_count": 0,
                        "risk_score_raw": 0.0,
                        "risk_score_weighted": 0.0,
                        "avg_power_level": 0.0,
                    }
                )
                raw_politeness_vals.append(0.0)
                raw_risk_vals.append(0.0)
                continue

            topic_str = str(topic)
            weights = []
            for s in sents:
                scores = s.topic_scores
                if isinstance(scores, str):
                    try:
                        scores = json.loads(scores)
                    except Exception:
                        scores = {}
                w = 0.0
                if isinstance(scores, dict):
                    w = float(scores.get(topic_str, 0.0) or 0.0)
                weights.append(w)

            sum_w = sum(weights)
            if sum_w == 0:
                # No topic weight, default everything to 0
                raw_results.append(
                    {
                        "key": (file_id, country, topic, version),
                        "demand_count": 0.0,
                        "demand_density_per_1k": 0.0,
                        "speech_act_distribution": {},
                        "frame_competition_index": 0.0,
                        "avg_hedging": 0.0,
                        "raw_politeness": 0.0,
                        "diplomatic_signal_index_raw": 0.0,
                        "topic_entropy": actor_topic_metrics.get(actor_key, {}).get(
                            "entropy", 0.0
                        ),
                        "js_divergence": actor_topic_metrics.get(actor_key, {}).get(
                            "jsd", 0.0
                        ),
                        "segment_count": 0,
                        "risk_score_raw": 0.0,
                        "risk_score_weighted": 0.0,
                        "avg_power_level": 0.0,
                    }
                )
                raw_politeness_vals.append(0.0)
                raw_risk_vals.append(0.0)
                continue

            # word counts & demands
            total_word_count = sum(
                s.word_count * w
                for s, w in zip(sents, weights)
                if s.word_count is not None
            )
            demand_count = sum(
                w
                for s, w in zip(sents, weights)
                if s.demand_type in ("explicit", "implicit")
            )
            demand_density_per_1k = (
                demand_count / (total_word_count / 1000.0)
                if total_word_count > 0
                else 0.0
            )

            # speech act distribution (weighted ActionType distribution)
            act_weights = defaultdict(float)
            for s, w in zip(sents, weights):
                if w > 0:
                    actions = map_frame_to_actions(s.dominant_frame, s.demand_type)
                    for act in actions:
                        act_weights[act.value] += w
            total_act_w = sum(act_weights.values())
            speech_act_dist = (
                {k: v / total_act_w for k, v in act_weights.items()}
                if total_act_w > 0
                else {}
            )

            # frame competition index (Shannon entropy of frame distribution)
            frame_weights = defaultdict(float)
            for s, w in zip(sents, weights):
                if w > 0 and s.dominant_frame:
                    frame_weights[s.dominant_frame] += w
            total_frame_w = sum(frame_weights.values())
            frame_probs = (
                [v / total_frame_w for v in frame_weights.values()]
                if total_frame_w > 0
                else []
            )
            frame_competition_index = (
                float(-sum(p * np.log2(p) for p in frame_probs if p > 0))
                if frame_probs
                else 0.0
            )

            # avg hedging
            hedging_denom = sum(
                s.word_count * w
                for s, w in zip(sents, weights)
                if s.word_count is not None
            )
            avg_hedging = (
                sum(
                    s.hedging_score * s.word_count * w
                    for s, w in zip(sents, weights)
                    if s.hedging_score is not None and s.word_count is not None
                )
                / hedging_denom
                if hedging_denom > 0
                else 0.0
            )

            # raw politeness
            sum_face_save = sum(
                s.face_save_count * w
                for s, w in zip(sents, weights)
                if s.face_save_count is not None
            )
            sum_face_threat = sum(
                s.face_threat_count * w
                for s, w in zip(sents, weights)
                if s.face_threat_count is not None
            )
            raw_politeness = (sum_face_save - sum_face_threat) / sum_w

            # avg power level
            avg_power_level = (
                sum(
                    s.power_level * w
                    for s, w in zip(sents, weights)
                    if s.power_level is not None
                )
                / sum_w
            )

            # risk raw and weighted
            risk_score_raw = (
                sum(
                    s.risk_score * w
                    for s, w in zip(sents, weights)
                    if s.risk_score is not None
                )
                / sum_w
            )
            risk_score_weighted = risk_score_raw * avg_power_level

            # segment count (unique seg_ids where topic is the primary topic of the sentence)
            seg_ids = set()
            for s in sents:
                if s.seg_id and s.topic_scores:
                    s_scores = s.topic_scores
                    if isinstance(s_scores, str):
                        try:
                            s_scores = json.loads(s_scores)
                        except Exception:
                            s_scores = {}
                    valid_scores = {
                        k: float(v) for k, v in s_scores.items() if v is not None
                    }
                    if valid_scores:
                        max_t = max(valid_scores, key=valid_scores.get)
                        if str(max_t) == topic_str:
                            seg_ids.add(s.seg_id)
            segment_count = len(seg_ids)

            raw_results.append(
                {
                    "key": (file_id, country, topic, version),
                    "demand_count": demand_count,
                    "demand_density_per_1k": demand_density_per_1k,
                    "speech_act_distribution": speech_act_dist,
                    "frame_competition_index": frame_competition_index,
                    "avg_hedging": avg_hedging,
                    "raw_politeness": raw_politeness,
                    "topic_entropy": actor_topic_metrics.get(actor_key, {}).get(
                        "entropy", 0.0
                    ),
                    "js_divergence": actor_topic_metrics.get(actor_key, {}).get(
                        "jsd", 0.0
                    ),
                    "segment_count": segment_count,
                    "risk_score_raw": risk_score_raw,
                    "risk_score_weighted": risk_score_weighted,
                    "avg_power_level": avg_power_level,
                }
            )
            raw_politeness_vals.append(raw_politeness)
            raw_risk_vals.append(risk_score_raw)

        # 7. Normalize politeness and risk raw scores
        min_polite = min(raw_politeness_vals) if raw_politeness_vals else 0.0
        max_polite = max(raw_politeness_vals) if raw_politeness_vals else 0.0
        range_polite = max_polite - min_polite

        min_risk = min(raw_risk_vals) if raw_risk_vals else 0.0
        max_risk = max(raw_risk_vals) if raw_risk_vals else 0.0
        range_risk = max_risk - min_risk

        print(f"Politeness min: {min_polite}, max: {max_polite}")
        print(f"Risk raw min: {min_risk}, max: {max_risk}")

        # 8. Perform normalized calculations and batch update
        print("Writing recalculated data to database...")
        update_data = []
        for raw in raw_results:
            key = raw["key"]
            raw_p = raw["raw_politeness"]
            raw_r = raw["risk_score_raw"]

            avg_politeness = (
                (raw_p - min_polite) / range_polite if range_polite > 0 else 0.0
            )
            risk_score_normalized = (
                (raw_r - min_risk) / range_risk if range_risk > 0 else 0.0
            )

            # diplomatic_signal_index = (1 - avg_hedging) * avg_politeness * avg_power_level
            diplomatic_signal_index = (
                (1.0 - raw["avg_hedging"]) * avg_politeness * raw["avg_power_level"]
            )

            update_data.append(
                {
                    "b_file_id": key[0],
                    "b_country": key[1],
                    "b_topic": key[2],
                    "b_version": key[3],
                    "demand_count": raw["demand_count"],
                    "demand_density_per_1k": raw["demand_density_per_1k"],
                    "speech_act_distribution": raw["speech_act_distribution"],
                    "frame_competition_index": raw["frame_competition_index"],
                    "avg_hedging": raw["avg_hedging"],
                    "avg_politeness": avg_politeness,
                    "diplomatic_signal_index": diplomatic_signal_index,
                    "topic_entropy": raw["topic_entropy"],
                    "js_divergence": raw["js_divergence"],
                    "segment_count": raw["segment_count"],
                    "risk_score_raw": raw_r,
                    "risk_score_weighted": raw["risk_score_weighted"],
                    "risk_score_normalized": risk_score_normalized,
                }
            )

        # Executing batch updates using executemany for high performance
        stmt = text(
            """
            UPDATE actor_topic_projection
            SET demand_count = :demand_count,
                demand_density_per_1k = :demand_density_per_1k,
                speech_act_distribution = :speech_act_distribution,
                frame_competition_index = :frame_competition_index,
                avg_hedging = :avg_hedging,
                avg_politeness = :avg_politeness,
                diplomatic_signal_index = :diplomatic_signal_index,
                topic_entropy = :topic_entropy,
                js_divergence = :js_divergence,
                segment_count = :segment_count,
                risk_score_raw = :risk_score_raw,
                risk_score_weighted = :risk_score_weighted,
                risk_score_normalized = :risk_score_normalized
            WHERE file_id = :b_file_id AND country = :b_country AND topic = :b_topic AND topic_model_version = :b_version
        """
        )

        # Serialize JSON columns to string for DB driver compatibility
        for row in update_data:
            row["speech_act_distribution"] = json.dumps(row["speech_act_distribution"])

        # Execute in batches of 100
        batch_size = 100
        for i in range(0, len(update_data), batch_size):
            batch = update_data[i : i + batch_size]
            conn.execute(stmt, batch)

        # Commit the transaction
        conn.commit()
        print(
            f"Successfully recalculated and updated {len(update_data)} projection rows in database."
        )


if __name__ == "__main__":
    main()
