import json

import httpx
import pytest

from app.services.ollama import OllamaClient, OllamaError, parse_tool_calls, strip_thinking


def client_with(handler) -> OllamaClient:
    return OllamaClient("http://ollama.test:11434", "qwen3:8b", transport=httpx.MockTransport(handler))


def test_chat_posts_the_conversation_and_tools_to_ollama() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Hello"}})

    tools = [{"type": "function", "function": {"name": "search_catalog"}}]
    reply = client_with(handler).chat([{"role": "user", "content": "hi"}], tools)

    assert reply == {"role": "assistant", "content": "Hello"}
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    assert seen["body"]["model"] == "qwen3:8b"
    assert seen["body"]["stream"] is False
    assert seen["body"]["think"] is False
    assert seen["body"]["tools"] == tools
    assert seen["body"]["options"]["temperature"] == 0.3


def test_no_tools_key_is_sent_when_there_are_none() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    client_with(handler).chat([{"role": "user", "content": "hi"}], None)
    assert "tools" not in seen["body"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="model not found"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_a_broken_ollama_is_reported_as_one_error(response: httpx.Response) -> None:
    with pytest.raises(OllamaError):
        client_with(lambda _: response).chat([], None)


def test_an_unreachable_ollama_is_reported_as_one_error() -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(OllamaError):
        client_with(refuse).chat([], None)


def test_structured_tool_calls_are_read() -> None:
    message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": "evaluate_offer", "arguments": {"sku": "LOAF-BLK-43", "offer_naira": 35000}}},
            {"function": {"name": "search_catalog", "arguments": '{"query": "loafers"}'}},  # arguments as a string
        ],
    }
    calls = parse_tool_calls(message)
    assert [(c.name, c.arguments) for c in calls] == [
        ("evaluate_offer", {"sku": "LOAF-BLK-43", "offer_naira": 35000}),
        ("search_catalog", {"query": "loafers"}),
    ]


def test_tool_calls_written_into_the_text_are_read_too() -> None:
    message = {
        "role": "assistant",
        "content": '<think>they want a price</think>\n<tool_call>\n{"name": "search_catalog", "arguments": {"query": "sneakers"}}\n</tool_call>',
    }
    calls = parse_tool_calls(message)
    assert [(c.name, c.arguments) for c in calls] == [("search_catalog", {"query": "sneakers"})]


def test_plain_replies_have_no_tool_calls() -> None:
    assert parse_tool_calls({"role": "assistant", "content": "Hello there"}) == []
    assert parse_tool_calls({"role": "assistant", "content": "<tool_call>{broken</tool_call>"}) == []


def test_thinking_is_stripped_from_replies() -> None:
    assert strip_thinking("<think>hmm, price?</think>The loafers are ₦45,000.") == "The loafers are ₦45,000."
    assert strip_thinking("Fine.<think>never closed") == "Fine."
    assert strip_thinking("  plain  ") == "plain"
