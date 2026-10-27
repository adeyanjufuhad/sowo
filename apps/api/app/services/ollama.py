"""Qwen3 through Ollama's /api/chat, with tool calling.

One POST per model turn and no SDK, so the whole conversation with the model is easy to read and to fake in
tests. The agent (app/services/agent.py) only depends on the small ChatModel protocol below.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import get_settings


class ModelError(RuntimeError):
    """The model (Ollama or a hosted endpoint) was unreachable, timed out, or answered with something we can't use."""


OllamaError = ModelError  # the name the agent, the flow and the tests grew up with


class ChatModel(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        """Send the conversation, return the assistant message: {"role", "content", "tool_calls"?}."""
        ...


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        temperature: float = 0.3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._temperature = temperature
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # Qwen3 can "think" before answering. On a shop's WhatsApp that is seconds of dead air for
            # no gain, because the server, not the model, makes every decision that matters.
            "think": False,
            "options": {"temperature": self._temperature},
        }
        if tools:
            payload["tools"] = tools
        try:
            response = self._http.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict):
            raise OllamaError("Ollama returned no message")
        return message


@lru_cache
def get_ollama_client() -> OllamaClient:
    settings = get_settings()
    return OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
        temperature=settings.ollama_temperature,
    )


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_TOOL_CALL_BLOCK = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove any <think>…</think> block (and a dangling opener) from a model reply."""
    text = _THINK_BLOCK.sub("", text)
    if "<think>" in text.lower():
        text = re.split(r"<think>", text, flags=re.IGNORECASE)[0]
    return text.strip()


def _as_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def parse_tool_calls(message: dict[str, Any]) -> list[ToolRequest]:
    """Tool calls from an assistant message.

    Ollama normally returns them structured. Qwen3 sometimes writes them into the text as
    <tool_call>{"name": …, "arguments": …}</tool_call> instead, so accept that form too.
    """
    requests: list[ToolRequest] = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") if isinstance(call, dict) else None
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            requests.append(ToolRequest(function["name"], _as_arguments(function.get("arguments"))))
    if requests:
        return requests
    content = message.get("content")
    if isinstance(content, str):
        for block in _TOOL_CALL_BLOCK.findall(strip_thinking_keep_calls(content)):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and isinstance(data.get("name"), str):
                requests.append(ToolRequest(data["name"], _as_arguments(data.get("arguments"))))
    return requests


def strip_thinking_keep_calls(text: str) -> str:
    """Like strip_thinking, but for finding <tool_call> blocks: only drop closed think blocks."""
    return _THINK_BLOCK.sub("", text)
