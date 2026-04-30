from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field

from models.alerts import Alert
from models.incidents import Incident
from models.topology import ServiceTopology
from models.logs import LogEntry
from models.metrics import MetricDataPoint, MetricAnomaly
from models.changes import ChangeRecord
from models.diagnosis import RootCauseAnalysis, FixPlan, PostIncidentReview


class SharedContext(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    topology: ServiceTopology
    raw_alerts: list[Alert] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)
    log_entries: list[LogEntry] = Field(default_factory=list)
    metric_series: list[MetricDataPoint] = Field(default_factory=list)
    metric_anomalies: list[MetricAnomaly] = Field(default_factory=list)
    change_records: list[ChangeRecord] = Field(default_factory=list)
    root_cause_analyses: list[RootCauseAnalysis] = Field(default_factory=list)
    fix_plans: list[FixPlan] = Field(default_factory=list)
    reviews: list[PostIncidentReview] = Field(default_factory=list)
    current_phase: str = "alert_ingestion"
    agent_outputs: dict[str, Any] = Field(default_factory=dict)

    def get_logs_for_service(
        self, service_name: str, level: str | None = None
    ) -> list[LogEntry]:
        results = [l for l in self.log_entries if l.service_name == service_name]
        if level:
            results = [l for l in results if l.level.value == level]
        return results

    def get_metrics_for_service(
        self, service_name: str
    ) -> list[MetricDataPoint]:
        return [m for m in self.metric_series if m.service_name == service_name]

    def get_anomalies_for_service(
        self, service_name: str
    ) -> list[MetricAnomaly]:
        return [a for a in self.metric_anomalies if a.service_name == service_name]

    def get_recent_changes(
        self, service_name: str, hours: int = 72
    ) -> list[ChangeRecord]:
        now = datetime.now()
        cutoff = now - __import__("datetime").timedelta(hours=hours)
        return [
            c for c in self.change_records
            if c.service_name == service_name and c.timestamp >= cutoff
        ]

    def get_call_chain_to(self, service_name: str) -> list[str]:
        """Find the call chain from the highest-tier service down to the target."""
        for node in sorted(self.topology.nodes, key=lambda n: n.tier):
            chain = self.topology.get_call_chain(node.name, service_name)
            if chain:
                return chain
        return [service_name]

    def to_context_summary(self) -> str:
        """Serialize to a concise string for Claude prompt injection."""
        lines = []
        lines.append(f"=== Session: {self.session_id} ===")
        lines.append(f"Phase: {self.current_phase}")
        lines.append(f"\nTopology:\n{self.topology.to_text()}")

        if self.raw_alerts:
            lines.append(f"\nRaw Alerts: {len(self.raw_alerts)} alerts")
            for svc in sorted(set(a.service_name for a in self.raw_alerts)):
                svc_alerts = [a for a in self.raw_alerts if a.service_name == svc]
                lines.append(f"  {svc}: {len(svc_alerts)} alerts")

        if self.incidents:
            lines.append(f"\nIncidents: {len(self.incidents)}")
            for inc in self.incidents:
                lines.append(f"  [{inc.id}] {inc.title}")
                lines.append(f"    Services: {', '.join(inc.impacted_services)}")
                lines.append(f"    Raw alerts: {inc.raw_alert_count} -> Deduplicated: {inc.deduplicated_count}")
                lines.append(f"    Summary: {inc.summary}")

        if self.metric_anomalies:
            lines.append(f"\nMetric Anomalies: {len(self.metric_anomalies)}")
            for a in self.metric_anomalies:
                lines.append(
                    f"  {a.service_name}/{a.metric_type.value}: "
                    f"observed={a.observed_value}, baseline={a.baseline_value} "
                    f"(+{a.deviation_percent:.1f}%)"
                )

        if self.change_records:
            lines.append(f"\nRecent Changes: {len(self.change_records)}")
            for c in self.change_records:
                lines.append(
                    f"  [{c.change_type.value}] {c.service_name}: {c.description} "
                    f"(by {c.author})"
                )

        if self.root_cause_analyses:
            lines.append(f"\nRoot Cause Analyses: {len(self.root_cause_analyses)}")
            for rca in self.root_cause_analyses:
                lines.append(f"  Root: {rca.root_cause_service}")
                lines.append(f"  Cause: {rca.root_cause_description}")
                lines.append(f"  Confidence: {rca.confidence:.0%}")
                for step in rca.evidence_chain:
                    lines.append(f"    Step {step.step_number}: {step.action}")
                    lines.append(f"      Observation: {step.observation}")
                    lines.append(f"      Finding: {step.finding}")

        if self.fix_plans:
            lines.append(f"\nFix Plans: {len(self.fix_plans)}")
            for fp in self.fix_plans:
                lines.append(f"  Recommended: {fp.recommended_action}")
                for s in fp.suggestions:
                    lines.append(f"    - [{s.risk_level} risk] {s.title}: {s.description}")

        return "\n".join(lines)
