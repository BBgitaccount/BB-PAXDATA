from typing import Any

from rich.console import Console

console = Console()


class BuildReporter:
    @staticmethod
    def print_summary(
        processed_count: int, skipped_count: int, error_count: int, container: Any
    ) -> None:
        console.print("\n[green][OK] Build completed!")
        console.print(f"Processed: {processed_count}")
        console.print(f"Skipped: {skipped_count}")
        console.print(f"Errors: {error_count}")

        if hasattr(container, "ai_analyst") and container.ai_analyst is not None:
            if hasattr(container.ai_analyst, "get_usage_summary"):
                usage = container.ai_analyst.get_usage_summary()
                console.print("\n[bold cyan]📊 AI Kullanım Raporu:[/bold cyan]")
                console.print(
                    f"  AI çağrısı yapılan cümle: {usage.get('ai_calls_made', 0)}"
                )
                console.print(
                    f"  AI limiti:               {usage.get('ai_limit', 'Sınırsız')}"
                )
                console.print(f"  Kalan hak:               {usage.get('remaining', 0)}")
                if usage.get("is_exhausted"):
                    console.print(
                        "  [yellow][WARN]  Limit doldu — sonraki cümleler logic-only ile analiz edildi.[/yellow]"
                    )
