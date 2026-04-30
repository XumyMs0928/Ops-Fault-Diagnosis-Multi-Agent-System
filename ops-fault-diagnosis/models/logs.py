from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class LogLevel(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"
    DEBUG = "DEBUG"


class LogEntry(BaseModel):
    timestamp: datetime
    service_name: str
    level: LogLevel
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    exception_class: str | None = None
    stack_trace: str | None = None
