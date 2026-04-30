from __future__ import annotations

import time
from typing import Callable

from agents.base_agent import BaseAgent, AgentResult
from models.shared_context import SharedContext
from models.diagnosis import PostIncidentReview


class PostIncidentReviewAgent(BaseAgent):
    name = "post-incident"
    display_name = "Post-Incident Review Agent"
    avatar = "\U0001f4cb"
    color = "yellow"

    async def run(
        self, context: SharedContext, event_callback: Callable | None = None
    ) -> AgentResult:
        start = time.time()
        self._reset_conversation()
        reasoning_trace: list[str] = []

        def emit(event_type: str, data):
            if event_callback:
                event_callback(self.name, event_type, data)

        if not context.incidents:
            return AgentResult(
                agent_name=self.name,
                success=False,
                reasoning_trace=["No incident to review"],
                duration_seconds=time.time() - start,
            )

        emit("step", "Generating post-incident review report...")

        prompt = f"""Generate a comprehensive post-incident review based on the following data.

## Incident Summary
{context.to_context_summary()}

## Fix Plan
{self._format_fix_plans(context.fix_plans)}

Generate the post-incident review as JSON."""

        result, usage = self._call_claude_json(prompt, event_callback)

        # Parse into PostIncidentReview
        review = self._parse_review(result, context.incidents[0].id)
        context.reviews = [review]

        reasoning_trace.append("Post-incident review generated")
        reasoning_trace.append(f"  Action items: {len(review.action_items)}")
        reasoning_trace.append(f"  What went well: {len(review.what_went_well)}")
        reasoning_trace.append(f"  What could improve: {len(review.what_could_improve)}")

        duration = time.time() - start
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=review,
            reasoning_trace=reasoning_trace,
            duration_seconds=duration,
            token_usage=usage,
        )

    def _format_fix_plans(self, fix_plans) -> str:
        lines = []
        for fp in fix_plans:
            lines.append(f"Recommended: {fp.recommended_action}")
            for s in fp.suggestions:
                lines.append(
                    f"  - [{s.risk_level} risk] {s.title}: {s.description}"
                )
                if s.remediation_script:
                    lines.append(f"    Script: {s.remediation_script}")
        return "\n".join(lines) if lines else "No fix plan available."

    def _parse_review(self, result: dict, incident_id: str) -> PostIncidentReview:
        return PostIncidentReview(
            incident_id=incident_id,
            timeline_summary=result.get("timeline_summary", ""),
            impact_assessment=result.get("impact_assessment", ""),
            root_cause_summary=result.get("root_cause_summary", ""),
            what_went_well=result.get("what_went_well", []),
            what_could_improve=result.get("what_could_improve", []),
            action_items=result.get("action_items", []),
            lessons_learned=result.get("lessons_learned", ""),
        )
