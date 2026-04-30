from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

import anthropic
from pydantic import BaseModel, Field

from models.shared_context import SharedContext
from utils.streaming import stream_claude_response, call_claude_json, extract_json_block


class AgentResult(BaseModel):
    agent_name: str
    success: bool
    output: Any = None
    reasoning_trace: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    token_usage: dict = Field(default_factory=dict)


class BaseAgent(ABC):
    name: str = ""
    display_name: str = ""
    avatar: str = ""
    color: str = "white"

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-4-6"):
        self.client = client
        self.model = model
        self._system_prompt: str = ""
        self._conversation: list[dict] = []
        self._load_system_prompt()

    def _load_system_prompt(self) -> None:
        """Load system prompt from the prompts/ directory."""
        prompt_dir = Path(__file__).parent / "prompts"
        prompt_file = prompt_dir / f"{self.name}.md"
        if prompt_file.exists():
            self._system_prompt = prompt_file.read_text(encoding="utf-8")
        else:
            self._system_prompt = f"You are a helpful AI assistant named {self.display_name}."

    def _call_claude(
        self,
        user_message: str,
        event_callback: Callable | None = None,
        max_tokens: int = 4096,
    ) -> tuple[str, dict]:
        """Call Claude API with streaming. Returns (response_text, usage_stats)."""
        self._conversation.append({"role": "user", "content": user_message})

        def on_chunk(text: str):
            if event_callback:
                event_callback(self.name, "thinking_chunk", text)

        response_text, usage = stream_claude_response(
            client=self.client,
            model=self.model,
            system_prompt=self._system_prompt,
            messages=self._conversation,
            on_chunk=on_chunk,
            max_tokens=max_tokens,
        )

        self._conversation.append({"role": "assistant", "content": response_text})
        return response_text, usage

    def _call_claude_json(
        self,
        user_message: str,
        event_callback: Callable | None = None,
        max_tokens: int = 4096,
    ) -> tuple[Any, dict]:
        """Call Claude and parse response as JSON."""
        self._conversation.append({"role": "user", "content": user_message})

        def on_chunk(text: str):
            if event_callback:
                event_callback(self.name, "thinking_chunk", text)

        result, usage = call_claude_json(
            client=self.client,
            model=self.model,
            system_prompt=self._system_prompt,
            messages=self._conversation,
            on_chunk=on_chunk,
            max_tokens=max_tokens,
        )

        # Store the raw response in conversation history
        raw_response = json.dumps(result, ensure_ascii=False, indent=2)
        self._conversation.append({"role": "assistant", "content": raw_response})
        return result, usage

    def _reset_conversation(self) -> None:
        self._conversation = []

    @abstractmethod
    async def run(
        self, context: SharedContext, event_callback: Callable | None = None
    ) -> AgentResult:
        """Execute the agent's task. Must be implemented by each agent."""
        ...
