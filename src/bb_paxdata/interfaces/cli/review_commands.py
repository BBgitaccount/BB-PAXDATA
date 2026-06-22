"""review_commands.py — CLI interface for human review submission, calibration runs, and viewing disagreements."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Database session maker helper
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bb_paxdata.application.services.calibration_service import CalibrationService
from bb_paxdata.application.use_cases.submit_human_review import (
    SubmitHumanReviewCommand,
    SubmitHumanReviewUseCase,
)
from bb_paxdata.infrastructure.db.repositories.unit_of_work import SqlAlchemyUnitOfWork

# Safe encoding reconfiguration on Windows to prevent UnicodeEncodeErrors with Turkish characters
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass


def _get_database_url() -> str:
    from bb_paxdata.config.settings import get_settings

    return get_settings().database_url or "sqlite+aiosqlite:///paxdata.db"


def _get_uow_factory() -> Callable[[], SqlAlchemyUnitOfWork]:
    engine = create_async_engine(_get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return lambda: SqlAlchemyUnitOfWork(session_factory)


app = typer.Typer(name="review", help="Human Review ve Kalibrasyon komutları")
console = Console()


@app.command("submit")
def submit_review(
    analysis_id: str = typer.Option(..., help="İncelenecek analiz ID"),
    reviewer_id: str = typer.Option(..., help="Uzman ID (örn: dr_yilmaz_01)"),
    human_frame: str | None = typer.Option(None, help="Uzmanın frame değerlendirmesi"),
    human_risk: str | None = typer.Option(
        None, help="Uzmanın risk değerlendirmesi (LOW/MED/HIGH/CRITICAL)"
    ),
    human_sbi: float | None = typer.Option(None, help="Uzmanın SBI skoru"),
    human_sentiment: float | None = typer.Option(None, help="Uzmanın sentiment skoru"),
    reason: str | None = typer.Option(None, help="Anlaşmazlık nedeni/açıklama"),
    duration: int | None = typer.Option(None, help="Değerlendirme süresi (saniye)"),
) -> None:
    """Human review değerlendirmesi gönderir."""
    asyncio.run(
        _run_submit(
            analysis_id=analysis_id,
            reviewer_id=reviewer_id,
            human_frame=human_frame,
            human_risk=human_risk,
            human_sbi=human_sbi,
            human_sentiment=human_sentiment,
            reason=reason,
            duration=duration,
        )
    )


async def _run_submit(
    analysis_id: str,
    reviewer_id: str,
    human_frame: str | None,
    human_risk: str | None,
    human_sbi: float | None,
    human_sentiment: float | None,
    reason: str | None,
    duration: int | None,
) -> None:
    uow_factory = _get_uow_factory()
    use_case = SubmitHumanReviewUseCase(uow_factory)
    command = SubmitHumanReviewCommand(
        analysis_id=analysis_id,
        reviewer_id=reviewer_id,
        human_frame=human_frame,
        human_risk=human_risk,
        human_sbi=human_sbi,
        human_sentiment=human_sentiment,
        disagreement_reason=reason,
        review_duration_seconds=duration,
    )

    console.print(
        f"[bold cyan]Review gönderiliyor...[/bold cyan] (Reviewer: {reviewer_id}, Analysis: {analysis_id})"
    )
    try:
        review = await use_case.execute(command)
        console.print(
            f"[green][OK] Human Review başarıyla kaydedildi![/green] ID: {review.id}"
        )
        console.print(
            f"  - Durum: [bold yellow]{review.agreement_status.value}[/bold yellow]"
        )
        if review.has_frame_disagreement:
            console.print(
                f"  - Frame Anlaşmazlığı: AI '{review.ai_dominant_frame}' vs Uzman '{review.human_dominant_frame}'"
            )
        if review.has_risk_disagreement:
            console.print(
                f"  - Risk Anlaşmazlığı: AI '{review.ai_risk_level}' vs Uzman '{review.human_risk_level}'"
            )
    except Exception as exc:
        console.print(f"[red][ERROR] Hata oluştu:[/red] {exc}")
        sys.exit(1)


@app.command("calibrate")
def calibrate(
    prompt_version: str = typer.Option(
        ..., help="Kalibrasyon yapılacak prompt versiyonu"
    ),
    days_back: int = typer.Option(
        7, help="Kaç gün geriye dönük kalibrasyon yapılacağı"
    ),
) -> None:
    """Belirtilen prompt versiyonu için Cohen's Kappa ve F1 skorlarını hesaplar ve kalibrasyon raporu üretir."""
    asyncio.run(_run_calibrate(prompt_version=prompt_version, days_back=days_back))


