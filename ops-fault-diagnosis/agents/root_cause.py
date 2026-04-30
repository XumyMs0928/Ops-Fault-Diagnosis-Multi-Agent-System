from __future__ import annotations

import asyncio
import time
from typing import Callable

from agents.base_agent import BaseAgent, AgentResult
from models.shared_context import SharedContext
from models.diagnosis import RootCauseAnalysis, EvidenceStep


class RootCauseLocalizationAgent(BaseAgent):
    """Long-chain reasoning agent that traces the call chain step by step."""

    name = "root-cause"
    display_name = "Root Cause Localization Agent"
    avatar = "\U0001f3af"
    color = "red"

    async def run(
        self, context: SharedContext, event_callback: Callable | None = None
    ) -> AgentResult:
        start = time.time()
        self._reset_conversation()
        reasoning_trace: list[str] = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        def emit(event_type: str, data):
            if event_callback:
                event_callback(self.name, event_type, data)

        if not context.incidents:
            return AgentResult(
                agent_name=self.name,
                success=False,
                reasoning_trace=["No incidents to analyze"],
                duration_seconds=time.time() - start,
            )

        incident = context.incidents[0]
        event_msg = f"Analyzing incident: {incident.title} (services: {', '.join(incident.impacted_services)})"
        emit("step", event_msg)
        reasoning_trace.append(event_msg)

        # === Step 1: Trace the call chain from surface symptoms ===
        emit("step", "Step 1: Tracing service call chain from surface symptom...")
        step1_prompt = self._build_step1_prompt(context, incident)
        step1_result, step1_usage = self._call_claude_json(step1_prompt, event_callback)
        total_usage["input_tokens"] += step1_usage.get("input_tokens", 0)
        total_usage["output_tokens"] += step1_usage.get("output_tokens", 0)

        suspected_root = step1_result.get("suspected_root_service", "")
        reasoning_trace.append(
            f"Step 1: Call chain traced -> suspected root: {suspected_root}"
        )

        # === Step 2: Deep dive on suspected root service ===
        emit("step", f"Step 2: Deep diving on {suspected_root} - examining logs and metrics...")
        step2_prompt = self._build_step2_prompt(context, suspected_root)
        step2_result, step2_usage = self._call_claude_json(step2_prompt, event_callback)
        total_usage["input_tokens"] += step2_usage.get("input_tokens", 0)
        total_usage["output_tokens"] += step2_usage.get("output_tokens", 0)

        reasoning_trace.append(
            f"Step 2: Examined {suspected_root} logs/metrics -> {step2_result.get('diagnosis', 'ongoing')}"
        )

        # === Step 3: Cross-reference recent changes ===
        affected_services = incident.impacted_services
        emit("step", "Step 3: Cross-referencing recent deployments and config changes...")
        step3_prompt = self._build_step3_prompt(context, affected_services)
        step3_result, step3_usage = self._call_claude_json(step3_prompt, event_callback)
        total_usage["input_tokens"] += step3_usage.get("input_tokens", 0)
        total_usage["output_tokens"] += step3_usage.get("output_tokens", 0)

        change_correlation = step3_result.get("change_correlation", "")
        reasoning_trace.append(
            f"Step 3: Recent changes analyzed -> {change_correlation}"
        )

        # === Step 4: Synthesize the full root cause analysis ===
        emit("step", "Step 4: Synthesizing complete root cause analysis with evidence chain...")
        step4_prompt = self._build_step4_prompt(
            step1_result, step2_result, step3_result, incident
        )
        rca_result, step4_usage = self._call_claude_json(step4_prompt, event_callback)
        total_usage["input_tokens"] += step4_usage.get("input_tokens", 0)
        total_usage["output_tokens"] += step4_usage.get("output_tokens", 0)

        # Build the RootCauseAnalysis object
        rca = self._parse_rca(rca_result, incident.id)
        context.root_cause_analyses = [rca]

        reasoning_trace.append(
            f"Step 4: Root cause identified -> {rca.root_cause_service}: "
            f"{rca.root_cause_description[:100]}..."
        )
        reasoning_trace.append(f"Confidence: {rca.confidence:.0%}")
        reasoning_trace.append(f"Evidence chain: {len(rca.evidence_chain)} steps")

        duration = time.time() - start
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=rca,
            reasoning_trace=reasoning_trace,
            duration_seconds=duration,
            token_usage=total_usage,
        )

    def _build_step1_prompt(self, context: SharedContext, incident) -> str:
        topology_text = context.topology.to_text()
        anomalies_text = self._format_anomalies(context.metric_anomalies)
        incident_summary = (
            f"Incident: {incident.title}\n"
            f"Impacted services: {', '.join(incident.impacted_services)}\n"
            f"Summary: {incident.summary}"
        )

        return f"""Given this incident, trace the service call chain from surface symptoms to identify the likely root cause service.

## Service Topology
{topology_text}

## Incident
{incident_summary}

## Metric Anomalies
{anomalies_text}

Start from the surface-level services (lowest tier) showing errors, and trace downstream through the call chain. Which service, at the deepest point of the chain, is most likely the root cause?

Return JSON:
{{
  "call_chain_trace": "Description of the traced path",
  "suspected_root_service": "service-name",
  "reasoning": "Why this service is the likely root cause"
}}"""

    def _build_step2_prompt(self, context: SharedContext, service_name: str) -> str:
        logs = context.get_logs_for_service(service_name)
        logs_text = self._format_logs(logs[-30:] if len(logs) > 30 else logs)  # Last 30 entries
        anomalies = context.get_anomalies_for_service(service_name)
        anomalies_text = self._format_anomalies(anomalies)
        metrics = context.get_metrics_for_service(service_name)
        # Get latest metric values
        latest_metrics: dict[str, float] = {}
        for m in metrics:
            key = m.metric_type.value
            latest_metrics[key] = m.value

        return f"""Examine the logs and metrics for service "{service_name}" to identify the specific issue.

## Recent Logs for {service_name}
{logs_text}

## Metric Anomalies for {service_name}
{anomalies_text}

## Latest Metric Values for {service_name}
{self._format_metric_values(latest_metrics)}

What specific failure is occurring in this service? Look for connection failures, timeouts, resource exhaustion, errors, or other anomalies in the logs.

Return JSON:
{{
  "diagnosis": "Specific diagnosis of the issue",
  "evidence": ["List of specific evidence from logs/metrics"],
  "severity": "critical|high|medium"
}}"""

    def _build_step3_prompt(self, context: SharedContext, services: list[str]) -> str:
        changes_text = self._format_changes(context.change_records)
        return f"""Check if recent deployments, config changes, or scaling events correlate with the incident.

## Affected Services
{', '.join(services)}

## Recent Changes (all services)
{changes_text}

Which changes are most likely related to the current incident? Consider timing and service proximity.

Return JSON:
{{
  "change_correlation": "Description of which changes correlate and why",
  "related_changes": ["List of specific change descriptions that likely triggered the issue"],
  "trigger_likelihood": "high|medium|low"
}}"""

    def _build_step4_prompt(self, step1, step2, step3, incident) -> str:
        return f"""Now synthesize the complete root cause analysis based on all investigation steps.

## Step 1 - Call Chain Trace
{step1.get('call_chain_trace', 'N/A')}
Suspected root: {step1.get('suspected_root_service', 'N/A')}
Reasoning: {step1.get('reasoning', 'N/A')}

## Step 2 - Deep Dive Diagnosis
{step2.get('diagnosis', 'N/A')}
Evidence: {step2.get('evidence', [])}
Severity: {step2.get('severity', 'N/A')}

## Step 3 - Change Correlation
{step3.get('change_correlation', 'N/A')}
Related changes: {step3.get('related_changes', [])}
Trigger likelihood: {step3.get('trigger_likelihood', 'N/A')}

## Incident
{incident.title} - {incident.summary}

Produce the final root cause analysis with a complete evidence chain.

Return JSON:
{{
  "root_cause_service": "service-name",
  "root_cause_description": "Clear, detailed description of the root cause",
  "confidence": 0.92,
  "evidence_chain": [
    {{"step_number": 1, "action": "What was investigated", "observation": "What was found", "finding": "What it implies"}},
    {{"step_number": 2, "action": "...", "observation": "...", "finding": "..."}},
    {{"step_number": 3, "action": "...", "observation": "...", "finding": "..."}},
    {{"step_number": 4, "action": "...", "observation": "...", "finding": "..."}}
  ],
  "contributing_factors": ["Factor 1", "Factor 2"],
  "timeline": [
    {{"time": "HH:MM:SS", "event": "Description"}}
  ]
}}"""

    def _parse_rca(self, result: dict, incident_id: str) -> RootCauseAnalysis:
        evidence_chain = []
        for step in result.get("evidence_chain", []):
            evidence_chain.append(EvidenceStep(
                step_number=step.get("step_number", 0),
                action=step.get("action", ""),
                observation=step.get("observation", ""),
                finding=step.get("finding", ""),
            ))

        return RootCauseAnalysis(
            incident_id=incident_id,
            root_cause_service=result.get("root_cause_service", "unknown"),
            root_cause_description=result.get("root_cause_description", ""),
            evidence_chain=evidence_chain,
            contributing_factors=result.get("contributing_factors", []),
            confidence=result.get("confidence", 0.5),
            timeline=result.get("timeline", []),
        )

    def _format_logs(self, logs) -> str:
        lines = []
        for l in logs:
            exc = f" [{l.exception_class}]" if l.exception_class else ""
            lines.append(
                f"[{l.timestamp.strftime('%H:%M:%S')}] {l.service_name} {l.level.value}: "
                f"{l.message}{exc}"
            )
        return "\n".join(lines)

    def _format_anomalies(self, anomalies) -> str:
        if not anomalies:
            return "No anomalies detected."
        lines = []
        for a in anomalies:
            lines.append(
                f"  {a.service_name}/{a.metric_type.value}: observed={a.observed_value}, "
                f"baseline={a.baseline_value} (+{a.deviation_percent:.1f}%)"
            )
        return "\n".join(lines)

    def _format_changes(self, changes) -> str:
        lines = []
        for c in changes:
            lines.append(
                f"[{c.timestamp.strftime('%Y-%m-%d %H:%M')}] {c.change_type.value} "
                f"on {c.service_name}: {c.description} (by {c.author})"
            )
        return "\n".join(lines)

    def _format_metric_values(self, metrics: dict[str, float]) -> str:
        if not metrics:
            return "No metric data available."
        return "\n".join(f"  {k}: {v}" for k, v in metrics.items())
