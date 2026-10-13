"""OpenRouter client (via the OpenAI-compatible API) with streaming.

`LLMClient.stream_chat` streams a chat completion, forwards text deltas to a
callback as they arrive, and assembles the final assistant message, including
tool calls that arrive split across many chunks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

import openai

from .config import Config


class LLMError(Exception):
    """Raised for API failures; message is safe to show (contains no secrets)."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as produced by the model

    def parsed_arguments(self) -> dict:
        """Parse arguments JSON; raises ValueError with a readable message."""
        if not self.arguments.strip():
            return {}
        try:
            args = json.loads(self.arguments)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON arguments for {self.name}: {e}") from e
        if not isinstance(args, dict):
            raise ValueError(f"arguments for {self.name} must be a JSON object")
        return args


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict | None = None

    def to_dict(self) -> dict:
        """Convert to an OpenAI-format message for appending to history."""
        msg: dict = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments or "{}"},
                }
                for tc in self.tool_calls
            ]
        return msg


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self._client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            default_headers={"X-Title": "Engram"},  # optional OpenRouter attribution
        )

    @property
    def model(self) -> str:
        return self.config.model

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> AssistantMessage:
        kwargs: dict = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            kwargs["max_tokens"] = self.config.max_tokens

        result = AssistantMessage()
        text_parts: list[str] = []
        # Tool-call fragments keyed by their `index`; id/name usually arrive in the
        # first fragment and `arguments` is streamed piecewise across later ones.
        partial_calls: dict[int, dict] = {}

        try:
            stream = self._client.chat.completions.create(**kwargs)
            for chunk in stream:
                if chunk.usage:
                    result.usage = chunk.usage.model_dump()
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta is not None:
                    if delta.content:
                        text_parts.append(delta.content)
                        if on_token:
                            on_token(delta.content)
                    for tc in delta.tool_calls or []:
                        idx = tc.index if tc.index is not None else len(partial_calls)
                        slot = partial_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function is not None:
                            if tc.function.name:
                                slot["name"] += tc.function.name
                            if tc.function.arguments:
                                slot["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    result.finish_reason = choice.finish_reason
        except openai.AuthenticationError:
            raise LLMError("authentication failed: check OPENROUTER_API_KEY") from None
        except openai.NotFoundError as e:
            raise LLMError(f"model or endpoint not found ({self.config.model}): {_err_msg(e)}") from None
        except openai.RateLimitError as e:
            raise LLMError(f"rate limited: {_err_msg(e)}") from None
        except openai.APIStatusError as e:
            raise LLMError(f"API error {e.status_code}: {_err_msg(e)}") from None
        except openai.APIConnectionError:
            raise LLMError(f"could not connect to {self.config.base_url}") from None

        result.content = "".join(text_parts)
        for i, slot in enumerate(partial_calls[k] for k in sorted(partial_calls)):
            result.tool_calls.append(
                ToolCall(id=slot["id"] or f"call_{i}", name=slot["name"], arguments=slot["arguments"])
            )
        return result


def _err_msg(e: openai.APIStatusError) -> str:
    body = e.body
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    return str(getattr(e, "message", "")) or e.__class__.__name__
