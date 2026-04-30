from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from cli.theme import SCENARIO_INFO

console = Console()


def interactive_menu() -> dict:
    """Show interactive scenario selection menu and return choices."""
    console.print()
    console.print(Panel(
        "[bold]Ops Fault Diagnosis - Multi-Agent System[/bold]\n"
        "[dim]Powered by Claude (claude-sonnet-4-6)[/dim]",
        border_style="blue",
    ))
    console.print()
    console.print("[bold]Available Scenarios:[/bold]")
    console.print()

    for key, info in SCENARIO_INFO.items():
        console.print(f"  [cyan]{key}[/cyan]. {info['name']}")
        console.print(f"     [dim]{info['desc']}[/dim]")
        console.print()

    console.print("  [cyan]Q[/cyan]. Quit")
    console.print()

    scenario = Prompt.ask(
        "[bold]Select scenario[/bold]",
        choices=["1", "2", "3", "Q"],
        default="1",
    )

    if scenario.upper() == "Q":
        console.print("[dim]Goodbye![/dim]")
        raise SystemExit(0)

    speed = Prompt.ask(
        "[bold]Speed[/bold]",
        choices=["fast", "normal", "step"],
        default="normal",
    )

    return {"scenario": scenario, "speed": speed}
