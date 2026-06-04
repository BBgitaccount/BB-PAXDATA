import typer
import uvicorn

app = typer.Typer(help="FastAPI Sunucusu Yönetim Komutları")


@app.command("run")
def run_server(
    host: str = typer.Option("127.0.0.1", help="Sunucu Host Adresi"),
    port: int = typer.Option(8000, help="Sunucu Port Numarası"),
    reload: bool = typer.Option(
        True, help="Hot-reload modunu aktif et (geliştirme için)"
    ),
):
    """FastAPI Sunucusunu Uvicorn üzerinden başlatır."""
    typer.echo(f"🚀 Sunucu başlatılıyor: http://{host}:{port}")
    uvicorn.run(
        "bb_paxdata.interfaces.api.main:app", host=host, port=port, reload=reload
    )
