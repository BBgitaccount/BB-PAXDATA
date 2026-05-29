filepath = r"c:\Users\THINKPAD\Desktop\BB-PAXDATA\alembic\versions\84643356932b_merge_panels_and_processed_files_into_.py"

with open(filepath, encoding="utf-8") as f:
    content = f.read()

# We want drop_constraint to use None, but create_foreign_key / create_unique_constraint to use names.
# Let's replace the drop_constraints to use None.
content = content.replace(
    "batch_op.drop_constraint('fk_ai_panel_synthesis_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_country_stats_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_demand_records_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_discourse_network_edges_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_discourse_network_edges_legacy_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_legacy_country_references_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_panel_dynamics_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_pattern_records_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_segments_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_segments_speaker_id_speakers', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_sentences_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_speaker_profiles_speaker_id_speakers', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_topic_matrix_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_words_panel_id_panels', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)

# And in downgrade:
content = content.replace(
    "batch_op.drop_constraint('fk_words_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_topic_matrix_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_sentences_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_segments_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_segments_speaker_id_speaker_profiles', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_pattern_records_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_panel_dynamics_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_legacy_country_references_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_discourse_network_edges_legacy_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_discourse_network_edges_panel_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_demand_records_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_country_stats_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('fk_ai_panel_synthesis_file_id_files', type_='foreignkey')",
    "batch_op.drop_constraint(None, type_='foreignkey')",
)
content = content.replace(
    "batch_op.drop_constraint('uq_ai_panel_synthesis_file_id', type_='unique')",
    "batch_op.drop_constraint(None, type_='unique')",
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Migration file constraints V2 successfully updated!")
