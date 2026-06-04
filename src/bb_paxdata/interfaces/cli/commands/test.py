"""
Testing and Evaluation CLI commands.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(help="Test ve Değerlendirme komutları (Parçalı test, AI testi vb.)")
console = Console()


@app.command("run")
def run_tests(
    type: str = typer.Option(
        "logic", "--type", "-t", help="Çalıştırılacak test tipi (logic, ai, e2e, all)"
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="AI testlerinde analiz edilecek maksimum cümle sayısı (Maliyet kontrolü için)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Detaylı log göster"),
) -> None:
    """
    Belirli bir kapsamdaki testleri çalıştırır.

    --type logic : AI servislerini çağırmadan mantıksal testleri çalıştırır.
    --type ai    : Sadece AI/LLM servislerini test eder.
    --type e2e   : Uçtan uca tüm sistemi test eder.
    """
    console.rule(
        f"[bold blue]Test Çalıştırma Başlıyor: Mod = {type.upper()}[/bold blue]"
    )

    pytest_args = ["tests/"]

    if verbose:
        pytest_args.append("-v")

    if type == "logic":
        pytest_args.extend(["-m", "not ai and not e2e"])
        console.print(
            "[yellow][INFO][/yellow] Sadece logic (mantık) ve NLP testleri çalıştırılıyor. AI çağrıları yapılmayacak."
        )
    elif type == "ai":
        pytest_args.extend(["-m", "ai"])
        console.print(
            "[yellow][INFO][/yellow] Sadece AI (LLM) değerlendirme testleri çalıştırılıyor."
        )
        if limit:
            # We can pass limit via env var to be caught by tests/conftest.py or test code
            os.environ["AI_TEST_LIMIT"] = str(limit)
            console.print(
                f"[yellow][INFO][/yellow] Test limiti {limit} cümle ile sınırlandırıldı."
            )
    elif type == "e2e":
        pytest_args.extend(["-m", "e2e"])
        console.print("[yellow][INFO][/yellow] Uçtan uca (E2E) testler çalıştırılıyor.")
    elif type == "all":
        console.print("[yellow][INFO][/yellow] Tüm test süiti çalıştırılıyor.")
    else:
        console.print(
            f"[red]Geçersiz test tipi: {type}. (Geçerli tipler: logic, ai, e2e, all)[/red]"
        )
        sys.exit(1)

    exit_code = pytest.main(pytest_args)

    if exit_code == 0:
        console.print("[green bold][OK] Tüm testler başarıyla geçti![/green bold]")
    else:
        console.print(
            f"[red bold][ERROR] Testler başarısız oldu. (Çıkış kodu: {exit_code})[/red bold]"
        )
        sys.exit(exit_code)


@app.command("eval-sentence")
def eval_sentence(
    text: str = typer.Argument(..., help="Analiz edilecek cümle"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Detaylı NLP ara adımlarını göster"
    ),
    logic_only: bool = typer.Option(
        False,
        "--logic-only",
        "-L",
        help="LLM/AI çağrısı yapmadan kural tabanlı analiz yap (AI-free mod)",
    ),
    variant: str = typer.Option(
        "default",
        "--variant",
        "-V",
        help="Çalıştırılacak pipeline varyantı (default, fast_mode, no_ai_mode vb.)",
    ),
) -> None:
    """
    Tek bir cümleyi AnalysisPipeline üzerinden uçtan uca analiz eder.
    Hata ayıklama ve AI davranışını anlık incelemek için kullanılır.
    """
    asyncio.run(_run_eval_sentence(text, verbose, logic_only, variant))


async def _run_eval_sentence(
    text: str, verbose: bool, logic_only: bool = False, variant: str = "default"
) -> None:
    from bb_paxdata.infrastructure.container.service_container import ServiceContainer

    console.print(f"[cyan]Analiz Ediliyor:[/cyan] '{text}'")
    if logic_only:
        console.print(
            "[bold yellow]⚡ LOGIC-ONLY mod — LLM çağrısı yapılmayacak.[/bold yellow]"
        )
    console.print(f"[cyan]Kullanılan Pipeline Varyantı:[/cyan] '{variant}'")

    try:
        ServiceContainer.reset_instance()
        container = ServiceContainer(logic_mode=logic_only)
        pipeline = container.pipeline

        # Analizi çalıştır
        result = await pipeline.run(text, metadata={"pipeline_variant": variant})

        if result.analysis:
            console.print(Panel("[green]Analiz Başarılı[/green]"))

            table = Table(
                title="AI Analiz Sonuçları",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Metrik", style="cyan")
            table.add_column("Değer", style="white")

            table.add_row("Duygu Skoru", str(result.analysis.ai_sentiment_score))
            table.add_row("Risk Skoru", str(result.analysis.ai_risk_score))
            table.add_row(
                "Diplomatik Ton",
                str(getattr(result.analysis, "ai_diplomatic_tone", "N/A")),
            )
            table.add_row(
                "Ana Konu", str(getattr(result.analysis, "ai_primary_topic", "N/A"))
            )
            table.add_row("Anomali Skoru", str(result.analysis.anomaly_score))

            console.print(table)

            if verbose and result.analysis.tokens:
                console.print("\n[bold yellow]NLP Çıkarımları:[/bold yellow]")
                console.print(f"Token Sayısı: {len(result.analysis.tokens)}")
                console.print(f"Varlıklar (Entities): {result.analysis.entities}")

        else:
            console.print("[red]Analiz sonucu alınamadı![/red]")
            if result.errors:
                for err in result.errors:
                    console.print(f"- {err}")

    except Exception as e:
        console.print(f"[red bold]Hata oluştu: {e}[/red bold]")
        sys.exit(1)


@app.command("eval-dataset")
def eval_dataset(
    limit: int = typer.Option(
        None, "--limit", "-l", help="Değerlendirilecek maksimum cümle sayısı"
    )
) -> None:
    """
    Golden Dataset üzerinden tüm kalite değerlendirme (DeepEval) pipeline'ını çalıştırır.
    """
    console.print("[bold blue]Golden Dataset Değerlendirmesi Başlıyor...[/bold blue]")

    if limit:
        console.print(f"[yellow]Limit: {limit} cümle ile sınırlandırıldı.[/yellow]")
        os.environ["AI_TEST_LIMIT"] = str(limit)

    # Arka planda pytest marker üzerinden çalıştırabiliriz
    exit_code = pytest.main(["tests/quality/", "-v"])
    sys.exit(exit_code)
