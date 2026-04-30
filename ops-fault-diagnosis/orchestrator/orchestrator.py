from __future__ import annotations

import asyncio
from typing import Callable

import anthropic

from agents.alert_aggregation import AlertAggregationAgent
from agents.root_cause import RootCauseLocalizationAgent
from agents.fix_suggestion import FixSuggestionAgent
from agents.post_incident import PostIncidentReviewAgent
from models.shared_context import SharedContext
from orchestrator.event_bus import EventBus


class Orchestrator:
    """Manages the full agent pipeline lifecycle."""

    def __init__(
        self,
        context: SharedContext,
        client: anthropic.Anthropic,
        model: str = "claude-sonnet-4-6",
        event_bus: EventBus | None = None,
        speed: str = "normal",
    ):
        self.context = context
        self.client = client
        self.model = model
        self.event_bus = event_bus or EventBus()
        self.speed = speed

        # Create agents
        self.alert_agent = AlertAggregationAgent(client, model)
        self.root_cause_agent = RootCauseLocalizationAgent(client, model)
        self.fix_agent = FixSuggestionAgent(client, model)
        self.review_agent = PostIncidentReviewAgent(client, model)

        self.results = []

    async def run(self) -> list:
        """Execute the full 4-phase pipeline."""

        # Phase 1: Alert Aggregation
        self.context.current_phase = "alert_ingestion"
        self.event_bus.emit("orchestrator", "phase_change", "alert_ingestion")
        cb1 = self.event_bus.create_callback(self.alert_agent.name)
        result1 = await self.alert_agent.run(self.context, cb1)
        self.results.append(result1)
        await self._maybe_pause("alert_ingestion")

        # Phase 2: Root Cause Localization
        self.context.current_phase = "root_cause"
        self.event_bus.emit("orchestrator", "phase_change", "root_cause")
        cb2 = self.event_bus.create_callback(self.root_cause_agent.name)
        result2 = await self.root_cause_agent.run(self.context, cb2)
        self.results.append(result2)
        await self._maybe_pause("root_cause")

        # Phase 3: Fix Suggestion
        self.context.current_phase = "fix"
        self.event_bus.emit("orchestrator", "phase_change", "fix")
        cb3 = self.event_bus.create_callback(self.fix_agent.name)
        result3 = await self.fix_agent.run(self.context, cb3)
        self.results.append(result3)
        await self._maybe_pause("fix")

        # Phase 4: Post-Incident Review
        self.context.current_phase = "review"
        self.event_bus.emit("orchestrator", "phase_change", "review")
        cb4 = self.event_bus.create_callback(self.review_agent.name)
        result4 = await self.review_agent.run(self.context, cb4)
        self.results.append(result4)

        return self.results

    async def _maybe_pause(self, phase: str):
        """Pause between phases based on speed setting."""
        if self.speed == "step":
            # Wait for user to press Enter
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\n  Press Enter to continue to next phase...")
            )
        elif self.speed == "normal":
            await asyncio.sleep(1)
        # fast = no pause
