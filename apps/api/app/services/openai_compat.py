"""Qwen3 through any OpenAI-compatible /chat/completions endpoint (Groq, OpenRouter, Cloudflare, vLLM, ...).

Lets the model run on a hosted free tier instead of on the developer's laptop. The agent only depends on the
ChatModel protocol, so this speaks the agent's own message shape (the one Ollama uses) on the way in and out and
translates to and from the OpenAI one here: tool-call ids, JSON-string arguments and the `tool` role.
"""

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.services.ollama import ModelError

RETRY_STATUSES = {429, 502, 503}
MAX_RETRY_WAIT_SECONDS = 20.0
MAX_RETRIES = 2


_XML_FUNCTION = re.compile(r"<function[=/]\s*([A-Za-z_][\w.-]*)\s*>(.*?)</function>", re.DOTALL)
_XML_PARAMETER = re.compile(r"<parameter[=/]\s*([A-Za-z_][\w.-]*)\s*>(.*?)</parameter>", re.DOTALL)


def _typed(value: str) -> Any:
    """XML carries everything as text; the tools take whole numbers and booleans."""
    value = value.strip()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def calls_from_failed_generation(text: str) -> list[dict[str, Any]]:
    """Tool calls written in Qwen's XML layout, which some hosts reject before we see them.

    Groq answers 400 tool_use_failed and returns the model's raw text as `failed_generation` when Qwen writes
    <function=name><parameter=key>value</parameter></function> and slips on the syntax. The meaning is clear, so
    read it. Whatever is read is still checked by the server's own tools like any other call.
    """
    calls = []
    for name, body in _XML_FUNCTION.findall(text):
        arguments = {key: _typed(value) for key, value in _XML_PARAMETER.findall(body)}
        calls.append({"function": {"name": name, "arguments": arguments}})
    return calls


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The agent's messages in OpenAI's shape. A tool result answers the assistant's calls in order."""
    converted: list[dict[str, Any]] = []
    waiting: list[str] = []
    issued = 0
    for message in messages:
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            calls = []
            for call in message["tool_calls"]:
                function = call.get("function", {})
                arguments = function.get("arguments", {})
                call_id = call.get("id") or f"call_{issued}"
                issued += 1
                waiting.append(call_id)
                calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": function.get("name", ""),
                            "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
                        },
                    }
                )
            converted.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        elif role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": waiting.pop(0) if waiting else f"call_{issued}",
                    "content": message.get("content", ""),
                }
            )
        else:
            converted.append({"role": role, "content": message.get("content", "")})
    return converted


def from_openai_message(message: dict[str, Any]) -> dict[str, Any]:
    """An OpenAI assistant message as the agent expects it: {"role", "content", "tool_calls"?}."""
    reply: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            continue
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except ValueError:
                arguments = {}
        calls.append(
            {"id": call.get("id"), "function": {"name": function["name"], "arguments": arguments or {}}}
        )
    if calls:
        reply["tool_calls"] = calls
    return reply


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120.0,
        temperature: float = 0.3,
        reasoning_effort: str = "",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._sleep = sleep
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport, headers=headers
        )

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(messages),
            "temperature": self._temperature,
            "stream": False,
        }
        if self._reasoning_effort:
            # Qwen3 "thinks" before answering, which is seconds of dead air on WhatsApp. Hosts that support it take
            # a setting such as "none"; anything left over is stripped from the reply by the agent.
            payload["reasoning_effort"] = self._reasoning_effort
        if tools:
            payload["tools"] = tools
        try:
            response = self._post(payload)
            data = response.json()
        except httpx.HTTPStatusError as exc:
            recovered = self._recover_tool_call(exc.response)
            if recovered is not None:
                return recovered
            # The host says why in the body (a bad tool call, a retired model, a limit); the status line doesn't.
            raise ModelError(f"Model request failed: {exc} -- {exc.response.text[:600]}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelError(f"Model request failed: {exc}") from exc
        choices = data.get("choices") if isinstance(data, dict) else None
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        if not isinstance(message, dict):
            raise ModelError("The model returned no message")
        return from_openai_message(message)

    @staticmethod
    def _recover_tool_call(response: httpx.Response) -> dict[str, Any] | None:
        if response.status_code != 400:
            return None
        try:
            error = response.json()["error"]
            generated = error["failed_generation"] if error.get("code") == "tool_use_failed" else ""
        except (ValueError, KeyError, TypeError):
            return None
        calls = calls_from_failed_generation(generated) if isinstance(generated, str) else []
        return {"role": "assistant", "content": "", "tool_calls": calls} if calls else None

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """One POST, and a couple of patient retries if a free tier says it is busy or a per-minute limit is hit."""
        response = self._http.post("/chat/completions", json=payload)
        for _ in range(MAX_RETRIES):
            if response.status_code not in RETRY_STATUSES:
                break
            try:
                wait = float(response.headers.get("retry-after", "2"))
            except ValueError:
                wait = 2.0
            # Hosts round the wait down a little, so add half a second.
            self._sleep(min(max(wait + 0.5, 0.5), MAX_RETRY_WAIT_SECONDS))
            response = self._http.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response
