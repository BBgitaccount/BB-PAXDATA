"""add_all_strategic_views

Revision ID: 0762fd4c7846
Revises: b754aee19e42
Create Date: 2026-05-22 21:10:06.230668

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0762fd4c7846"
down_revision: Union[str, None] = "b754aee19e42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_word_freq_country")
    op.execute(
        """CREATE VIEW v_word_freq_country AS SELECT country, word_norm, COUNT(*) as freq FROM words GROUP BY country, word_norm"""
    )

    op.execute("DROP VIEW IF EXISTS v_sentence_freq_country")
    op.execute(
        """CREATE VIEW v_sentence_freq_country AS SELECT country, COUNT(*) as freq FROM sentences GROUP BY country"""
    )

    op.execute("DROP VIEW IF EXISTS v_sentiment_analysis")
    op.execute(
        """CREATE VIEW v_sentiment_analysis AS SELECT sent_id, country, vader_compound, negation_aware_diplo as neg_aware_sentiment FROM sentences"""
    )

    op.execute("DROP VIEW IF EXISTS v_diplomatic_network")
    op.execute(
        """CREATE VIEW v_diplomatic_network AS SELECT from_country, to_country, COUNT(*) as edges FROM discourse_network_edges GROUP BY from_country, to_country"""
    )

    op.execute("DROP VIEW IF EXISTS v_ally_enemy")
    op.execute(
        """CREATE VIEW v_ally_enemy AS SELECT from_country, to_country, affinity_score, relationship_type FROM country_pair_sentiment"""
    )

    op.execute("DROP VIEW IF EXISTS v_message_volume")
    op.execute(
        """CREATE VIEW v_message_volume AS SELECT country, SUM(word_count) as total_words, SUM(char_count) as total_chars FROM sentences GROUP BY country"""
    )

    op.execute("DROP VIEW IF EXISTS v_turkey_foreign_policy")
    op.execute(
        """CREATE VIEW v_turkey_foreign_policy AS SELECT to_country, relationship_type, affinity_score FROM country_pair_sentiment WHERE from_country='Turkey'"""
    )

    op.execute("DROP VIEW IF EXISTS v_risk_analysis")
    op.execute(
        """CREATE VIEW v_risk_analysis AS SELECT panel_id, country, SUM(risk_score) as total_risk FROM segments GROUP BY panel_id, country"""
    )

    op.execute("DROP VIEW IF EXISTS v_speaker_power")
    op.execute(
        """CREATE VIEW v_speaker_power AS SELECT full_name as speaker_name, country, power_level, influence_tier, n_panels, n_sentences FROM speakers"""
    )

    op.execute("DROP VIEW IF EXISTS v_pattern_analysis")
    op.execute(
        """CREATE VIEW v_pattern_analysis AS SELECT country, dominant_frame, COUNT(*) as pattern_count FROM segments GROUP BY country, dominant_frame"""
    )

    op.execute("DROP VIEW IF EXISTS v_demand_analysis")
    op.execute(
        """CREATE VIEW v_demand_analysis AS SELECT country, demand_type, demand_category, COUNT(*) as demand_count FROM sentences WHERE demand_type IS NOT NULL GROUP BY country, demand_type, demand_category"""
    )

    op.execute("DROP VIEW IF EXISTS v_country_overview")
    op.execute(
        """CREATE VIEW v_country_overview AS SELECT country, SUM(n_sentences) as sents, SUM(total_words) as words FROM speakers GROUP BY country"""
    )

    op.execute("DROP VIEW IF EXISTS v_sbi_analysis")
    op.execute(
        """CREATE VIEW v_sbi_analysis AS SELECT speaker_name, country, AVG(sbi_score) as avg_sbi FROM segments GROUP BY speaker_name, country"""
    )

    op.execute("DROP VIEW IF EXISTS v_dki_profile")
    op.execute(
        """CREATE VIEW v_dki_profile AS SELECT speaker_name, country, AVG(dki_score) as avg_dki FROM segments GROUP BY speaker_name, country"""
    )

    op.execute("DROP VIEW IF EXISTS v_framing_analysis")
    op.execute(
        """CREATE VIEW v_framing_analysis AS SELECT dominant_frame, COUNT(*) as frame_count FROM segments GROUP BY dominant_frame"""
    )

    op.execute("DROP VIEW IF EXISTS v_hedging_politeness")
    op.execute(
        """CREATE VIEW v_hedging_politeness AS SELECT speaker_name, country, AVG(hedging_score) as avg_hedging, AVG(politeness_ratio) as avg_polite FROM sentences GROUP BY speaker_name, country"""
    )

    op.execute("DROP VIEW IF EXISTS v_temporal_evolution")
    op.execute(
        """CREATE VIEW v_temporal_evolution AS SELECT panel_id, seg_id, global_sent_start, duration_sec FROM segments"""
    )

    op.execute("DROP VIEW IF EXISTS v_manipulation_scores")
    op.execute(
        """CREATE VIEW v_manipulation_scores AS SELECT speaker_name, country, AVG(formula_manip_score) as avg_manip FROM segments GROUP BY speaker_name, country"""
    )

    op.execute("DROP VIEW IF EXISTS v_discourse_dynamics")
    op.execute(
        """CREATE VIEW v_discourse_dynamics AS SELECT panel_id, COUNT(seg_id) as segment_count, AVG(risk_score) as avg_risk FROM segments GROUP BY panel_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_risk_summary")
    op.execute(
        """CREATE VIEW v_ai_risk_summary AS SELECT s.country, s.panel_id, AVG(a.risk_score) as avg_risk FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id = s.sent_id GROUP BY s.country, s.panel_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_validation_health")
    op.execute(
        """CREATE VIEW v_ai_validation_health AS SELECT check_type, COUNT(*) as fails FROM ai_validation_log GROUP BY check_type"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_speaker_insights")
    op.execute(
        """CREATE VIEW v_ai_speaker_insights AS SELECT s.speaker_name, a.diplomatic_tone, a.primary_topic FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_country_logic")
    op.execute(
        """CREATE VIEW v_ai_country_logic AS SELECT s.country, COUNT(a.overall_logic_check) as logic_fails FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id WHERE a.overall_logic_check='FAIL' GROUP BY s.country"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_intent_map")
    op.execute(
        """CREATE VIEW v_ai_intent_map AS SELECT s.country, a.primary_topic, COUNT(*) as intent_cnt FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.primary_topic"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_discourse_quality")
    op.execute(
        """CREATE VIEW v_ai_discourse_quality AS SELECT s.speaker_name, AVG(a.manipulation_score) as avg_manip FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.speaker_name"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_contextual_flags_summary")
    op.execute(
        """CREATE VIEW v_ai_contextual_flags_summary AS SELECT s.country, a.flag_category, COUNT(*) as flag_cnt FROM ai_contextual_flags a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.flag_category"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_demand_analysis")
    op.execute(
        """CREATE VIEW v_ai_demand_analysis AS SELECT s.country, a.demand_category, COUNT(*) as d_cnt FROM ai_demand_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.demand_category"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_demand_future")
    op.execute(
        """CREATE VIEW v_ai_demand_future AS SELECT s.country, a.demand_category, SUM(a.strategic_value) as total_intensity FROM ai_demand_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.demand_category"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_sentence_deep")
    op.execute(
        """CREATE VIEW v_ai_sentence_deep AS SELECT s.sent_id, s.text, a.risk_level, a.manipulation_score FROM sentences s LEFT JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_sentence_complete_profile")
    op.execute(
        """CREATE VIEW v_ai_sentence_complete_profile AS SELECT s.sent_id, s.text, s.country, a.sentiment_score, a.risk_level FROM sentences s LEFT JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_segment_insights")
    op.execute(
        """CREATE VIEW v_ai_segment_insights AS SELECT seg_id, segment_summary, power_dynamics FROM ai_segment_insights"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_network_cross")
    op.execute(
        """CREATE VIEW v_ai_network_cross AS SELECT from_country, to_country, SUM(affinity_score) as network_affinity FROM country_pair_sentiment GROUP BY from_country, to_country"""
    )

    op.execute("DROP VIEW IF EXISTS v_ai_panel_synthesis")
    op.execute(
        """CREATE VIEW v_ai_panel_synthesis AS SELECT panel_id, panel_summary, risk_map FROM ai_panel_synthesis"""
    )

    op.execute("DROP VIEW IF EXISTS v_discourse_drift_alerts")
    op.execute(
        """CREATE VIEW v_discourse_drift_alerts AS SELECT speaker_name, panel_id, AVG(risk_score) as avg_risk FROM segments GROUP BY speaker_name, panel_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_hypocrisy_contradiction_index")
    op.execute(
        """CREATE VIEW v_hypocrisy_contradiction_index AS SELECT s.speaker_name, s.sent_id, s.dominant_topic, s.vader_compound FROM sentences s JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"""
    )

    op.execute("DROP VIEW IF EXISTS v_echo_chamber_alignment")
    op.execute(
        """CREATE VIEW v_echo_chamber_alignment AS SELECT s1.country as c1, s2.country as c2, COUNT(*) as shared_frames FROM sentences s1 JOIN sentences s2 ON s1.dominant_frame = s2.dominant_frame AND s1.country != s2.country GROUP BY s1.country, s2.country"""
    )

    op.execute("DROP VIEW IF EXISTS v_cognitive_load_manipulation")
    op.execute(
        """CREATE VIEW v_cognitive_load_manipulation AS SELECT s.speaker_name, AVG(s.hedging_score + s.politeness_ratio) as cognitive_load FROM sentences s GROUP BY s.speaker_name"""
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_word_freq_country")
    op.execute("DROP VIEW IF EXISTS v_sentence_freq_country")
    op.execute("DROP VIEW IF EXISTS v_sentiment_analysis")
    op.execute("DROP VIEW IF EXISTS v_diplomatic_network")
    op.execute("DROP VIEW IF EXISTS v_ally_enemy")
    op.execute("DROP VIEW IF EXISTS v_message_volume")
    op.execute("DROP VIEW IF EXISTS v_turkey_foreign_policy")
    op.execute("DROP VIEW IF EXISTS v_risk_analysis")
    op.execute("DROP VIEW IF EXISTS v_speaker_power")
    op.execute("DROP VIEW IF EXISTS v_pattern_analysis")
    op.execute("DROP VIEW IF EXISTS v_demand_analysis")
    op.execute("DROP VIEW IF EXISTS v_country_overview")
    op.execute("DROP VIEW IF EXISTS v_sbi_analysis")
    op.execute("DROP VIEW IF EXISTS v_dki_profile")
    op.execute("DROP VIEW IF EXISTS v_framing_analysis")
    op.execute("DROP VIEW IF EXISTS v_hedging_politeness")
    op.execute("DROP VIEW IF EXISTS v_temporal_evolution")
    op.execute("DROP VIEW IF EXISTS v_manipulation_scores")
    op.execute("DROP VIEW IF EXISTS v_discourse_dynamics")
    op.execute("DROP VIEW IF EXISTS v_ai_risk_summary")
    op.execute("DROP VIEW IF EXISTS v_ai_validation_health")
    op.execute("DROP VIEW IF EXISTS v_ai_speaker_insights")
    op.execute("DROP VIEW IF EXISTS v_ai_country_logic")
    op.execute("DROP VIEW IF EXISTS v_ai_intent_map")
    op.execute("DROP VIEW IF EXISTS v_ai_discourse_quality")
    op.execute("DROP VIEW IF EXISTS v_ai_contextual_flags_summary")
    op.execute("DROP VIEW IF EXISTS v_ai_demand_analysis")
    op.execute("DROP VIEW IF EXISTS v_ai_demand_future")
    op.execute("DROP VIEW IF EXISTS v_ai_sentence_deep")
    op.execute("DROP VIEW IF EXISTS v_ai_sentence_complete_profile")
    op.execute("DROP VIEW IF EXISTS v_ai_segment_insights")
    op.execute("DROP VIEW IF EXISTS v_ai_network_cross")
    op.execute("DROP VIEW IF EXISTS v_ai_panel_synthesis")
    op.execute("DROP VIEW IF EXISTS v_discourse_drift_alerts")
    op.execute("DROP VIEW IF EXISTS v_hypocrisy_contradiction_index")
    op.execute("DROP VIEW IF EXISTS v_echo_chamber_alignment")
    op.execute("DROP VIEW IF EXISTS v_cognitive_load_manipulation")
