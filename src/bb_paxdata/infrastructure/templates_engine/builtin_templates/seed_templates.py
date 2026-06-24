# src/bb_paxdata/infrastructure/templates_engine/builtin_templates/seed_templates.py
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from bb_paxdata.infrastructure.db.session import async_session_maker
from bb_paxdata.infrastructure.db.template_table import (
    ReportTemplate,
    ReportTemplateVersion,
    TemplateCategory,
)
from bb_paxdata.infrastructure.templates_engine.engine import SafeTemplateEngine


async def seed_builtin_templates() -> None:
    """
    Seed built-in system templates into the database.
    This should be run during application startup or migration.
    """
    templates_dir = Path(__file__).parent

    builtin_templates = [
        {
            "name": "BM Güvenlik Konseyi Analiz Raporu",
            "category": TemplateCategory.UN_SECURITY_COUNCIL.value,
            "file": "un_security_council.html.jinja2",
            "description": "UNSC oturumları için standart analiz formatı",
            "output_format": "html",
        },
        {
            "name": "İkili Görüşme Analiz Raporu",
            "category": TemplateCategory.BILATERAL.value,
            "file": "bilateral_meeting.html.jinja2",
            "description": "İki taraf arasındaki diyalog dengesi analizi",
            "output_format": "html",
        },
        {
            "name": "Dönemsel Eğilim Raporu",
            "category": TemplateCategory.PERIODIC.value,
            "file": "periodic_trend.html.jinja2",
            "description": "Birden fazla session karşılaştırmalı trend analizi",
            "output_format": "html",
        },
        {
            "name": "Karşılaştırmalı Analiz Raporu",
            "category": TemplateCategory.COMPARATIVE.value,
            "file": "comparative_analysis.html.jinja2",
            "description": "2-4 session karşılaştırmalı detaylı analiz",
            "output_format": "html",
        },
    ]

    engine = SafeTemplateEngine()

    async with async_session_maker() as session:
        for tmpl_config in builtin_templates:
            template_path = templates_dir / tmpl_config["file"]

            if not template_path.exists():
                print(f"Warning: Template file not found: {template_path}")
                continue

            content = template_path.read_text(encoding="utf-8")

            # Check if template already exists
            stmt = select(ReportTemplate).where(
                ReportTemplate.category == tmpl_config["category"],
                ReportTemplate.is_system,
            )
            existing = await session.scalar(stmt)

            if existing:
                # Check if content changed
                if existing.content != content:
                    # Create version snapshot
                    latest_version = await session.scalar(
                        select(ReportTemplateVersion)
                        .where(ReportTemplateVersion.template_id == existing.id)
                        .order_by(ReportTemplateVersion.version_number.desc())
                    )
                    new_version_num = (
                        (latest_version.version_number + 1) if latest_version else 1
                    )

                    version = ReportTemplateVersion(
                        template_id=existing.id,
                        version_number=new_version_num,
                        content=existing.content,
                        change_summary="System template update",
                        created_by="system",
                    )
                    session.add(version)

                    # Update template
                    existing.content = content
                    existing.variables_used = json.dumps(
                        engine.extract_variables(content)
                    )
                    print(f"Updated system template: {tmpl_config['name']}")
                else:
                    print(f"System template unchanged: {tmpl_config['name']}")
            else:
                # Create new template
                variables = engine.extract_variables(content)
                template = ReportTemplate(
                    name=tmpl_config["name"],
                    description=tmpl_config["description"],
                    category=tmpl_config["category"],
                    content=content,
                    output_format=tmpl_config["output_format"],
                    variables_used=json.dumps(variables),
                    is_published=True,
                    is_system=True,
                    created_by="system",
                )
                session.add(template)
                print(f"Created system template: {tmpl_config['name']}")

        await session.commit()
        print("System templates seeded successfully")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed_builtin_templates())
