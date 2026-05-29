import re

filepath = r"c:\Users\THINKPAD\Desktop\BB-PAXDATA\alembic\versions\84643356932b_merge_panels_and_processed_files_into_.py"

with open(filepath, encoding="utf-8") as f:
    content = f.read()

# Let's clean up all constraint names first by replacing all named constraints back to None
# This resets the file to a clean state.
content = re.sub(
    r"drop_constraint\('[^']+', type_='foreignkey'\)",
    "drop_constraint(None, type_='foreignkey')",
    content,
)
content = re.sub(
    r"drop_constraint\('[^']+', type_='unique'\)",
    "drop_constraint(None, type_='unique')",
    content,
)
content = re.sub(r"create_foreign_key\('[^']+',", "create_foreign_key(None,", content)
content = re.sub(
    r"create_unique_constraint\('[^']+',", "create_unique_constraint(None,", content
)

# Now let's find the upgrade and downgrade functions.
upgrade_part = re.search(
    r"def upgrade\(\) -> None:(.*?)def downgrade\(\) -> None:", content, re.DOTALL
)
downgrade_part = re.search(r"def downgrade\(\) -> None:(.*?)$", content, re.DOTALL)


def process_function_body(body_text, is_downgrade=False):
    # Parse each batch_alter_table block
    # Pattern: with op.batch_alter_table('table_name', ...) as batch_op:
    # followed by lines of code inside the block (indented by spaces)
    pattern = r"(with op\.batch_alter_table\('(\w+)',.*?\n)(.*?)(?=\n\s*with op\.batch_alter_table|\n\s*#|\n\s*def|\n\s*op\.drop_table|\n\s*op\.create_table|$)"

    def replacer(match):
        header = match.group(1)
        table_name = match.group(2)
        body = match.group(3)

        # Replace create_unique_constraint(None, ['file_id']) / ['panel_id']
        body = re.sub(
            r"create_unique_constraint\(None,\s*\['file_id'\]\)",
            f"create_unique_constraint('uq_{table_name}_file_id', ['file_id'])",
            body,
        )
        body = re.sub(
            r"create_unique_constraint\(None,\s*\['panel_id'\]\)",
            f"create_unique_constraint('uq_{table_name}_panel_id', ['panel_id'])",
            body,
        )

        # Replace drop_constraint(None, type_='unique')
        body = re.sub(
            r"drop_constraint\(None,\s*type_='unique'\)",
            (
                f"drop_constraint('uq_{table_name}_file_id', type_='unique')"
                if is_downgrade
                else f"drop_constraint('uq_{table_name}_panel_id', type_='unique')"
            ),
            body,
        )

        # Special case: segments has multiple foreign keys
        if table_name == "segments":
            if not is_downgrade:
                # upgrade
                # first drop: panels, second drop: speakers
                body = body.replace(
                    "drop_constraint(None, type_='foreignkey')",
                    "drop_constraint('fk_segments_panel_id_panels', type_='foreignkey')",
                    1,
                )
                body = body.replace(
                    "drop_constraint(None, type_='foreignkey')",
                    "drop_constraint('fk_segments_speaker_id_speakers', type_='foreignkey')",
                    1,
                )
                # first create: files, second create: speaker_profiles
                body = body.replace(
                    "create_foreign_key(None, 'files', ['file_id'], ['file_id'])",
                    "create_foreign_key('fk_segments_file_id_files', 'files', ['file_id'], ['file_id'])",
                    1,
                )
                body = body.replace(
                    "create_foreign_key(None, 'speaker_profiles', ['speaker_id'], ['speaker_id'])",
                    "create_foreign_key('fk_segments_speaker_id_speaker_profiles', 'speaker_profiles', ['speaker_id'], ['speaker_id'])",
                    1,
                )
            else:
                # downgrade
                # first drop: files, second drop: speaker_profiles
                body = body.replace(
                    "drop_constraint(None, type_='foreignkey')",
                    "drop_constraint('fk_segments_file_id_files', type_='foreignkey')",
                    1,
                )
                body = body.replace(
                    "drop_constraint(None, type_='foreignkey')",
                    "drop_constraint('fk_segments_speaker_id_speaker_profiles', type_='foreignkey')",
                    1,
                )
                # first create: panels, second create: speakers
                body = body.replace(
                    "create_foreign_key(None, 'panels', ['panel_id'], ['panel_id'])",
                    "create_foreign_key('fk_segments_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])",
                    1,
                )
                body = body.replace(
                    "create_foreign_key(None, 'speakers', ['speaker_id'], ['speaker_id'])",
                    "create_foreign_key('fk_segments_speaker_id_speakers', 'speakers', ['speaker_id'], ['speaker_id'])",
                    1,
                )
        elif table_name == "speaker_profiles":
            if not is_downgrade:
                body = body.replace(
                    "drop_constraint(None, type_='foreignkey')",
                    "drop_constraint('fk_speaker_profiles_speaker_id_speakers', type_='foreignkey')",
                )
            else:
                body = body.replace(
                    "create_foreign_key(None, 'speakers', ['speaker_id'], ['speaker_id'])",
                    "create_foreign_key('fk_speaker_profiles_speaker_id_speakers', 'speakers', ['speaker_id'], ['speaker_id'])",
                )
        elif not is_downgrade:
            # upgrade
            # drop_constraint: referencing panels
            body = re.sub(
                r"drop_constraint\(None,\s*type_='foreignkey'\)",
                f"drop_constraint('fk_{table_name}_panel_id_panels', type_='foreignkey')",
                body,
            )
            # create_foreign_key: referencing files (on file_id or panel_id)
            body = re.sub(
                r"create_foreign_key\(None,\s*'files',\s*\['file_id'\],\s*\['file_id'\]\)",
                f"create_foreign_key('fk_{table_name}_file_id_files', 'files', ['file_id'], ['file_id'])",
                body,
            )
            body = re.sub(
                r"create_foreign_key\(None,\s*'files',\s*\['panel_id'\],\s*\['file_id'\],\s*ondelete='CASCADE'\)",
                f"create_foreign_key('fk_{table_name}_panel_id_files', 'files', ['panel_id'], ['file_id'], ondelete='CASCADE')",
                body,
            )
        else:
            # downgrade
            # drop_constraint: referencing files
            body = re.sub(
                r"drop_constraint\(None,\s*type_='foreignkey'\)",
                f"drop_constraint('fk_{table_name}_file_id_files', type_='foreignkey')",
                body,
            )
            # special case for discourse_network_edges in downgrade where column is panel_id referencing files
            body = re.sub(
                r"drop_constraint\('fk_discourse_network_edges_panel_id_files',\s*type_='foreignkey'\)",  # wait it was reset to None
                "drop_constraint('fk_discourse_network_edges_panel_id_files', type_='foreignkey')",
                body,
            )
            # create_foreign_key: referencing panels
            body = re.sub(
                r"create_foreign_key\(None,\s*'panels',\s*\['panel_id'\],\s*\['panel_id'\]\)",
                f"create_foreign_key('fk_{table_name}_panel_id_panels', 'panels', ['panel_id'], ['panel_id'])",
                body,
            )
            body = re.sub(
                r"create_foreign_key\(None,\s*'panels',\s*\['panel_id'\],\s*\['panel_id'\],\s*ondelete='CASCADE'\)",
                f"create_foreign_key('fk_{table_name}_panel_id_panels', 'panels', ['panel_id'], ['panel_id'], ondelete='CASCADE')",
                body,
            )
            # speaker_profiles referencing speakers in downgrade
            body = re.sub(
                r"create_foreign_key\(None,\s*'speakers',\s*\['speaker_id'\],\s*\['speaker_id'\]\)",
                f"create_foreign_key('fk_{table_name}_speaker_id_speakers', 'speakers', ['speaker_id'], ['speaker_id'])",
                body,
            )

        return header + body

    new_body = re.sub(pattern, replacer, body_text, flags=re.DOTALL)
    return new_body


# Process upgrade and downgrade bodies
new_upgrade = process_function_body(upgrade_part.group(1), is_downgrade=False)
new_downgrade = process_function_body(downgrade_part.group(1), is_downgrade=True)

# Reassemble content
content = (
    content[: upgrade_part.start(1)]
    + new_upgrade
    + content[upgrade_part.end(1) : downgrade_part.start(1)]
    + new_downgrade
    + content[downgrade_part.end(1) :]
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Migration constraints successfully processed via regex!")
