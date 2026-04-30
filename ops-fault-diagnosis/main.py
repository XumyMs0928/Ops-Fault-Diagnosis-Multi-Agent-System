#!/usr/bin/env python3
"""Ops Fault Diagnosis Multi-Agent System - Entry Point"""

from __future__ import annotations

import asyncio
import os
import sys

import click
from dotenv import load_dotenv
from rich.console import Console

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic

from simulation.topology_builder import build_topology
from simulation.alert_generator import AlertGenerator
from simulation.log_generator import LogGenerator
from simulation.metrics_generator import MetricsGenerator
from simulation.change_generator import ChangeGenerator
from simulation.scenarios.connection_pool_exhaustion import ConnectionPoolExhaustionScenario
from simulation.scenarios.memory_leak_oom import MemoryLeakOOMScenario
from simulation.scenarios.disk_full_cascade import DiskFullCascadeScenario
from models.shared_context import SharedContext
from orchestrator.orchestrator import Orchestrator
from orchestrator.event_bus import EventBus, AgentEvent
from cli.display import Display
from cli.interactive import interactive_menu
from cli.theme import AGENT_STYLES, PHASE_STYLES

console = Console()

SCENARIOS = {
    "1": ConnectionPoolExhaustionScenario(),
    "2": MemoryLeakOOMScenario(),
    "3": DiskFullCascadeScenario(),
}


def load_scenario(scenario_key: str) -> SharedContext:
    """Load a scenario and populate the SharedContext with simulated data."""
    scenario = SCENARIOS[scenario_key]
    topology = build_topology()

    # Generate all simulated data
    alert_batch = AlertGenerator(topology, scenario).generate_alert_storm()
    log_entries = LogGenerator(topology, scenario).generate_logs()
    metric_points = MetricsGenerator(topology, scenario).generate_metrics()
    metric_anomalies = MetricsGenerator(topology, scenario).detect_anomalies()
    change_records = ChangeGenerator(topology, scenario).generate_changes()

    context = SharedContext(
        topology=topology,
        raw_alerts=alert_batch.alerts,
        log_entries=log_entries,
        metric_series=metric_points,
        metric_anomalies=metric_anomalies,
        change_records=change_records,
    )

    return context


def create_event_handler(display: Display, speed: str):
    """Create an event handler that routes EventBus events to the Display."""
    current_agent = None

    def handler(event: AgentEvent):
        nonlocal current_agent

        if event.event_type == "phase_change":
            display.show_phase(event.data)
            current_agent = None
            return

        if event.event_type == "step":
            if current_agent != event.agent_name:
                current_agent = event.agent_name
                display.show_agent_start(event.agent_name)
            display.show_agent_step(event.agent_name, event.data)
            return

        if event.event_type == "thinking_chunk":
            if current_agent != event.agent_name:
                current_agent = event.agent_name
                display.show_agent_start(event.agent_name)
            display.show_agent_thinking(event.agent_name, event.data)
            return

    return handler


async def run_pipeline(scenario_key: str, speed: str, api_key: str, model: str):
    """Main pipeline execution."""
    display = Display()

    # Load scenario
    scenario = SCENARIOS[scenario_key]
    display.show_banner(scenario.name())

    # Initialize context with simulated data
    console.print(f"[dim]Loading scenario: {scenario.name()}...[/dim]")
    context = load_scenario(scenario_key)
    console.print(f"[dim]Generated {len(context.raw_alerts)} alerts, "
                  f"{len(context.log_entries)} log entries, "
                  f"{len(context.metric_series)} metric points, "
                  f"{len(context.change_records)} changes[/dim]")
    console.print()

    # Show topology
    display.show_topology(context)
    console.print()

    # Create Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Set up event bus and display handler
    event_bus = EventBus()
    event_bus.subscribe(create_event_handler(display, speed))

    # Create and run orchestrator
    orchestrator = Orchestrator(
        context=context,
        client=client,
        model=model,
        event_bus=event_bus,
        speed=speed,
    )

    results = await orchestrator.run()

    # Show summary dashboard
    display.show_summary_dashboard(context)

    # Print token usage summary
    total_input = sum(r.token_usage.get("input_tokens", 0) for r in results)
    total_output = sum(r.token_usage.get("output_tokens", 0) for r in results)
    total_duration = sum(r.duration_seconds for r in results)
    console.print(f"[dim]Total: {total_input} input tokens, {total_output} output tokens, "
                  f"{total_duration:.1f}s elapsed[/dim]")


@click.command()
@click.option("--scenario", "-s", type=click.Choice(["1", "2", "3"]),
              help="Scenario number (1=DB conn pool, 2=OOM, 3=Disk full)")
@click.option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key")
@click.option("--model", default="claude-sonnet-4-6", help="Model name")
@click.option("--speed", type=click.Choice(["fast", "normal", "step"]),
              default="normal", help="Execution speed")
def main(scenario, api_key, model, speed):
    """Ops Fault Diagnosis Multi-Agent System"""
    load_dotenv()

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set. "
                      "Set it via --api-key, env var, or .env file[/red]")
        sys.exit(1)

    # Interactive mode if no scenario selected
    if not scenario:
        choices = interactive_menu()
        scenario = choices["scenario"]
        speed = choices.get("speed", speed)

    asyncio.run(run_pipeline(scenario, speed, api_key, model))


if __name__ == "__main__":
    main()
