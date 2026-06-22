#!/usr/bin/env python
"""Seed prompt_versions table with initial prompts from build_default_registry."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bb_paxdata.application.domain.services.prompt_registry import (
    build_default_registry,
)
from bb_paxdata.infrastructure.db.models import PromptVersion as PromptVersionORM
from bb_paxdata.infrastructure.db.session import get_db_session


def seed_prompt_versions() -> None:
    """Seed the prompt_versions table with prompts from build_default_registry."""
    print("Seeding prompt_versions table...")

    with get_db_session() as db:
        # Check if table is empty
        existing_count = db.query(PromptVersionORM).count()
        if existing_count > 0:
            print(f"Table already has {existing_count} prompts. Skipping seed.")
            return

        # Build default registry
        default_registry = build_default_registry()

        # Insert prompts into database
        for prompt_id, versions in default_registry.list_prompts().items():
            for version_str in versions:
                prompt = default_registry.get_version(prompt_id, version_str)
                if prompt:
                    orm = PromptVersionORM(
                        prompt_id=prompt.prompt_id,
                        version=prompt.version,
                        template=prompt.template,
                        description=prompt.description,
                        is_active=prompt.is_active,
                        model_name=prompt.model_name,
                        language=prompt.language,
                        academic_ref=prompt.academic_ref,
                        template_hash=prompt.template_hash,
                    )
                    db.add(orm)
                    print(f"  Added: {prompt.full_version_id}")

        db.commit()
        print(
            f"Seeding complete. Total prompts: {len(default_registry.list_prompts())}"
        )


if __name__ == "__main__":
    seed_prompt_versions()
