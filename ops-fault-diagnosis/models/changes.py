from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class ChangeType(str, Enum):
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    SCHEMA_MIGRATION = "schema_migration"
    SCALING = "scaling"


class ChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime
    service_name: str
    change_type: ChangeType
    description: str
    author: str
    rollback_possible: bool = True
    related_incidents: list[str] = Field(default_factory=list)
