from __future__ import annotations

from datetime import datetime
from typing import Callable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.tree import Tree

from cli.theme import AGENT_STYLES, PHASE_STYLES
from orchestrator.event_bus import AgentEvent


console = Console()


class Display:
    def __init__(self):
        self._current_panel_text: list[str] = []
        self._agent_name: str = ""

    def show_banner(self, scenario_name: str = ""):
        banner = Text()
        banner.append(" Ops Fault Diagnosis ", style="bold white on blue")
        banner.append(" Multi-Agent System ", style="bold white on red")
        if scenario_name:
            banner.append(f"  Scenario: {scenario_name} ", style="bold white on green")
        console.print()
        console.print(Panel(banner, border_style="blue"))
        console.print()

    def show_phase(self, phase: str):
        style = PHASE_STYLES.get(phase, {"label": "PHASE", "emoji": ">>>", "color": "white"})
        console.print()
        console.print(Rule(
            f" {style['emoji']} {style['label']} ",
            style=style["color"],
        ))
        console.print()

    def show_agent_start(self, agent_name: str):
        style = AGENT_STYLES.get(agent_name, {"avatar": ">>", "name": agent_name, "color": "white"})
        text = Text()
        text.append(f" {style['avatar']} ", style="bold")
        text.append(f"{style['name']} Agent ", style=f"bold {style['color']}")
        text.append("thinking...", style="dim")
        console.print(text)

    def show_agent_thinking(self, agent_name: str, chunk: str):
        style = AGENT_STYLES.get(agent_name, {"color": "white"})
        console.print(chunk, end="", style=f"dim {style['color']}")

    def show_agent_step(self, agent_name: str, message: str):
        style = AGENT_STYLES.get(agent_name, {"avatar": ">", "color": "white"})
        console.print(f"  {style['avatar']} {message}", style=style["color"])

    def show_agent_result(self, agent_name: str, result):
        style = AGENT_STYLES.get(agent_name, {"avatar": "✅", "color": "white"})
        console.print()
        console.print(f"  {style['avatar']} ", style=f"bold {style['color']}", end="")

        if hasattr(result, 'reasoning_trace') and result.reasoning_trace:
            for line in result.reasoning_trace:
                console.print(f"  {line}", style=style["color"])

        console.print(
            f"  Completed in {result.duration_seconds:.1f}s "
            f"(tokens: {result.token_usage.get('input_tokens', 0)}in/{result.token_usage.get('output_tokens', 0)}out)",
            style="dim",
        )
        console.print()

    def show_summary_dashboard(self, context):
        console.print()
        console.print(Rule(" INCIDENT SUMMARY DASHBOARD ", style="bold blue"))

        # Timeline table
        table = Table(title="Key Metrics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Raw Alerts", str(len(context.raw_alerts)))
        if context.incidents:
            inc = context.incidents[0]
            table.add_row("Deduplicated Alerts", str(inc.deduplicated_count))
            table.add_row("Incidents Created", str(len(context.incidents)))
        if context.root_cause_analyses:
            rca = context.root_cause_analyses[0]
            table.add_row("Root Cause Service", rca.root_cause_service)
            table.add_row("Evidence Chain Steps", str(len(rca.evidence_chain)))
            table.add_row("Confidence", f"{rca.confidence:.0%}")
        if context.fix_plans:
            fp = context.fix_plans[0]
            table.add_row("Fix Suggestions", str(len(fp.suggestions)))
            table.add_row("Recommended Action", fp.recommended_action[:60] + "..." if len(fp.recommended_action) > 60 else fp.recommended_action)

        console.print(table)

        # Fix suggestions detail
        if context.fix_plans and context.fix_plans[0].suggestions:
            console.print()
            console.print(Rule(" TOP FIX RECOMMENDATION ", style="bold green"))
            best = context.fix_plans[0].suggestions[0]
            console.print(f"  \U0001f527 {best.title}", style="bold green")
            console.print(f"     {best.description}")
            console.print(f"     Risk: {best.risk_level} | Confidence: {best.confidence:.0%}", style="dim")
            if best.remediation_script:
                console.print(f"     Script: {best.remediation_script}", style="bold yellow")

        # Post-incident review
        if context.reviews:
            review = context.reviews[0]
            console.print()
            console.print(Rule(" POST-INCIDENT REVIEW ", style="bold yellow"))
            console.print(f"  Impact: {review.impact_assessment}")
            console.print(f"  Root Cause: {review.root_cause_summary}")
            console.print()
            if review.what_went_well:
                console.print("  What Went Well:", style="bold green")
                for item in review.what_went_well:
                    console.print(f"    ✅ {item}")
            if review.what_could_improve:
                console.print("  What Could Improve:", style="bold red")
                for item in review.what_could_improve:
                    console.print(f"    ⚠️ {item}")
            if review.action_items:
                console.print("  Action Items:", style="bold yellow")
                for ai in review.action_items:
                    console.print(f"    [{ai.get('priority', 'P2')}] {ai.get('item', '')} ({ai.get('owner', 'TBD')})")
            if review.lessons_learned:
                console.print(f"\n  Lessons Learned: {review.lessons_learned}", style="italic")

        console.print()
        console.print(Rule(style="blue"))

    def show_topology(self, context):
        tree = Tree("\U0001f310 Service Topology")
        for node in context.topology.nodes:
            deps = context.topology.get_dependencies(node.name)
            branch = tree.add(f"[cyan]{node.name}[/] (tier {node.tier})")
            for dep in deps:
                branch.add(f"[green]{dep}[/]")
        console.print(tree)
