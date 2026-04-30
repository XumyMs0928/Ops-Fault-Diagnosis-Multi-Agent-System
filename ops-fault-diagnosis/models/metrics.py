from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class MetricType(str, Enum):
    CPU = "cpu_utilization_percent"
    MEMORY = "memory_utilization_percent"
    LATENCY_P99 = "latency_p99_ms"
    ERROR_RATE = "error_rate_percent"
    DISK = "disk_utilization_percent"
    CONNECTION_ACTIVE = "active_connections"


class MetricDataPoint(BaseModel):
    timestamp: datetime
    service_name: str
    metric_type: MetricType
    value: float


class MetricAnomaly(BaseModel):
    service_name: str
    metric_type: MetricType
    observed_value: float
    baseline_value: float
    deviation_percent: float
    start_time: datetime
    is_anomaly: bool = True
