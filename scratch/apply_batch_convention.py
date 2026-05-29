import re

filepath = r"c:\Users\THINKPAD\Desktop\BB-PAXDATA\alembic\versions\84643356932b_merge_panels_and_processed_files_into_.py"

with open(filepath, encoding="utf-8") as f:
    content = f.read()

# Re-apply fix_migration_constraints.py replacements first to ensure all constraint names are named
# Let's run the exact replacement logic from fix_migration_constraints.py
upgrade_replacements = {
    (
        "with op.batch_alter_table('ai_panel_synthesis', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.create_unique_constraint(None, ['file_id'])\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('ai_panel_synthesis', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.create_unique_constraint('uq_ai_panel_synthesis_file_id', ['file_id'])\n        batch_op.drop_constraint('fk_ai_panel_synthesis_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_ai_panel_synthesis_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('country_stats', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('country_stats', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint('fk_country_stats_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_country_stats_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('demand_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('demand_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_constraint('fk_demand_records_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_demand_records_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('discourse_network_edges', schema=None) as batch_op:\n        batch_op.drop_index(batch_op.f('ix_net_actor'))\n        batch_op.drop_index(batch_op.f('ix_net_session'))\n        batch_op.drop_index(batch_op.f('ix_net_weight'))\n        batch_op.create_index(batch_op.f('ix_discourse_network_edges_session_id'), ['session_id'], unique=False)\n        batch_op.create_index(batch_op.f('ix_discourse_network_edges_weight'), ['weight'], unique=False)\n        batch_op.create_index('ix_net_weight_high', ['weight'], unique=False, postgresql_where='weight > 0.5')\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['panel_id'], ['file_id'], ondelete='CASCADE')"
    ): (
        "with op.batch_alter_table('discourse_network_edges', schema=None) as batch_op:\n        batch_op.drop_index(batch_op.f('ix_net_actor'))\n        batch_op.drop_index(batch_op.f('ix_net_session'))\n        batch_op.drop_index(batch_op.f('ix_net_weight'))\n        batch_op.create_index(batch_op.f('ix_discourse_network_edges_session_id'), ['session_id'], unique=False)\n        batch_op.create_index(batch_op.f('ix_discourse_network_edges_weight'), ['weight'], unique=False)\n        batch_op.create_index('ix_net_weight_high', ['weight'], unique=False, postgresql_where='weight > 0.5')\n        batch_op.drop_constraint('fk_discourse_network_edges_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_discourse_network_edges_panel_id_files', 'files', ['panel_id'], ['file_id'], ondelete='CASCADE')"
    ),
    (
        "with op.batch_alter_table('discourse_network_edges_legacy', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_index(batch_op.f('idx_net_legacy_from'))\n        batch_op.create_index('idx_net_from', ['from_country'], unique=False)\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('discourse_network_edges_legacy', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_index(batch_op.f('idx_net_legacy_from'))\n        batch_op.create_index('idx_net_from', ['from_country'], unique=False)\n        batch_op.drop_constraint('fk_discourse_network_edges_legacy_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_discourse_network_edges_legacy_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('legacy_country_references', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('legacy_country_references', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_constraint('fk_legacy_country_references_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_legacy_country_references_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('panel_dynamics', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_index(batch_op.f('idx_dyn_panel'))\n        batch_op.create_index('idx_dyn_panel', ['file_id'], unique=False)\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('panel_dynamics', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.drop_index(batch_op.f('idx_dyn_panel'))\n        batch_op.create_index('idx_dyn_panel', ['file_id'], unique=False)\n        batch_op.drop_constraint('fk_panel_dynamics_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_panel_dynamics_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('pattern_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.alter_column('risk_score', \n               existing_type=sa.INTEGER(),\n               server_default=None,\n               existing_nullable=False)\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('pattern_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=True))\n        batch_op.alter_column('risk_score', \n               existing_type=sa.INTEGER(),\n               server_default=None,\n               existing_nullable=False)\n        batch_op.drop_constraint('fk_pattern_records_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_pattern_records_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('segments', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_index(batch_op.f('idx_seg_panel'))\n        batch_op.create_index('idx_seg_file', ['file_id'], unique=False)\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.create_foreign_key(None, 'speaker_profiles', ['speaker_id'], ['speaker_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('segments', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_index(batch_op.f('idx_seg_panel'))\n        batch_op.create_index('idx_seg_file', ['file_id'], unique=False)\n        batch_op.drop_constraint('fk_segments_panel_id_panels', type_='foreignkey')\n        batch_op.drop_constraint('fk_segments_speaker_id_speakers', type_='foreignkey')\n        batch_op.create_foreign_key('fk_segments_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.create_foreign_key('fk_segments_speaker_id_speaker_profiles', 'speaker_profiles', ['speaker_id'], ['speaker_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('sentences', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_index(batch_op.f('idx_sent_panel'))\n        batch_op.create_index('idx_sent_file', ['file_id'], unique=False)\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('sentences', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_index(batch_op.f('idx_sent_panel'))\n        batch_op.create_index('idx_sent_file', ['file_id'], unique=False)\n        batch_op.drop_constraint('fk_sentences_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_sentences_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('speaker_profiles', schema=None) as batch_op:\n        batch_op.alter_column('total_duration_sec', \n               existing_type=sa.INTEGER(),\n               server_default=None,\n               existing_nullable=False)\n        batch_op.drop_constraint(None, type_='foreignkey')"
    ): (
        "with op.batch_alter_table('speaker_profiles', schema=None) as batch_op:\n        batch_op.alter_column('total_duration_sec', \n               existing_type=sa.INTEGER(),\n               server_default=None,\n               existing_nullable=False)\n        batch_op.drop_constraint('fk_speaker_profiles_speaker_id_speakers', type_='foreignkey')"
    ),
    (
        "with op.batch_alter_table('topic_matrix', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('topic_matrix', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint('fk_topic_matrix_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_topic_matrix_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
    (
        "with op.batch_alter_table('words', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ): (
        "with op.batch_alter_table('words', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('file_id', sa.String(), nullable=False))\n        batch_op.drop_constraint('fk_words_panel_id_panels', type_='foreignkey')\n        batch_op.create_foreign_key('fk_words_file_id_files', 'files', ['file_id'], ['file_id'])\n        batch_op.drop_column('panel_id')"
    ),
}

for target, replacement in upgrade_replacements.items():
    if target in content:
        content = content.replace(target, replacement)
    else:
        normalized_target = target.replace("\r\n", "\n")
        content = content.replace(normalized_target, replacement)

downgrade_replacements = {
    (
        "with op.batch_alter_table('words', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('words', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_words_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_words_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('topic_matrix', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('topic_matrix', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_topic_matrix_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_topic_matrix_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('speaker_profiles', schema=None) as batch_op:\n        batch_op.create_foreign_key(None, 'speakers', ['speaker_id'], ['speaker_id'])\n        batch_op.alter_column('total_duration_sec', \n               existing_type=sa.INTEGER(),\n               server_default=sa.text(\"'0'\"),\n               existing_nullable=False)"
    ): (
        "with op.batch_alter_table('speaker_profiles', schema=None) as batch_op:\n        batch_op.create_foreign_key('fk_speaker_profiles_speaker_id_speakers', 'speakers', ['speaker_id'], ['speaker_id'])\n        batch_op.alter_column('total_duration_sec', \n               existing_type=sa.INTEGER(),\n               server_default=sa.text(\"'0'\"),\n               existing_nullable=False)"
    ),
    (
        "with op.batch_alter_table('sentences', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_sent_file')\n        batch_op.create_index(batch_op.f('idx_sent_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('sentences', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_sentences_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_sentences_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_sent_file')\n        batch_op.create_index(batch_op.f('idx_sent_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('segments', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.create_foreign_key(None, 'speakers', ['speaker_id'], ['speaker_id'])\n        batch_op.drop_index('idx_seg_file')\n        batch_op.create_index(batch_op.f('idx_seg_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('segments', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_segments_file_id_files', type_='foreignkey')\n        batch_op.drop_constraint('fk_segments_speaker_id_speaker_profiles', type_='foreignkey')\n        batch_op.create_foreign_key('fk_segments_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.create_foreign_key('fk_segments_speaker_id_speakers', 'speakers', ['speaker_id'], ['speaker_id'])\n        batch_op.drop_index('idx_seg_file')\n        batch_op.create_index(batch_op.f('idx_seg_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('pattern_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.alter_column('risk_score', \n               existing_type=sa.INTEGER(),\n               server_default=sa.text(\"'0'\"),\n               existing_nullable=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('pattern_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint('fk_pattern_records_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_pattern_records_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.alter_column('risk_score', \n               existing_type=sa.INTEGER(),\n               server_default=sa.text(\"'0'\"),\n               existing_nullable=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('panel_dynamics', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_dyn_panel')\n        batch_op.create_index(batch_op.f('idx_dyn_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('panel_dynamics', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint('fk_panel_dynamics_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_panel_dynamics_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_dyn_panel')\n        batch_op.create_index(batch_op.f('idx_dyn_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('legacy_country_references', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('legacy_country_references', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint('fk_legacy_country_references_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_legacy_country_references_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('discourse_network_edges_legacy', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_net_from')\n        batch_op.create_index(batch_op.f('idx_net_legacy_from'), ['from_country'], unique=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('discourse_network_edges_legacy', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint('fk_discourse_network_edges_legacy_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_discourse_network_edges_legacy_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_index('idx_net_from')\n        batch_op.create_index(batch_op.f('idx_net_legacy_from'), ['from_country'], unique=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('discourse_network_edges', schema=None) as batch_op:\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'], ondelete='CASCADE')\n        batch_op.drop_index('ix_net_weight_high', postgresql_where='weight > 0.5')\n        batch_op.drop_index(batch_op.f('ix_discourse_network_edges_weight'))\n        batch_op.drop_index(batch_op.f('ix_discourse_network_edges_session_id'))\n        batch_op.create_index(batch_op.f('ix_net_weight'), ['weight'], unique=False)\n        batch_op.create_index(batch_op.f('ix_net_session'), ['session_id'], unique=False)\n        batch_op.create_index(batch_op.f('ix_net_actor'), ['actor_id'], unique=False)"
    ): (
        "with op.batch_alter_table('discourse_network_edges', schema=None) as batch_op:\n        batch_op.drop_constraint('fk_discourse_network_edges_panel_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_discourse_network_edges_panel_id_panels', 'panels', ['panel_id'], ['panel_id'], ondelete='CASCADE')\n        batch_op.drop_index('ix_net_weight_high', postgresql_where='weight > 0.5')\n        batch_op.drop_index(batch_op.f('ix_discourse_network_edges_weight'))\n        batch_op.drop_index(batch_op.f('ix_discourse_network_edges_session_id'))\n        batch_op.create_index(batch_op.f('ix_net_weight'), ['weight'], unique=False)\n        batch_op.create_index(batch_op.f('ix_net_session'), ['session_id'], unique=False)\n        batch_op.create_index(batch_op.f('ix_net_actor'), ['actor_id'], unique=False)"
    ),
    (
        "with op.batch_alter_table('dependency_triples', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_index('idx_dep_panel')\n        batch_op.create_index(batch_op.f('idx_dep_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('dependency_triples', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_index('idx_dep_panel')\n        batch_op.create_index(batch_op.f('idx_dep_panel'), ['panel_id'], unique=False)\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('demand_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('demand_records', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=True))\n        batch_op.drop_constraint('fk_demand_records_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_demand_records_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('country_stats', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('country_stats', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_country_stats_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_country_stats_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
    (
        "with op.batch_alter_table('ai_panel_synthesis', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint(None, type_='foreignkey')\n        batch_op.create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_constraint(None, type_='unique')\n        batch_op.drop_column('file_id')"
    ): (
        "with op.batch_alter_table('ai_panel_synthesis', schema=None) as batch_op:\n        batch_op.add_column(sa.Column('panel_id', sa.VARCHAR(), nullable=False))\n        batch_op.drop_constraint('fk_ai_panel_synthesis_file_id_files', type_='foreignkey')\n        batch_op.create_foreign_key('fk_ai_panel_synthesis_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])\n        batch_op.drop_constraint('uq_ai_panel_synthesis_file_id', type_='unique')\n        batch_op.create_unique_constraint('uq_ai_panel_synthesis_panel_id', ['panel_id'])\n        batch_op.drop_column('file_id')"
    ),
}

for target, replacement in downgrade_replacements.items():
    if target in content:
        content = content.replace(target, replacement)
    else:
        normalized_target = target.replace("\r\n", "\n")
        content = content.replace(normalized_target, replacement)


# Now, inject naming_convention parameter into all batch_alter_table calls
# e.g., with op.batch_alter_table('ai_panel_synthesis', schema=None) as batch_op:
# -> with op.batch_alter_table('ai_panel_synthesis', schema=None, naming_convention=naming_convention) as batch_op:

# Define naming_convention dictionary at the top of upgrade and downgrade
upgrade_inject = """def upgrade() -> None:
    # Fetch and drop all views to avoid view validation errors on batch alter
    bind = op.get_bind()
    views = bind.execute(sa.text("SELECT name, sql FROM sqlite_master WHERE type='view'")).fetchall()
    view_defs = []
    for name, sql in views:
        if sql:
            op.execute(f"DROP VIEW IF EXISTS {name}")
            view_defs.append((name, sql))

    naming_convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
"""

downgrade_inject = """def downgrade() -> None:
    # Fetch and drop all views to avoid view validation errors on batch alter
    bind = op.get_bind()
    views = bind.execute(sa.text("SELECT name, sql FROM sqlite_master WHERE type='view'")).fetchall()
    view_defs = []
    for name, sql in views:
        if sql:
            op.execute(f"DROP VIEW IF EXISTS {name}")
            view_defs.append((name, sql))

    naming_convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
"""

content = re.sub(
    r"def upgrade\(\) -> None:\s*# Fetch and drop all views to avoid view validation errors on batch alter.*?# ### commands auto generated by Alembic - please adjust! ###",
    upgrade_inject
    + "    # ### commands auto generated by Alembic - please adjust! ###",
    content,
    flags=re.DOTALL,
)

content = re.sub(
    r"def downgrade\(\) -> None:\s*# Fetch and drop all views to avoid view validation errors on batch alter.*?# ### commands auto generated by Alembic - please adjust! ###",
    downgrade_inject
    + "    # ### commands auto generated by Alembic - please adjust! ###",
    content,
    flags=re.DOTALL,
)

# Replaces all batch_alter_table calls
content = re.sub(
    r"with op\.batch_alter_table\('([^']+)', schema=None\) as batch_op:",
    r"with op.batch_alter_table('\1', schema=None, naming_convention=naming_convention) as batch_op:",
    content,
)

content = re.sub(
    r"with op\.batch_alter_table\(\"([^\"]+)\"\) as batch_op:",
    r"with op.batch_alter_table('\1', naming_convention=naming_convention) as batch_op:",
    content,
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Applied naming_convention to batch_alter_table calls!")
