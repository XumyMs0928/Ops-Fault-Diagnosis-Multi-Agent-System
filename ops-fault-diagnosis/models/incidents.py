from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid

from models.alerts import AlertSeverity


class IncidentStatus(str, Enum):
    CREATED = "created"
    INVESTIGATING = "investigating"
    ROOT_CAUSE_FOUND = "root_cause_found"
    FIX_SUGGESTED = "fix_suggested"
    RESOLVED = "resolved"


class CorrelationGroup(BaseModel):
    group_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    alert_ids: list[str]
    common_service: str
    correlation_reason: str
    estimated_severity: AlertSeverity


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    status: IncidentStatus = IncidentStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.now)
    alert_groups: list[CorrelationGroup] = Field(default_factory=list)
    raw_alert_count: int = 0
    deduplicated_count: int = 0
    impacted_services: list[str] = Field(default_factory=list)
    summary: str = ""
