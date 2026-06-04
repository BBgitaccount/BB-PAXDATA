import sqlite3

DB_PATH = "c:\\Users\\THINKPAD\\Desktop\\BB-PAXDATA\\paxdata.db"
MIGRATION_PATH = "c:\\Users\\THINKPAD\\Desktop\\BB-PAXDATA\\alembic\\versions\\0762fd4c7846_add_all_strategic_views.py"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


def get_columns(table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
tables = [t[0] for t in tables]

# Let's map out views
views = {}

views["v_word_freq_country"] = (
    "SELECT country, word_norm, COUNT(*) as freq FROM words GROUP BY country, word_norm"
)
views["v_sentence_freq_country"] = (
    "SELECT country, COUNT(*) as freq FROM sentences GROUP BY country"
)
views["v_sentiment_analysis"] = (
    "SELECT sent_id, country, vader_compound, negation_aware_diplo as neg_aware_sentiment FROM sentences"
)
views["v_diplomatic_network"] = (
    "SELECT from_country, to_country, COUNT(*) as edges FROM discourse_network_edges GROUP BY from_country, to_country"
)
views["v_ally_enemy"] = (
    "SELECT from_country, to_country, affinity_score, relationship_type FROM country_pair_sentiment"
)
views["v_message_volume"] = (
    "SELECT country, SUM(word_count) as total_words, SUM(char_count) as total_chars FROM sentences GROUP BY country"
)
views["v_turkey_foreign_policy"] = (
    "SELECT to_country, relationship_type, affinity_score FROM country_pair_sentiment WHERE from_country='Turkey'"
)
views["v_risk_analysis"] = (
    "SELECT panel_id, country, SUM(risk_score) as total_risk FROM segments GROUP BY panel_id, country"
)
views["v_speaker_power"] = (
    "SELECT full_name as speaker_name, country, power_level, influence_tier, n_panels, n_sentences FROM speakers"
)
views["v_pattern_analysis"] = (
    "SELECT country, dominant_frame, COUNT(*) as pattern_count FROM segments GROUP BY country, dominant_frame"
)
views["v_demand_analysis"] = (
    "SELECT country, demand_type, demand_category, COUNT(*) as demand_count FROM sentences WHERE demand_type IS NOT NULL GROUP BY country, demand_type, demand_category"
)
views["v_country_overview"] = (
    "SELECT country, SUM(n_sentences) as sents, SUM(total_words) as words FROM speakers GROUP BY country"
)
views["v_sbi_analysis"] = (
    "SELECT speaker_name, country, AVG(sbi_score) as avg_sbi FROM segments GROUP BY speaker_name, country"
)
views["v_dki_profile"] = (
    "SELECT speaker_name, country, AVG(dki_score) as avg_dki FROM segments GROUP BY speaker_name, country"
)
views["v_framing_analysis"] = (
    "SELECT dominant_frame, COUNT(*) as frame_count FROM segments GROUP BY dominant_frame"
)
views["v_hedging_politeness"] = (
    "SELECT speaker_name, country, AVG(hedging_score) as avg_hedging, AVG(politeness_ratio) as avg_polite FROM sentences GROUP BY speaker_name, country"
)
views["v_temporal_evolution"] = (
    "SELECT panel_id, seg_id, global_sent_start, duration_sec FROM segments"
)
views["v_manipulation_scores"] = (
    "SELECT speaker_name, country, AVG(formula_manip_score) as avg_manip FROM segments GROUP BY speaker_name, country"
)
views["v_discourse_dynamics"] = (
    "SELECT panel_id, COUNT(seg_id) as segment_count, AVG(risk_score) as avg_risk FROM segments GROUP BY panel_id"
)

# AI Views
views["v_ai_risk_summary"] = (
    "SELECT s.country, s.panel_id, AVG(a.risk_score) as avg_risk FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id = s.sent_id GROUP BY s.country, s.panel_id"
)

# Use ai_validation_log or ai_fail_analysis
if "ai_validation_log" in tables:
    views["v_ai_validation_health"] = (
        "SELECT check_type, COUNT(*) as fails FROM ai_validation_log GROUP BY check_type"
    )
else:
    views["v_ai_validation_health"] = "SELECT 'dummy' as check_type"

views["v_ai_speaker_insights"] = (
    "SELECT s.speaker_name, a.diplomatic_tone, a.primary_topic FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id"
)
views["v_ai_country_logic"] = (
    "SELECT s.country, COUNT(a.overall_logic_check) as logic_fails FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id WHERE a.overall_logic_check='FAIL' GROUP BY s.country"
)

views["v_ai_intent_map"] = (
    "SELECT s.country, a.primary_topic, COUNT(*) as intent_cnt FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.primary_topic"
)
views["v_ai_discourse_quality"] = (
    "SELECT s.speaker_name, AVG(a.manipulation_score) as avg_manip FROM ai_sentence_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.speaker_name"
)

views["v_ai_contextual_flags_summary"] = (
    "SELECT s.country, a.flag_category, COUNT(*) as flag_cnt FROM ai_contextual_flags a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.flag_category"
)

if "ai_demand_analysis" in tables:
    views["v_ai_demand_analysis"] = (
        "SELECT s.country, a.demand_category, COUNT(*) as d_cnt FROM ai_demand_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.demand_category"
    )
    views["v_ai_demand_future"] = (
        "SELECT s.country, a.demand_category, SUM(a.strategic_value) as total_intensity FROM ai_demand_analysis a JOIN sentences s ON a.sent_id=s.sent_id GROUP BY s.country, a.demand_category"
    )
else:
    views["v_ai_demand_analysis"] = (
        "SELECT country, demand_category, COUNT(*) as d_cnt FROM sentences GROUP BY country, demand_category"
    )
    views["v_ai_demand_future"] = (
        "SELECT country, demand_category, COUNT(*) as d_cnt FROM sentences GROUP BY country, demand_category"
    )


views["v_ai_sentence_deep"] = (
    "SELECT s.sent_id, s.text, a.risk_level, a.manipulation_score FROM sentences s LEFT JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"
)
views["v_ai_sentence_complete_profile"] = (
    "SELECT s.sent_id, s.text, s.country, a.sentiment_score, a.risk_level FROM sentences s LEFT JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"
)

if "ai_segment_insights" in tables:
    views["v_ai_segment_insights"] = (
        "SELECT seg_id, segment_summary, power_dynamics FROM ai_segment_insights"
    )
else:
    views["v_ai_segment_insights"] = (
        "SELECT seg_id, dominant_topic, risk_score FROM segments"
    )

views["v_ai_network_cross"] = (
    "SELECT from_country, to_country, SUM(affinity_score) as network_affinity FROM country_pair_sentiment GROUP BY from_country, to_country"
)

if "ai_panel_synthesis" in tables:
    views["v_ai_panel_synthesis"] = (
        "SELECT panel_id, panel_summary, risk_map FROM ai_panel_synthesis"
    )
else:
    views["v_ai_panel_synthesis"] = (
        "SELECT panel_id, AVG(risk_score) as avg_risk FROM segments GROUP BY panel_id"
    )

# New Strategic Views
views["v_discourse_drift_alerts"] = (
    "SELECT speaker_name, panel_id, AVG(risk_score) as avg_risk FROM segments GROUP BY speaker_name, panel_id"
)
views["v_hypocrisy_contradiction_index"] = (
    "SELECT s.speaker_name, s.sent_id, s.dominant_topic, s.vader_compound FROM sentences s JOIN ai_sentence_analysis a ON s.sent_id=a.sent_id"
)
views["v_echo_chamber_alignment"] = (
    "SELECT s1.country as c1, s2.country as c2, COUNT(*) as shared_frames FROM sentences s1 JOIN sentences s2 ON s1.dominant_frame = s2.dominant_frame AND s1.country != s2.country GROUP BY s1.country, s2.country"
)
views["v_cognitive_load_manipulation"] = (
    "SELECT s.speaker_name, AVG(s.hedging_score + s.politeness_ratio) as cognitive_load FROM sentences s GROUP BY s.speaker_name"
)


migration_content = '''"""add_all_strategic_views

Revision ID: 0762fd4c7846
Revises: b754aee19e42
Create Date: 2026-05-22 21:10:06.230668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0762fd4c7846'
down_revision: Union[str, None] = 'b754aee19e42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
'''

for view_name, sql in views.items():
    migration_content += f'    op.execute("DROP VIEW IF EXISTS {view_name}")\n'
    migration_content += f'    op.execute("""CREATE VIEW {view_name} AS {sql}""")\n\n'

migration_content += "def downgrade() -> None:\n"
for view_name in views.keys():
    migration_content += f"""    op.execute("DROP VIEW IF EXISTS {view_name}")\n"""

with open(MIGRATION_PATH, "w", encoding="utf-8") as f:
    f.write(migration_content)

print("Migration generated successfully!")
