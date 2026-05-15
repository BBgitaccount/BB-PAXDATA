# src/bb_paxdata/interfaces/cli/commands/analyze.py
"""
bbdbda analyze alt komutları.
"""
from __future__ import annotations

import asyncio
import sys

import typer
from bb_paxdata.application.use_cases.aggregate_bilateral_sentiment import (
    AggregateBilateralSentimentInput,
)
from bb_paxdata.application.use_cases.aggregate_panel_topics import (
    AggregatePanelTopicsInput,
)
from bb_paxdata.application.use_cases.build_panel_network import BuildPanelNetworkInput
from bb_paxdata.interfaces.cli.dependencies import (
    get_session,
    make_aggregate_bilateral_use_case,
    make_aggregate_topics_use_case,
    make_build_network_use_case,
)
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="analyze", help="Diplomatik söylem analiz komutları")
console = Console()


@app.command("country-refs")
def cmd_country_refs(
    panel_id: str = typer.Option(
        ..., "--panel-id", "-p", help="Analiz edilecek panel ID'si"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Bir paneldeki tüm CountryReference'lardan BilateralSentiment aggregate'lerini üretir.
    Ülke çiftleri arasındaki diplomatik söylem dinamiğini hesaplar.
    """
    asyncio.run(_run_country_refs(panel_id=panel_id, verbose=verbose))


async def _run_country_refs(panel_id: str, verbose: bool) -> None:
    console.print(
        f"[bold]Panel:[/bold] {panel_id} için bilateral sentiment hesaplanıyor..."
    )

    async with get_session() as session:
        use_case = make_aggregate_bilateral_use_case(session)
        output = await use_case.execute(
            AggregateBilateralSentimentInput(panel_id=panel_id)
        )

    if output.succeeded:
        console.print(
            f"[green]✓[/green] Tamamlandı — "
            f"Oluşturulan: {output.created_count}, "
            f"Güncellenen: {output.updated_count}, "
            f"Toplam çift: {output.total_pairs}"
        )
    else:
        console.print(f"[yellow]⚠[/yellow] Kısmi başarı — {len(output.errors)} hata:")
        for err in output.errors:
            console.print(f"  [red]•[/red] {err}", highlight=False)
        if not output.created_count and not output.updated_count:
            sys.exit(1)


@app.command("network")
def cmd_network(
    panel_id: str = typer.Option(
        ..., "--panel-id", "-p", help="Ağı oluşturulacak panel ID'si"
    ),
    weight_threshold: float = typer.Option(
        0.0, "--threshold", "-t", help="Minimum kenar ağırlığı"
    ),
    show_centrality: bool = typer.Option(
        False, "--centrality", "-c", help="Merkezi ülkeleri göster"
    ),
) -> None:
    """
    BilateralSentiment kayıtlarından DiscourseFlow (söylem ağı) kenarlarını üretir.
    Opsiyonel olarak betweenness centrality hesaplar.
    """
    asyncio.run(
        _run_network(
            panel_id=panel_id,
            weight_threshold=weight_threshold,
            show_centrality=show_centrality,
        )
    )


async def _run_network(
    panel_id: str,
    weight_threshold: float,
    show_centrality: bool,
) -> None:
    console.print(f"[bold]Panel:[/bold] {panel_id} için söylem ağı kuruluyor...")

    async with get_session() as session:
        use_case = make_build_network_use_case(session)
        output = await use_case.execute(
            BuildPanelNetworkInput(
                panel_id=panel_id,
                weight_threshold=weight_threshold,
            )
        )

    if not output.succeeded:
        console.print("[red]✗[/red] Ağ kurulamadı:")
        for err in output.errors:
            console.print(f"  {err}", highlight=False)
        sys.exit(1)

    console.print(
        f"[green]✓[/green] Ağ kuruldu — "
        f"{output.node_count} düğüm, {output.edges_created} kenar"
    )

    if show_centrality and output.centrality:
        table = Table(title="Betweenness Centrality (İlk 10)")
        table.add_column("Ülke", style="cyan")
        table.add_column("Skor", justify="right")
        sorted_c = sorted(output.centrality.items(), key=lambda x: x[1], reverse=True)
        for country, score in sorted_c[:10]:
            table.add_row(country, f"{score:.4f}")
        console.print(table)


@app.command("full")
def cmd_full(
    panel_id: str = typer.Option(
        ..., "--panel-id", "-p", help="Tam analiz yapılacak panel ID'si"
    ),
    weight_threshold: float = typer.Option(0.0, "--threshold", "-t"),
    show_centrality: bool = typer.Option(False, "--centrality", "-c"),
) -> None:
    """
    Tüm pipeline'ı sırayla çalıştırır:
    1. Bilateral sentiment aggregation
    2. Söylem ağı kurulumu
    3. Topic matrix aggregation
    """
    asyncio.run(
        _run_full(
            panel_id=panel_id,
            weight_threshold=weight_threshold,
            show_centrality=show_centrality,
        )
    )


async def _run_full(
    panel_id: str,
    weight_threshold: float,
    show_centrality: bool,
) -> None:
    console.rule(f"[bold]Full Analysis — Panel: {panel_id}[/bold]")
    has_error = False

    # Adım 1: Bilateral Sentiment
    console.print("\n[bold]Adım 1/3:[/bold] Bilateral sentiment hesaplanıyor...")
    async with get_session() as session:
        output1 = await make_aggregate_bilateral_use_case(session).execute(
            AggregateBilateralSentimentInput(panel_id=panel_id)
        )

    if output1.succeeded:
        console.print(f"  [green]✓[/green] {output1.total_pairs} çift işlendi")
    else:
        console.print(f"  [yellow]⚠[/yellow] {len(output1.errors)} hata ile tamamlandı")
        has_error = True

    # Adım 2: Network Builder
    console.print("\n[bold]Adım 2/3:[/bold] Söylem ağı kuruluyor...")
    async with get_session() as session:
        output2 = await make_build_network_use_case(session).execute(
            BuildPanelNetworkInput(panel_id=panel_id, weight_threshold=weight_threshold)
        )

    if output2.succeeded:
        console.print(
            f"  [green]✓[/green] {output2.node_count} düğüm, {output2.edges_created} kenar"
        )
        if show_centrality and output2.centrality:
            top3 = sorted(output2.centrality.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
            top3_str = ", ".join(f"{c}({s:.3f})" for c, s in top3)
            console.print(f"  [dim]Top 3 merkezi ülke:[/dim] {top3_str}")
    else:
        console.print("  [red]✗[/red] Ağ kurulamadı")
        has_error = True

    # Adım 3: Topic Aggregation
    console.print("\n[bold]Adım 3/3:[/bold] Topic matrix hesaplanıyor...")
    async with get_session() as session:
        output3 = await make_aggregate_topics_use_case(session).execute(
            AggregatePanelTopicsInput(panel_id=panel_id)
        )

    if output3.succeeded:
        console.print(
            f"  [green]✓[/green] {output3.synthesized_count} ülke için topic sentezi yapıldı"
        )
    else:
        console.print(f"  [yellow]⚠[/yellow] {len(output3.errors)} hata")
        has_error = True

    console.rule()
    if has_error:
        console.print("[yellow]Analiz kısmi başarı ile tamamlandı.[/yellow]")
        sys.exit(1)
    else:
        console.print("[green bold]Analiz başarıyla tamamlandı.[/green bold]")
