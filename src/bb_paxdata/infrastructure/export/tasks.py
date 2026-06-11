# src/bb_paxdata/infrastructure/export/tasks.py
from __future__ import annotations

import logging
import pathlib

import nbformat as nbf
from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)
from bb_paxdata.infrastructure.db.models import File
from bb_paxdata.infrastructure.db.session import get_db_session
from bb_paxdata.infrastructure.export.gexf_builder import GEXFBuilder
from bb_paxdata.infrastructure.export.latex_utils import render_latex_template
from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app
from celery import Task
from sqlalchemy import select

celery_app = get_celery_app()

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="export.latex_report")
def export_latex_report_task(
    self: Task,
    file_id: str,
    template_str: str,
    output_path: str,
) -> dict:
    """
    Celery task that compiles and saves a LaTeX report from a File analysis.
    """
    logger.info("Starting LaTeX report export for file_id: %s", file_id)
    self.update_state(state="PROGRESS", meta={"step": "fetching_data", "percent": 10})

    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with get_db_session() as session:
        # Load File and associated segments
        stmt = select(File).where(File.file_id == file_id)
        file_obj = session.scalars(stmt).first()
        if not file_obj:
            raise ValueError(f"File analysis not found: {file_id}")

        self.update_state(
            state="PROGRESS", meta={"step": "preparing_context", "percent": 40}
        )

        # Build context
        segments_data = []
        for segment in file_obj.segments:
            sentences_data = []
            for sentence in segment.sentences:
                sentences_data.append(
                    {
                        "text": sentence.text,
                        "risk_score": sentence.risk_score,
                        "sentiment_score": sentence.vader_compound,
                        "power_level": sentence.power_level,
                    }
                )
            segments_data.append(
                {
                    "segment_index": segment.seq_order or 0,
                    "summary": (
                        segment.text[:100] + "..."
                        if len(segment.text) > 100
                        else segment.text
                    ),
                    "risk_level": str(segment.risk_score),
                    "sentences": sentences_data,
                }
            )

        context = {
            "title": file_obj.title or file_obj.file_name,
            "created_at": (
                file_obj.imported_at.strftime("%Y-%m-%d %H:%M:%S")
                if file_obj.imported_at
                else ""
            ),
            "status": "COMPLETED",
            "segments": segments_data,
        }

    self.update_state(
        state="PROGRESS", meta={"step": "rendering_template", "percent": 70}
    )
    rendered = render_latex_template(template_str, context)

    self.update_state(state="PROGRESS", meta={"step": "writing_file", "percent": 90})
    out_p.write_text(rendered, encoding="utf-8")

    logger.info("Successfully exported LaTeX report to %s", output_path)
    return {"status": "SUCCESS", "output_path": str(out_p.resolve())}