async def _run_calibrate(prompt_version: str, days_back: int) -> None:
    uow_factory = _get_uow_factory()
    service = CalibrationService(uow_factory)

    console.print(
        f"[bold cyan]Kalibrasyon çalıştırılıyor...[/bold cyan] Prompt: {prompt_version}, Geriye Dönük Gün: {days_back}"
    )
    try:
        report = await service.run_weekly_calibration(
            prompt_version=prompt_version, days_back=days_back
        )

        # Display results in a nice table
        table = Table(
            title=f"Kalibrasyon Sonuçları: {prompt_version}", border_style="cyan"
        )
        table.add_column("Metrik", style="bold white")
        table.add_column("Skor / Değer", style="bold green", justify="right")
        table.add_column("Açıklama", style="dim")

        table.add_row(
            "Toplam İnceleme",
            str(report.total_reviews),
            "İncelenen toplam cümle sayısı",
        )
        table.add_row(
            "Toplam Anlaşmazlık",
            str(report.total_disagreements),
            "Uzman-AI uyumsuzluk sayısı",
        )

        k_frame = (
            f"{report.cohens_kappa_frame:.3f}"
            if report.cohens_kappa_frame is not None
            else "N/A"
        )
        table.add_row("Cohen's Kappa (Frame)", k_frame, "Frame uyuşma katsayısı")

        k_risk = (
            f"{report.cohens_kappa_risk:.3f}"
            if report.cohens_kappa_risk is not None
            else "N/A"
        )
        table.add_row("Cohen's Kappa (Risk)", k_risk, "Risk uyuşma katsayısı")

        f1_frame = (
            f"{report.ai_human_f1_frame:.3f}"
            if report.ai_human_f1_frame is not None
            else "N/A"
        )
        table.add_row("Macro-F1 (Frame)", f1_frame, "Frame doğruluğu")

        f1_risk = (
            f"{report.ai_human_f1_risk:.3f}"
            if report.ai_human_f1_risk is not None
            else "N/A"
        )
        table.add_row("Macro-F1 (Risk)", f1_risk, "Risk doğruluğu")

        s_mae = f"{report.sbi_mae:.3f}" if report.sbi_mae is not None else "N/A"
        table.add_row("MAE (SBI Score)", s_mae, "Ortalama Mutlak Hata")

        console.print(table)

        if report.alert_message:
            console.print(
                Panel(
                    report.alert_message,
                    title="[bold red]KALİBRASYON ALARMI[/bold red]",
                    border_style="red",
                )
            )
        else:
            console.print(
                "[bold green][OK] Kalibrasyon testi başarılı, herhangi bir alarm üretilmedi.[/bold green]"
            )

    except Exception as exc:
        console.print(f"[red][ERROR] Hata oluştu:[/red] {exc}")
        sys.exit(1)


@app.command("show-disagreements")
def show_disagreements(
    prompt_version: str = typer.Option(..., help="Prompt versiyonu"),
    limit: int = typer.Option(50, help="Listelenecek maksimum anlaşmazlık sayısı"),
) -> None:
    """Belirtilen prompt versiyonu altındaki anlaşmazlıkları gösterir."""
    asyncio.run(_run_show_disagreements(prompt_version=prompt_version, limit=limit))


async def _run_show_disagreements(prompt_version: str, limit: int) -> None:
    uow_factory = _get_uow_factory()

    async with uow_factory() as uow:
        reviews = await uow.human_reviews.get_disagreements_for_prompt(
            prompt_version=prompt_version, limit=limit
        )

    if not reviews:
        console.print(
            f"[yellow]'{prompt_version}' için anlaşmazlık kaydı bulunamadı.[/yellow]"
        )
        return

    table = Table(
        title=f"Anlaşmazlık Kayıtları (Prompt: {prompt_version})", border_style="yellow"
    )
    table.add_column("Review ID", style="cyan")
    table.add_column("Sentence ID", style="magenta")
    table.add_column("Reviewer", style="blue")
    table.add_column("AI vs Human (Frame)", style="yellow")
    table.add_column("AI vs Human (Risk)", style="yellow")
    table.add_column("Neden / Gerekçe", style="white")

    for r in reviews:
        frame_diff = (
            f"{r.ai_dominant_frame or 'N/A'} ➔ {r.human_dominant_frame or 'N/A'}"
            if r.has_frame_disagreement
            else "[dim]Uyumlu[/dim]"
        )
        risk_diff = (
            f"{r.ai_risk_level or 'N/A'} ➔ {r.human_risk_level or 'N/A'}"
            if r.has_risk_disagreement
            else "[dim]Uyumlu[/dim]"
        )
        table.add_row(
            r.id[:8],
            r.analysis_id,
            r.reviewer_id,
            frame_diff,
            risk_diff,
            r.disagreement_reason or "",
        )

    console.print(table)


if __name__ == "__main__":
    app()
