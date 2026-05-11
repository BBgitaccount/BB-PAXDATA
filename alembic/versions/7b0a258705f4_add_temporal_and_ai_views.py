"""add_temporal_and_ai_views

Revision ID: 7b0a258705f4
Revises: 002
Create Date: 2026-05-11 13:33:01.843402

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b0a258705f4"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. v_f_fail_negation_analysis
    op.execute(
        """
    CREATE VIEW v_f_fail_negation_analysis AS
    SELECT
        a.sent_id, a.panel_id, a.speaker_name, a.country, a.check_type,
        a.original_sentence, a.formula_value, a.ai_value, a.discrepancy_score,
        a.negation_type AS AI_Negasyon_Tipi, a.negation_scope AS AI_Negasyon_Kapsami, 
        a.fail_reason AS AI_Neden_Fail,
        a.formula_gap AS AI_Formul_Eksigi, a.correction_suggestion AS AI_Duzeltme_Onerisi, 
        a.confidence_score AS AI_Guven_Skoru, a.processed_at
    FROM ai_fail_analysis a
    WHERE a.negation_type IS NOT NULL AND a.negation_type != 'yok'
      AND a.country NOT IN ('—','Unknown')
    """
    )

    # 2. v_f_fail_speaker_patterns
    op.execute(
        """
    CREATE VIEW v_f_fail_speaker_patterns AS
    SELECT
        a.speaker_name, a.country,
        COUNT(*)                                            AS total_fails,
        COUNT(DISTINCT a.check_type)                        AS affected_checks,
        ROUND(AVG(a.discrepancy_score), 4)                  AS avg_discrepancy,
        ROUND(AVG(a.confidence_score), 3)                   AS avg_ai_confidence,
        (SELECT a2.fail_category FROM ai_fail_analysis a2
         WHERE a2.speaker_name = a.speaker_name
         GROUP BY a2.fail_category ORDER BY COUNT(*) DESC LIMIT 1) AS dominant_fail_category,
        (SELECT a3.check_type FROM ai_fail_analysis a3
         WHERE a3.speaker_name = a.speaker_name
         GROUP BY a3.check_type ORDER BY COUNT(*) DESC LIMIT 1)         AS most_common_check,
        SUM(CASE WHEN a.negation_type != 'yok' AND a.negation_type IS NOT NULL THEN 1 ELSE 0 END) AS negation_fail_count,
        MAX(a.processed_at)                                             AS last_fail_at
    FROM ai_fail_analysis a
    WHERE a.country NOT IN ('—','Unknown')
    GROUP BY a.speaker_name, a.country
    """
    )

    # 3. v_f_fail_contextual_deep
    op.execute(
        """
    CREATE VIEW v_f_fail_contextual_deep AS
    SELECT
        a.sent_id, a.panel_id, a.speaker_name, a.country, a.check_type,
        a.original_sentence, a.prev_sentence, a.next_sentence, a.triplet_text,
        a.contextual_factor AS AI_Baglamsal_Faktor, a.temporal_factor AS AI_Temporal_Faktor, 
        a.fail_reason AS AI_Neden_Fail,
        a.formula_gap AS AI_Formul_Eksigi, a.ai_misperception AS AI_AI_Yanilgisi, 
        a.correction_suggestion AS AI_Duzeltme_Onerisi,
        a.discrepancy_score, a.confidence_score AS AI_Guven_Skoru, a.processed_at,
        asa.sentiment_score AS AI_Duygu_Skoru, asa.risk_level AS AI_Risk_Skoru, 
        asa.manipulation_score AS AI_Manipulasyon_Skor
    FROM ai_fail_analysis a
    LEFT JOIN ai_sentence_analysis asa ON a.sent_id = asa.sent_id
    WHERE a.country NOT IN ('—','Unknown')
    """
    )

    # 4. v_f_fail_formula_vs_ai
    op.execute(
        """
    CREATE VIEW v_f_fail_formula_vs_ai AS
    SELECT
        a.check_type, a.fail_category AS AI_Fail_Kategorisi,
        COUNT(*)                                            AS fail_count,
        ROUND(AVG(a.discrepancy_score), 4)                  AS avg_discrepancy,
        ROUND(AVG(a.confidence_score), 3)                   AS avg_ai_confidence,
        COUNT(DISTINCT a.sent_id)                           AS affected_sentences,
        COUNT(DISTINCT a.speaker_name)                      AS affected_speakers,
        (SELECT a2.sent_id FROM ai_fail_analysis a2
         WHERE a2.check_type = a.check_type AND a2.fail_category = a.fail_category
         ORDER BY a2.discrepancy_score DESC LIMIT 1)        AS max_discrepancy_sent_id
    FROM ai_fail_analysis a
    WHERE a.country NOT IN ('—','Unknown')
    GROUP BY a.check_type, a.fail_category
    """
    )

    # 5. v_f_fail_correction_suggestions
    op.execute(
        """
    CREATE VIEW v_f_fail_correction_suggestions AS
    SELECT
        a.fail_category AS AI_Fail_Kategorisi, a.check_type, a.negation_type AS AI_Negasyon_Tipi,
        COUNT(*)                                            AS occurrence_count,
        a.formula_gap                                       AS formula_shortcoming,
        a.correction_suggestion                             AS correction_suggestion,
        a.comparative_correction                            AS comparative_fix,
        ROUND(AVG(a.discrepancy_score), 4)                  AS avg_discrepancy,
        ROUND(AVG(a.confidence_score), 3)                   AS avg_confidence,
        MAX(a.processed_at)                                 AS last_seen
    FROM ai_fail_analysis a
    WHERE a.country NOT IN ('—','Unknown') AND a.correction_suggestion IS NOT NULL
    GROUP BY a.fail_category, a.check_type, a.correction_suggestion
    """
    )

    # 6. v_f_fail_temporal_analysis
    op.execute(
        """
    CREATE VIEW v_f_fail_temporal_analysis AS
    SELECT
        a.sent_id, a.panel_id, a.speaker_name, a.country,
        a.check_type, a.discrepancy_score,
        a.kgi_score, a.risk_delta, a.emotion_shift, a.topic_shift,
        a.fail_reason AS AI_Neden_Fail, a.temporal_factor AS AI_Temporal_Faktor,
        a.formula_inconsistency_score,
        a.global_sent_order,
        CASE
            WHEN a.risk_delta > 2 THEN 'SHARP_ESCALATION'
            WHEN a.emotion_shift > 0.5 THEN 'EMOTIONAL_SPIKE'
            WHEN a.topic_shift > 0.3 THEN 'TOPIC_PIVOT'
            ELSE 'GRADUAL_DRIFT'
        END AS temporal_pattern
    FROM ai_fail_analysis a
    WHERE a.country NOT IN ('—','Unknown')
    """
    )

    # 7. v_f_fail_ai_cross_reference
    op.execute(
        """
    CREATE VIEW v_f_fail_ai_cross_reference AS
    SELECT
        f.sent_id, f.check_type, f.fail_category AS AI_Fail_Kategorisi,
        f.formula_value, f.ai_value, f.discrepancy_score,
        asa.sentiment_score AS AI_Duygu_Skoru, asa.risk_level AS AI_Risk_Skoru, 
        asa.manipulation_score AS AI_Manipulasyon_Skor,
        f.fail_reason AS AI_Neden_Fail
    FROM ai_fail_analysis f
    LEFT JOIN ai_sentence_analysis asa ON f.sent_id = asa.sent_id
    WHERE f.country NOT IN ('—','Unknown')
    """
    )

    # 8. v_f_fail_anomaly_bridge
    op.execute(
        """
    CREATE VIEW v_f_fail_anomaly_bridge AS
    SELECT
        f.sent_id, f.speaker_name, f.country, f.check_type,
        f.fail_category AS AI_Fail_Kategorisi, f.negation_type AS AI_Negasyon_Tipi,
        c.anomaly_type, c.severity, c.flag_category, c.description AS anomaly_description
    FROM ai_fail_analysis f
    LEFT JOIN ai_contextual_flags c ON f.sent_id = c.sent_id
    WHERE c.severity IN ('HIGH', 'CRITICAL')
    """
    )

    # 9. v_f_fail_network_context
    op.execute(
        """
    CREATE VIEW v_f_fail_network_context AS
    SELECT
        f.sent_id, f.speaker_name, f.country, f.check_type,
        dne.from_country, dne.to_country, dne.edge_type,
        cp.relationship_type, cp.affinity_score,
        f.fail_reason AS AI_Neden_Fail
    FROM ai_fail_analysis f
    LEFT JOIN sentences s ON f.sent_id = s.sent_id
    LEFT JOIN discourse_network_edges dne
        ON s.panel_id = dne.panel_id AND s.country = dne.from_country
    LEFT JOIN country_pair_sentiment cp
        ON dne.from_country = cp.from_country AND dne.to_country = cp.to_country
    WHERE f.country NOT IN ('—','Unknown')
    """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_f_fail_negation_analysis")
    op.execute("DROP VIEW IF EXISTS v_f_fail_speaker_patterns")
    op.execute("DROP VIEW IF EXISTS v_f_fail_contextual_deep")
    op.execute("DROP VIEW IF EXISTS v_f_fail_formula_vs_ai")
    op.execute("DROP VIEW IF EXISTS v_f_fail_correction_suggestions")
    op.execute("DROP VIEW IF EXISTS v_f_fail_temporal_analysis")
    op.execute("DROP VIEW IF EXISTS v_f_fail_ai_cross_reference")
    op.execute("DROP VIEW IF EXISTS v_f_fail_anomaly_bridge")
    op.execute("DROP VIEW IF EXISTS v_f_fail_network_context")
