# src/bb_paxdata/infrastructure/export/tasks.py
from __future__ import annotations

import pathlib
from datetime import datetime, timezone

import nbformat as nbf
import structlog
from celery import Task
from sqlalchemy import select, update

from bb_paxdata.infrastructure.db.discourse_network_table import (
    DiscourseNetworkEdgeTable,
)
from bb_paxdata.infrastructure.db.export_job_table import ExportJob, ExportStatus
from bb_paxdata.infrastructure.db.models import File
from bb_paxdata.infrastructure.db.session import async_session_maker, get_db_session
from bb_paxdata.infrastructure.export.gexf_builder import GEXFBuilder
from bb_paxdata.infrastructure.export.latex_utils import render_latex_template
from bb_paxdata.infrastructure.export.storage import StorageManager
from bb_paxdata.infrastructure.tasks.celery_app import get_celery_app

celery_app = get_celery_app()

logger = structlog.get_logger(__name__)
storage = StorageManager()


async def update_job_status(
    job_id: str,
    status: str,
    progress_pct: int | None = None,
    download_url: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update ExportJob status in database."""
    async with async_session_maker() as session:
        values = {"status": status}
        if progress_pct is not None:
            values["progress_pct"] = progress_pct
        if download_url is not None:
            values["download_url"] = download_url
        if error_message is not None:
            values["error_message"] = error_message
        if status == ExportStatus.COMPLETED:
            values["completed_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.execute(
            update(ExportJob).where(ExportJob.id == job_id).values(**(values))
        )
        await session.commit()


def fetch_session_data(file_id: str, date_range: dict | None = None) -> dict:
    """Fetch session data from database for export."""
    with get_db_session() as session:
        stmt = select(File).where(File.file_id == file_id)
        file_obj = session.scalars(stmt).first()
        if not file_obj:
            raise ValueError(f"File not found: {file_id}")

        speakers_data = []
        statements_data = []
        risks_data = []
        edges_data = []

        # Collect segments as statements
        for segment in file_obj.segments:
            statements_data.append(
                {
                    "id": segment.seg_id,
                    "speaker_id": segment.speaker_id,
                    "speaker_name": segment.speaker_name,
                    "text": segment.text,
                    "risk_score": segment.risk_score,
                    "sbi_score": segment.sbi_score,
                    "timestamp": segment.ts_start_sec,
                    "country": segment.country,
                    "dominant_topic": segment.dominant_topic,
                }
            )

            # Collect risk signals as risks
            if segment.risk_score >= 5:
                risks_data.append(
                    {
                        "id": f"risk_{segment.seg_id}",
                        "level": "HIGH" if segment.risk_score >= 7 else "MEDIUM",
                        "category": segment.dominant_topic or "GENERAL",
                        "statement_id": segment.seg_id,
                        "speaker": segment.speaker_name,
                        "timestamp": segment.ts_start_sec,
                        "score": segment.risk_score,
                    }
                )

        # Collect network edges
        for edge in file_obj.network_edges:
            edges_data.append(
                {
                    "source": edge.actor_id,
                    "target": edge.concept_id,
                    "weight": float(edge.weight) if edge.weight else 1.0,
                    "type": "REFERENCE",
                    "timestamps": [],
                }
            )

        return {
            "session": {
                "id": file_obj.file_id,
                "title": file_obj.title or file_obj.file_name,
                "date": (
                    file_obj.imported_at.isoformat() if file_obj.imported_at else None
                ),
                "n_segments": file_obj.n_segments,
                "n_speakers": file_obj.n_speakers,
            },
            "speakers": speakers_data,
            "statements": statements_data,
            "risks": risks_data,
            "edges": edges_data,
        }


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


@celery_app.task(bind=True, name="export.pdf", max_retries=3, default_retry_delay=30)
def generate_pdf_export_task(
    self: Task, job_id: str, file_id: str, options: dict
) -> dict:
    """
    Celery task for PDF export with LaTeX compilation.
    """
    import asyncio

    logger.info("Starting PDF export for job_id: %s, file_id: %s", job_id, file_id)

    try:
        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=5))
        self.update_state(
            state="PROGRESS", meta={"step": "fetching_data", "percent": 10}
        )

        session_data = fetch_session_data(file_id)

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=30))
        self.update_state(
            state="PROGRESS", meta={"step": "generating_pdf", "percent": 40}
        )

        # For now, generate a simple text-based PDF placeholder
        # Full LaTeX implementation would require pdflatex in Docker
        from io import BytesIO

        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)

        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(72, 750, session_data["session"]["title"])

        # Metadata
        p.setFont("Helvetica", 10)
        p.drawString(72, 730, f"Date: {session_data['session']['date'] or 'N/A'}")
        p.drawString(72, 715, f"Segments: {session_data['session']['n_segments']}")
        p.drawString(72, 700, f"Speakers: {session_data['session']['n_speakers']}")

        # Statements summary
        y_pos = 670
        p.setFont("Helvetica-Bold", 12)
        p.drawString(72, y_pos, "Statements Summary")
        y_pos -= 20

        p.setFont("Helvetica", 9)
        for stmt in session_data["statements"][:20]:  # Limit to first 20 for demo
            if y_pos < 50:
                p.showPage()
                y_pos = 750
            text = f"{stmt['speaker_name']}: {stmt['text'][:80]}..."
            p.drawString(72, y_pos, text)
            y_pos -= 12

        p.save()
        pdf_bytes = buffer.getvalue()

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=80))
        self.update_state(state="PROGRESS", meta={"step": "uploading", "percent": 90})

        filename = f"export_{file_id}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        url = storage.upload_export(
            job_id=job_id,
            file_bytes=pdf_bytes,
            content_type="application/pdf",
            filename=filename,
        )

        asyncio.run(
            update_job_status(
                job_id, ExportStatus.COMPLETED, download_url=url, progress_pct=100
            )
        )

        logger.info("PDF export completed for job_id: %s", job_id)
        return {"status": "SUCCESS", "job_id": job_id, "download_url": url}

    except Exception as exc:
        logger.error("PDF export failed for job_id: %s", job_id, exc_info=True)
        asyncio.run(
            update_job_status(job_id, ExportStatus.FAILED, error_message=str(exc))
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="export.excel", max_retries=3, default_retry_delay=30)
def generate_excel_export_task(
    self: Task, job_id: str, file_id: str, options: dict
) -> dict:
    """
    Celery task for Excel export with multiple sheets and charts.
    """
    import asyncio

    logger.info("Starting Excel export for job_id: %s, file_id: %s", job_id, file_id)

    try:
        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=5))
        self.update_state(
            state="PROGRESS", meta={"step": "fetching_data", "percent": 10}
        )

        session_data = fetch_session_data(file_id, options.get("date_range"))

        total_rows = len(session_data["statements"])
        if total_rows > 200_000:
            raise ValueError(f"Too many rows: {total_rows}. Max 200k.")

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=30))
        self.update_state(
            state="PROGRESS", meta={"step": "generating_excel", "percent": 40}
        )

        from io import BytesIO

        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        wb = Workbook()
        wb.remove(wb.active)

        # Summary Sheet
        ws_summary = wb.create_sheet("Summary")
        ws_summary["A1"] = session_data["session"]["title"]
        ws_summary["A1"].font = Font(bold=True, size=14)
        ws_summary["A3"] = f"Date: {session_data['session']['date'] or 'N/A'}"
        ws_summary["A4"] = f"Segments: {session_data['session']['n_segments']}"
        ws_summary["A5"] = f"Speakers: {session_data['session']['n_speakers']}"
        ws_summary["A6"] = f"Total Statements: {total_rows}"

        # Statements Sheet
        ws_statements = wb.create_sheet("Statements")
        headers = ["ID", "Speaker", "Text", "Risk Score", "SBI Score", "Topic"]
        for col, header in enumerate(headers, 1):
            cell = ws_statements.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="1F3864", end_color="1F3864", fill_type="solid"
            )

        for row_idx, stmt in enumerate(session_data["statements"], 2):
            if row_idx > 50001:  # Max 50k rows per sheet
                break
            ws_statements.cell(row=row_idx, column=1, value=stmt["id"])
            ws_statements.cell(row=row_idx, column=2, value=stmt["speaker_name"])
            ws_statements.cell(row=row_idx, column=3, value=stmt["text"][:100])
            ws_statements.cell(row=row_idx, column=4, value=stmt["risk_score"])
            ws_statements.cell(row=row_idx, column=5, value=stmt["sbi_score"])
            ws_statements.cell(
                row=row_idx, column=6, value=stmt["dominant_topic"] or ""
            )

        # Risks Sheet
        ws_risks = wb.create_sheet("Risks")
        risk_headers = ["Risk ID", "Level", "Category", "Speaker", "Score"]
        for col, header in enumerate(risk_headers, 1):
            cell = ws_risks.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)

        for row_idx, risk in enumerate(session_data["risks"], 2):
            ws_risks.cell(row=row_idx, column=1, value=risk["id"])
            ws_risks.cell(row=row_idx, column=2, value=risk["level"])
            ws_risks.cell(row=row_idx, column=3, value=risk["category"])
            ws_risks.cell(row=row_idx, column=4, value=risk["speaker"])
            ws_risks.cell(row=row_idx, column=5, value=risk["score"])

        buffer = BytesIO()
        wb.save(buffer)
        excel_bytes = buffer.getvalue()

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=80))
        self.update_state(state="PROGRESS", meta={"step": "uploading", "percent": 90})

        filename = f"export_{file_id}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        url = storage.upload_export(
            job_id=job_id,
            file_bytes=excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )

        asyncio.run(
            update_job_status(
                job_id, ExportStatus.COMPLETED, download_url=url, progress_pct=100
            )
        )

        logger.info("Excel export completed for job_id: %s", job_id)
        return {"status": "SUCCESS", "job_id": job_id, "download_url": url}

    except Exception as exc:
        logger.error("Excel export failed for job_id: %s", job_id, exc_info=True)
        asyncio.run(
            update_job_status(job_id, ExportStatus.FAILED, error_message=str(exc))
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="export.gexf", max_retries=3, default_retry_delay=30)
def generate_gexf_export_task(
    self: Task, job_id: str, file_id: str, options: dict
) -> dict:
    """
    Celery task for GEXF export with network analysis.
    """
    import asyncio

    logger.info("Starting GEXF export for job_id: %s, file_id: %s", job_id, file_id)

    try:
        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=5))
        self.update_state(
            state="PROGRESS", meta={"step": "fetching_data", "percent": 10}
        )

        session_data = fetch_session_data(file_id)

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=30))
        self.update_state(
            state="PROGRESS", meta={"step": "building_network", "percent": 40}
        )

        builder = GEXFBuilder(description=f"Network Export for {file_id}")
        builder.add_node_attribute("0", "type", "string")
        builder.add_node_attribute("1", "risk_score", "double")

        # Add nodes and edges
        node_map = {}
        for stmt in session_data["statements"]:
            speaker_id = stmt["speaker_id"] or f"unknown_{stmt['speaker_name']}"
            if speaker_id not in node_map:
                builder.add_node(
                    speaker_id,
                    stmt["speaker_name"],
                    {"type": "Speaker", "risk_score": str(stmt["risk_score"])},
                )
                node_map[speaker_id] = True

        for edge in session_data["edges"]:
            builder.add_edge(
                source_id=edge["source"],
                target_id=edge["target"],
                weight=edge["weight"],
            )

        asyncio.run(update_job_status(job_id, ExportStatus.PROCESSING, progress_pct=80))
        self.update_state(state="PROGRESS", meta={"step": "serializing", "percent": 90})

        gexf_bytes = builder.to_string().encode("utf-8")

        filename = f"export_{file_id}_{datetime.now():%Y%m%d_%H%M%S}.gexf"
        url = storage.upload_export(
            job_id=job_id,
            file_bytes=gexf_bytes,
            content_type="application/gexf+xml",
            filename=filename,
        )

        asyncio.run(
            update_job_status(
                job_id, ExportStatus.COMPLETED, download_url=url, progress_pct=100
            )
        )

        logger.info("GEXF export completed for job_id: %s", job_id)
        return {"status": "SUCCESS", "job_id": job_id, "download_url": url}

    except Exception as exc:
        logger.error("GEXF export failed for job_id: %s", job_id, exc_info=True)
        asyncio.run(
            update_job_status(job_id, ExportStatus.FAILED, error_message=str(exc))
        )
        raise self.retry(exc=exc)
