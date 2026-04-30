from __future__ import annotations

import asyncio
import time
from typing import Callable

from agents.base_agent import BaseAgent, AgentResult
from models.shared_context import SharedContext
from models.incidents import Incident, CorrelationGroup, IncidentStatus
from models.alerts import AlertSeverity


class AlertAggregationAgent(BaseAgent):
    name = "alert-aggregation"
    display_name = "Alert Aggregation Agent"
    avatar = "\U0001f50d"
    color = "cyan"

    async def run(
        self, context: SharedContext, event_callback: Callable | None = None
    ) -> AgentResult:
        start = time.time()
        self._reset_conversation()
        reasoning_trace: list[str] = []

        def emit(event_type: str, data: str):
            if event_callback:
                event_callback(self.name, event_type, data)

        # Prepare alert summary for Claude
        alerts_text = self._format_alerts(context.raw_alerts)
        topology_text = context.topology.to_text()

        emit("step", f"Received {len(context.raw_alerts)} raw alerts spanning "
             f"{len(set(a.service_name for a in context.raw_alerts))} services")

        prompt = f"""Analyze the following raw alerts and correlate them into minimal meaningful incidents.

## Service Topology
{topology_text}

## Raw Alerts ({len(context.raw_alerts)} total)
{alerts_text}

De-duplicate and correlate these alerts based on the topology. Group cascading failures as a single incident. Return the incidents as a JSON array."""

        result, usage = self._call_claude_json(prompt, event_callback)

        # Parse into Incident objects
        incidents = self._parse_incidents(result, context)
        context.incidents = incidents

        reasoning_trace.append(f"Processed {len(context.raw_alerts)} raw alerts")
        reasoning_trace.append(f"Identified {len(incidents)} incident(s)")
        for inc in incidents:
            reasoning_trace.append(
                f"  [{inc.id}] {inc.title} - {inc.raw_alert_count} alerts -> {inc.deduplicated_count} unique"
            )

        duration = time.time() - start
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=incidents,
            reasoning_trace=reasoning_trace,
            duration_seconds=duration,
            token_usage=usage,
        )

    def _format_alerts(self, alerts) -> str:
        lines = []
        for a in alerts:
            lines.append(
                f"[{a.timestamp.strftime('%H:%M:%S')}] {a.service_name}/{a.alert_name} "
                f"({a.severity.value}): {a.message}"
            )
        return "\n".join(lines)

    def _parse_incidents(self, result, context: SharedContext) -> list[Incident]:
        incidents = []
        items = result if isinstance(result, list) else [result]

        for item in items:
            impacted = item.get("impacted_services", [])
            alert_groups = []
            for ag in item.get("alert_groups", []):
                alert_groups.append(CorrelationGroup(
                    common_service=ag.get("common_service", ""),
                    alert_ids=[],
                    correlation_reason=ag.get("correlation_reason", ""),
                    estimated_severity=AlertSeverity(
                        ag.get("severity", "high")
                    ),
                ))

            # Count raw and deduplicated alerts for this incident
            raw_count = sum(
                1 for a in context.raw_alerts
                if a.service_name in impacted
            )
            dedup_count = len(set(
                (a.service_name, a.alert_name) for a in context.raw_alerts
                if a.service_name in impacted
            ))

            incident = Incident(
                title=item.get("title", "Untitled Incident"),
                status=IncidentStatus.CREATED,
                impacted_services=impacted,
                summary=item.get("summary", ""),
                raw_alert_count=raw_count,
                deduplicated_count=dedup_count,
                alert_groups=alert_groups,
            )
            incidents.append(incident)

        return incidents
