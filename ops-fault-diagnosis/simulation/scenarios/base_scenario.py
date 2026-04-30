from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel

from models.topology import ServiceTopology


class AlertStormProfile(BaseModel):
    """Defines the core alert cascade for a scenario."""
    root_service: str
    surface_services: list[str]
    affected_services: list[str]
    core_alerts: list[dict]  # [{delay_seconds, service, alert_name, severity, message}]
    noise_services: list[str]  # services to generate unrelated noise alerts from


class LogFaultProfile(BaseModel):
    """Defines the fault-specific log entries for a scenario."""
    fault_logs: list[dict]  # [{delay_seconds, service, level, message, exception_class}]
    noise_ratio: float = 0.3  # ratio of normal INFO logs to inject


class MetricsFaultProfile(BaseModel):
    """Defines metric anomaly injections for a scenario."""
    anomalies: list[dict]  # [{service, metric_type, baseline, observed, deviation_percent}]


class ChangeProfile(BaseModel):
    """Defines recent changes relevant to the scenario."""
    root_cause_changes: list[dict]  # [{delay_hours, service, change_type, description, author}]
    noise_changes: list[dict]  # unrelated changes for misdirection


class BaseScenario(ABC):
    @abstractmethod
    def scenario_id(self) -> str: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def get_alert_profile(self) -> AlertStormProfile: ...

    @abstractmethod
    def get_log_profile(self) -> LogFaultProfile: ...

    @abstractmethod
    def get_metrics_profile(self) -> MetricsFaultProfile: ...

    @abstractmethod
    def get_change_profile(self) -> ChangeProfile: ...

    @abstractmethod
    def incident_timestamp(self) -> datetime: ...
