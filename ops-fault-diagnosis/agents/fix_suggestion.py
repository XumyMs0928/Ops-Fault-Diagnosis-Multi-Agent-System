from __future__ import annotations

import time
from typing import Callable

from agents.base_agent import BaseAgent, AgentResult
from models.shared_context import SharedContext
from models.diagnosis import FixPlan, FixSuggestion


class FixSuggestionAgent(BaseAgent):
    name = "fix-suggestion"
    display_name = "Fix Suggestion Agent"
    avatar = "\U0001f527"
    color = "green"

    async def run(
        self, context: SharedContext, event_callback: Callable | None = None
    ) -> AgentResult:
        start = time.time()
        self._reset_conversation()
        reasoning_trace: list[str] = []

        def emit(event_type: str, data):
            if event_callback:
                event_callback(self.name, event_type, data)

        if not context.root_cause_analyses:
            return AgentResult(
                agent_name=self.name,
                success=False,
                reasoning_trace=["No root cause analysis available"],
                duration_seconds=time.time() - start,
            )

        rca = context.root_cause_analyses[0]
        incident_id = context.incidents[0].id if context.incidents else ""

        emit("step", f"Generating fix suggestions for root cause: {rca.root_cause_service}")

        prompt = f"""Based on the following root cause analysis, generate actionable fix suggestions.

## Root Cause Analysis
- **Root Cause Service**: {rca.root_cause_service}
- **Description**: {rca.root_cause_description}
- **Confidence**: {rca.confidence:.0%}
- **Contributing Factors**: {', '.join(rca.contributing_factors)}

## Evidence Chain
{self._format_evidence_chain(rca.evidence_chain)}

## Recent Changes
{self._format_changes(context.change_records)}

Generate 2-4 fix suggestions including an immediate remediation and long-term prevention. Return the suggestions as JSON."""

        result, usage = self._call_claude_json(prompt, event_callback)

        # Parse into FixPlan
        fix_plan = self._parse_fix_plan(result, incident_id, rca.root_cause_service)
        context.fix_plans = [fix_plan]

        reasoning_trace.append(f"Generated {len(fix_plan.suggestions)} fix suggestions")
        for s in fix_plan.suggestions:
            reasoning_trace.append(
                f"  [{s.risk_level} risk] {s.title} (confidence: {s.confidence:.0%})"
            )
        reasoning_trace.append(f"Recommended: {fix_plan.recommended_action}")

        duration = time.time() - start
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=fix_plan,
            reasoning_trace=reasoning_trace,
            duration_seconds=duration,
            token_usage=usage,
        )

    def _format_evidence_chain(self, chain) -> str:
        lines = []
        for step in chain:
            lines.append(
                f"Step {step.step_number}: {step.action}\n"
                f"  Observation: {step.observation}\n"
                f"  Finding: {step.finding}"
            )
        return "\n".join(lines)

    def _format_changes(self, changes) -> str:
        lines = []
        for c in changes:
            lines.append(
                f"[{c.timestamp.strftime('%Y-%m-%d %H:%M')}] {c.change_type.value} "
                f"on {c.service_name}: {c.description}"
            )
        return "\n".join(lines)

    def _parse_fix_plan(self, result: dict, incident_id: str, root_cause: str) -> FixPlan:
        suggestions = []
        for s in result.get("suggestions", []):
            suggestions.append(FixSuggestion(
                title=s.get("title", ""),
                description=s.get("description", ""),
                remediation_script=s.get("remediation_script"),
                confidence=s.get("confidence", 0.5),
                risk_level=s.get("risk_level", "medium"),
                estimated_impact=s.get("estimated_impact", ""),
                prerequisites=s.get("prerequisites", []),
            ))

        return FixPlan(
            incident_id=incident_id,
            root_cause_id=root_cause,
            suggestions=suggestions,
            recommended_action=result.get("recommended_action", ""),
        )