@celery_app.task(bind=True, name="export.jupyter_notebook")
def export_jupyter_notebook_task(
    self: Task,
    file_id: str,
    output_path: str,
) -> dict:
    """
    Celery task that creates a programmatically generated Jupyter Notebook (.ipynb)
    representing the analysis data and exports it.
    """
    logger.info("Starting Jupyter Notebook export for file_id: %s", file_id)
    self.update_state(state="PROGRESS", meta={"step": "fetching_data", "percent": 20})

    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with get_db_session() as session:
        stmt = select(File).where(File.file_id == file_id)
        file_obj = session.scalars(stmt).first()
        if not file_obj:
            raise ValueError(f"File analysis not found: {file_id}")

        segments_data = []
        for segment in file_obj.segments:
            segments_data.append(
                {
                    "segment_id": segment.seg_id,
                    "risk_score": segment.risk_score,
                    "dki_score": segment.dki_score,
                    "sbi_score": segment.sbi_score,
                    "text": (
                        segment.text[:200] + "..."
                        if len(segment.text) > 200
                        else segment.text
                    ),
                }
            )

        self.update_state(
            state="PROGRESS", meta={"step": "generating_notebook", "percent": 50}
        )

        # Create notebook using nbformat
        nb = nbf.v4.new_notebook()

        title_md = (
            f"# BB-PAXDATA Analiz Raporu: {file_obj.title or file_obj.file_name}\n"
            f"**File ID:** {file_id}\n"
            f"**Tarih:** {file_obj.imported_at.isoformat() if file_obj.imported_at else 'N/A'}\n"
            f"**Segment Sayısı:** {len(file_obj.segments)}\n"
        )
        nb["cells"].append(nbf.v4.new_markdown_cell(title_md))

        # Add data code cell
        data_code = (
            f"# Analysis segments payload\n"
            f"segments_data = {segments_data}\n\n"
            f"import pandas as pd\n"
            f"df = pd.DataFrame(segments_data)\n"
            f"df.head()"
        )
        nb["cells"].append(nbf.v4.new_code_cell(data_code))

        # Add visualization code cell
        viz_code = (
            "import matplotlib.pyplot as plt\n"
            "if not df.empty:\n"
            "    fig, ax = plt.subplots(1, 2, figsize=(12, 5))\n"
            "    df['risk_score'].plot(kind='bar', ax=ax[0], title='Risk Score per Segment')\n"
            "    df['dki_score'].plot(kind='line', ax=ax[1], title='DKI Score Trend', marker='o')\n"
            "    plt.tight_layout()\n"
            "    plt.show()\n"
            "else:\n"
            "    print('No data available to plot')"
        )
        nb["cells"].append(nbf.v4.new_code_cell(viz_code))

    self.update_state(state="PROGRESS", meta={"step": "writing_file", "percent": 85})

    with open(out_p, "w", encoding="utf-8") as f:
        nbf.write(nb, f)

    logger.info("Successfully exported Jupyter Notebook to %s", output_path)
    return {"status": "SUCCESS", "output_path": str(out_p.resolve())}


@celery_app.task(bind=True, name="export.gexf_network")
def export_gexf_network_task(
    self: Task,
    file_id: str,
    output_path: str,
    description: str = "Fischer DNA Network Export",
) -> dict:
    """
    Celery task that exports Fischer Discourse Network edges for a File
    to Gephi-compatible GEXF format.
    """
    logger.info("Starting GEXF network export for file_id: %s", file_id)
    self.update_state(state="PROGRESS", meta={"step": "fetching_edges", "percent": 20})

    out_p = pathlib.Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with get_db_session() as session:
        stmt = select(DiscourseNetworkEdgeTable).where(
            DiscourseNetworkEdgeTable.file_id == file_id
        )
        edges = session.scalars(stmt).all()

        builder = GEXFBuilder(description=description)
        builder.add_node_attribute("0", "type", "string")

        total_edges = len(edges)
        if total_edges == 0:
            logger.warning("No network edges found for file_id: %s", file_id)

        self.update_state(
            state="PROGRESS", meta={"step": "building_graph", "percent": 40}
        )

        for i, edge in enumerate(edges):
            # Dynamic updates for large graphs
            if i % max(1, total_edges // 10) == 0:
                percent = 40 + int((i / total_edges) * 40)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "step": f"processing_edge_{i}/{total_edges}",
                        "percent": percent,
                    },
                )

            # Add bipartite nodes
            builder.add_node(edge.actor_id, edge.actor_id, {"type": "Actor"})
            builder.add_node(edge.concept_id, edge.concept_id, {"type": "Concept"})

            # Add edge
            builder.add_edge(
                source_id=edge.actor_id,
                target_id=edge.concept_id,
                weight=float(edge.weight) if edge.weight is not None else 1.0,
            )

    self.update_state(state="PROGRESS", meta={"step": "serializing_xml", "percent": 90})
    xml_str = builder.to_string()

    out_p.write_text(xml_str, encoding="utf-8")

    logger.info("Successfully exported GEXF Network to %s", output_path)
    return {"status": "SUCCESS", "output_path": str(out_p.resolve())}
