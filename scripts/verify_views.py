import sqlite3

DB_PATH = "c:\\Users\\THINKPAD\\Desktop\\BB-PAXDATA\\bb-paxdata.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

views = [
    "v_word_freq_country",
    "v_sentence_freq_country",
    "v_sentiment_analysis",
    "v_diplomatic_network",
    "v_ally_enemy",
    "v_message_volume",
    "v_turkey_foreign_policy",
    "v_risk_analysis",
    "v_speaker_power",
    "v_pattern_analysis",
    "v_demand_analysis",
    "v_country_overview",
    "v_sbi_analysis",
    "v_dki_profile",
    "v_framing_analysis",
    "v_hedging_politeness",
    "v_temporal_evolution",
    "v_manipulation_scores",
    "v_discourse_dynamics",
    "v_ai_risk_summary",
    "v_ai_validation_health",
    "v_ai_speaker_insights",
    "v_ai_country_logic",
    "v_ai_intent_map",
    "v_ai_discourse_quality",
    "v_ai_contextual_flags_summary",
    "v_ai_demand_analysis",
    "v_ai_demand_future",
    "v_ai_sentence_deep",
    "v_ai_sentence_complete_profile",
    "v_ai_segment_insights",
    "v_ai_network_cross",
    "v_ai_panel_synthesis",
    "v_discourse_drift_alerts",
    "v_hypocrisy_contradiction_index",
    "v_echo_chamber_alignment",
    "v_cognitive_load_manipulation",
]

success = 0
failed = []

print("Starting validation of 37 views...")
for view in views:
    try:
        cursor.execute(f"SELECT * FROM {view} LIMIT 1")
        row = cursor.fetchone()
        success += 1
    except Exception as e:
        print(f"FAILED: {view} -> {e}")
        failed.append(view)

print(f"\\nValidation Complete! {success}/37 passed.")
if failed:
    print(f"Failed views: {failed}")
else:
    print("ALL VIEWS SUCCESSFUL!")
