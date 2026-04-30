from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime
    service_name: str
    alert_name: str
    severity: AlertSeverity
    message: str
    labels: dict[str, str] = Field(default_factory=dict)
    fingerprint: str = ""

    def model_post_init(self, __context) -> None:
        if not self.fingerprint:
            self.fingerprint = f"{self.service_name}:{self.alert_name}:{self.severity.value}"


class AlertBatch(BaseModel):
    alerts: list[Alert]
    window_start: datetime
    window_end: datetime
