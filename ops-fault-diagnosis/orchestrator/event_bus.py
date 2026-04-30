from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel


class AgentEvent(BaseModel):
    agent_name: str
    event_type: str  # "thinking_chunk", "step", "result", "phase_change"
    data: Any
    timestamp: datetime = None

    def model_post_init(self, __context) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """Simple in-process pub/sub for agent events."""

    def __init__(self):
        self._subscribers: list[Callable[[AgentEvent], None]] = []

    def subscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        self._subscribers = [s for s in self._subscribers if s != callback]

    def emit(self, agent_name: str, event_type: str, data: Any) -> None:
        event = AgentEvent(
            agent_name=agent_name,
            event_type=event_type,
            data=data,
        )
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception:
                pass  # Don't let display errors break the agent pipeline

    def create_callback(self, agent_name: str) -> Callable:
        """Create a callback bound to a specific agent name."""
        def callback(event_type: str, data: Any) -> None:
            self.emit(agent_name, event_type, data)
        return callback
