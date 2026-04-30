from __future__ import annotations

import json
import re
import time
from typing import Callable

import anthropic


def extract_json_block(text: str) -> str:
    """Extract JSON from Claude response, handling markdown code blocks."""
    # Try to find ```json ... ``` block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON array or object
    for pattern in [r"\[[\s\S]*\]", r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return text.strip()


def stream_claude_response(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict],
    on_chunk: Callable[[str], None] | None = None,
    max_tokens: int = 4096,
) -> tuple[str, dict]:
    """
    Stream a Claude response with optional chunk callback for real-time display.

    Returns (full_response_text, usage_stats).
    """
    full_text = ""
    usage_stats = {"input_tokens": 0, "output_tokens": 0}

    try:
        with client.messages.stream(
            model=model,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
        ) as stream:
            for text in stream.text_stream:
                full_text += text
                if on_chunk:
                    on_chunk(text)

            # Get final message for usage stats
            final_msg = stream.get_final_message()
            usage_stats["input_tokens"] = final_msg.usage.input_tokens
            usage_stats["output_tokens"] = final_msg.usage.output_tokens

    except anthropic.RateLimitError:
        # Simple backoff
        time.sleep(5)
        return stream_claude_response(
            client, model, system_prompt, messages, on_chunk, max_tokens
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}") from e

    return full_text, usage_stats


def call_claude_json(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list[dict],
    on_chunk: Callable[[str], None] | None = None,
    max_tokens: int = 4096,
) -> tuple[dict | list, dict]:
    """
    Call Claude and parse the response as JSON.
    Returns (parsed_json, usage_stats).
    """
    response_text, usage = stream_claude_response(
        client, model, system_prompt, messages, on_chunk, max_tokens
    )
    json_str = extract_json_block(response_text)
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        # Try recovery: find the deepest valid JSON
        parsed = _recover_json(json_str)

    return parsed, usage


def _recover_json(text: str) -> dict | list:
    """Attempt to recover partial JSON by finding valid substrings."""
    for i in range(len(text), 0, -1):
        try:
            return json.loads(text[:i])
        except json.JSONDecodeError:
            continue
    return {"raw_response": text}
