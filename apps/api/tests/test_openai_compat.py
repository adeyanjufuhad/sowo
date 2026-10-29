"""The hosted-model client: Qwen3 behind any OpenAI-compatible /chat/completions endpoint."""

import json

import httpx
import pytest

from app.config import Settings
from app.services.model import get_chat_model
from app.services.ollama import ModelError, OllamaClient, OllamaError, parse_tool_calls
from app.services.openai_compat import (
    OpenAICompatibleClient,
    from_openai_message,
    to_openai_messages,
)

BASE = "https://llm.test/openai/v1"


def client_with(handler, **options) -> OpenAICompatibleClient:
    options.setdefault("sleep", lambda _: None)
    return OpenAICompatibleClient(BASE, "key-123", "qwen/test", transport=httpx.MockTransport(handler), **options)


def answer(message: dict) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": message}]})


# -- the request ---------------------------------------------------------------------------------------


def test_chat_posts_to_chat_completions_with_the_key_and_tools() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return answer({"role": "assistant", "content": "Hello"})

    tools = [{"type": "function", "function": {"name": "search_catalog"}}]
    reply = client_with(handler).chat([{"role": "user", "content": "hi"}], tools)

    assert reply == {"role": "assistant", "content": "Hello"}
    assert seen["url"] == f"{BASE}/chat/completions"
    assert seen["auth"] == "Bearer key-123"
    assert seen["body"]["model"] == "qwen/test"
    assert seen["body"]["stream"] is False
    assert seen["body"]["temperature"] == 0.3
    assert seen["body"]["tools"] == tools
    assert "reasoning_effort" not in seen["body"]


def test_no_tools_key_and_reasoning_effort_only_when_asked_for() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return answer({"content": "ok"})

    client_with(handler, reasoning_effort="none").chat([{"role": "user", "content": "hi"}], None)
    assert "tools" not in seen["body"]
    assert seen["body"]["reasoning_effort"] == "none"


def test_no_authorization_header_without_a_key() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return answer({"content": "ok"})

    OpenAICompatibleClient(BASE, "", "m", transport=httpx.MockTransport(handler)).chat([], None)
    assert "authorization" not in seen["headers"]


# -- message translation ---------------------------------------------------------------------------------


def test_tool_calls_get_ids_and_json_arguments_and_results_answer_them_in_order() -> None:
    messages = [
        {"role": "system", "content": "You are Sowo."},
        {"role": "user", "content": "black loafers"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "search_catalog", "arguments": {"query": "loafers"}}},
                {"function": {"name": "get_quote", "arguments": {"sku": "LOAF-BLK-43"}}},
            ],
        },
        {"role": "tool", "tool_name": "search_catalog", "content": '{"results": []}'},
        {"role": "tool", "tool_name": "get_quote", "content": '{"total": 1}'},
        {"role": "user", "content": "ok"},
    ]
    converted = to_openai_messages(messages)

    calls = converted[2]["tool_calls"]
    assert [call["id"] for call in calls] == ["call_0", "call_1"]
    assert all(call["type"] == "function" for call in calls)
    assert json.loads(calls[0]["function"]["arguments"]) == {"query": "loafers"}
    assert converted[3] == {"role": "tool", "tool_call_id": "call_0", "content": '{"results": []}'}
    assert converted[4]["tool_call_id"] == "call_1"
    assert converted[5] == {"role": "user", "content": "ok"}
    assert "tool_name" not in converted[3]


def test_a_second_round_of_tool_calls_keeps_ids_unique() -> None:
    call = {"function": {"name": "search_catalog", "arguments": {}}}
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [call]},
        {"role": "tool", "content": "{}"},
        {"role": "assistant", "content": "", "tool_calls": [call]},
        {"role": "tool", "content": "{}"},
    ]
    converted = to_openai_messages(messages)
    assert [m["tool_calls"][0]["id"] for m in converted if m["role"] == "assistant"] == ["call_0", "call_1"]
    assert [m["tool_call_id"] for m in converted if m["role"] == "tool"] == ["call_0", "call_1"]


def test_string_arguments_are_passed_through_unchanged() -> None:
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "f", "arguments": '{"a": 1}'}}]},
    ]
    assert to_openai_messages(messages)[0]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'


# -- the reply -------------------------------------------------------------------------------------------


def test_structured_tool_calls_come_back_in_the_agents_shape() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "abc", "type": "function", "function": {"name": "get_quote", "arguments": '{"sku": "X", "qty": 2}'}}
        ],
    }
    reply = from_openai_message(message)
    assert reply["content"] == ""
    requests = parse_tool_calls(reply)
    assert [(r.name, r.arguments) for r in requests] == [("get_quote", {"sku": "X", "qty": 2})]


@pytest.mark.parametrize("arguments", ["", "not json", None])
def test_unreadable_arguments_become_an_empty_dict(arguments) -> None:
    reply = from_openai_message({"tool_calls": [{"function": {"name": "search_catalog", "arguments": arguments}}]})
    assert reply["tool_calls"][0]["function"]["arguments"] == {}


def test_malformed_tool_calls_are_skipped() -> None:
    reply = from_openai_message({"content": "hi", "tool_calls": ["junk", {"function": {"arguments": "{}"}}]})
    assert "tool_calls" not in reply and reply["content"] == "hi"


def test_a_tool_call_written_into_the_text_is_still_found() -> None:
    text = '<tool_call>{"name": "search_catalog", "arguments": {"query": "bag"}}</tool_call>'
    reply = from_openai_message({"content": text})
    assert [r.name for r in parse_tool_calls(reply)] == ["search_catalog"]


# -- failures --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="bad key"),
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_a_broken_host_is_reported_as_one_error(response: httpx.Response) -> None:
    with pytest.raises(ModelError):
        client_with(lambda _: response).chat([], None)


def test_the_old_error_name_still_catches_it() -> None:
    assert OllamaError is ModelError


def test_an_unreachable_host_is_reported_as_one_error() -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ModelError):
        client_with(refuse).chat([], None)


def test_a_busy_free_tier_gets_a_patient_retry() -> None:
    attempts: list[int] = []
    waits: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"retry-after": "3"}, text="slow down")
        return answer({"content": "back"})

    reply = client_with(handler, sleep=waits.append).chat([], None)
    assert reply["content"] == "back" and len(attempts) == 2 and waits == [3.5]


def test_the_wait_is_capped_and_repeated_refusals_are_an_error() -> None:
    attempts: list[int] = []
    waits: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, headers={"retry-after": "600"})

    with pytest.raises(ModelError):
        client_with(handler, sleep=waits.append).chat([], None)
    assert len(attempts) == 3 and waits == [20.0, 20.0]


def test_the_key_is_not_in_the_error_message() -> None:
    with pytest.raises(ModelError) as caught:
        client_with(lambda _: httpx.Response(401, text="bad key")).chat([], None)
    assert "key-123" not in str(caught.value)


# -- choosing the provider -------------------------------------------------------------------------------


def test_ollama_is_the_default_provider() -> None:
    assert Settings(_env_file=None).model_provider == "ollama"


def test_the_hosted_provider_needs_a_url_and_a_model() -> None:
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        Settings(_env_file=None, model_provider="openai")
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        Settings(_env_file=None, model_provider="openai", llm_base_url=BASE)
    Settings(_env_file=None, model_provider="openai", llm_base_url=BASE, llm_model="qwen/test")


def test_the_configured_provider_picks_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    try:
        monkeypatch.setenv("MODEL_PROVIDER", "openai")
        monkeypatch.setenv("LLM_BASE_URL", BASE)
        monkeypatch.setenv("LLM_MODEL", "qwen/test")
        get_settings.cache_clear()
        get_chat_model.cache_clear()
        assert isinstance(get_chat_model(), OpenAICompatibleClient)

        monkeypatch.setenv("MODEL_PROVIDER", "ollama")
        get_settings.cache_clear()
        get_chat_model.cache_clear()
        assert isinstance(get_chat_model(), OllamaClient)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_chat_model.cache_clear()


# -- malformed tool calls --------------------------------------------------------------------------------


def tool_use_failed(generation: str) -> httpx.Response:
    error = {"message": "tool call validation failed", "code": "tool_use_failed", "failed_generation": generation}
    return httpx.Response(400, json={"error": error})


def test_a_tool_call_the_host_rejected_is_read_from_its_failed_generation() -> None:
    generation = (
        "<tool_call>" + chr(10) + "<function=search_catalog>" + chr(10) + "<parameter/query>" + chr(10)
        + "black loafers 43" + chr(10) + "</parameter>" + chr(10) + "</function>" + chr(10) + "</tool_call>"
    )
    reply = client_with(lambda _: tool_use_failed(generation)).chat([], [{"type": "function"}])
    assert [(r.name, r.arguments) for r in parse_tool_calls(reply)] == [("search_catalog", {"query": "black loafers 43"})]


def test_numbers_and_booleans_in_a_rejected_call_get_their_types_back() -> None:
    generation = (
        "<function=evaluate_offer><parameter=sku>LOAF-BLK-43</parameter>"
        "<parameter=offered_price_kobo>3500000</parameter><parameter=final>true</parameter></function>"
    )
    reply = client_with(lambda _: tool_use_failed(generation)).chat([], None)
    assert parse_tool_calls(reply)[0].arguments == {"sku": "LOAF-BLK-43", "offered_price_kobo": 3500000, "final": True}


def test_a_400_that_holds_no_readable_call_is_still_an_error_with_the_hosts_reason() -> None:
    with pytest.raises(ModelError, match="tool call validation failed"):
        client_with(lambda _: tool_use_failed("nothing useful")).chat([], None)
    with pytest.raises(ModelError, match="invalid model"):
        client_with(lambda _: httpx.Response(400, json={"error": {"message": "invalid model"}})).chat([], None)


def rejected_call(name: str, tools: list[dict]) -> list:
    """A call the host turned down, replayed through the client so its own text is read back."""
    generation = (
        "</tool_call>" + chr(10) + "<function=" + name + ">" + chr(10)
        + "<parameter=sku>" + chr(10) + "LOAF-BLK-14" + chr(10) + "</parameter>" + chr(10)
        + "<parameter=offer_naira>" + chr(10) + "35000" + chr(10) + "</parameter>" + chr(10)
        + "</function>" + chr(10) + "</tool_call>"
    )
    return parse_tool_calls(client_with(lambda _: tool_use_failed(generation)).chat([], tools))


def test_a_tool_name_the_model_wrote_with_junk_in_it_still_runs() -> None:
    # What Groq actually returned on 2026-10-29 when Qwen haggled: the arguments were fine, the name was not.
    tools = [{"function": {"name": "evaluate_offer"}}]
    for written in ("evaluate$$$$$offer", "evaluate Offering"):
        call = rejected_call(written, tools)[0]
        assert (call.name, call.arguments) == ("evaluate_offer", {"sku": "LOAF-BLK-14", "offer_naira": 35000})


def test_a_tool_name_cut_short_still_resolves_when_only_one_tool_starts_with_it() -> None:
    call = rejected_call("evaluate", [{"function": {"name": "evaluate_offer"}}])[0]
    assert call.name == "evaluate_offer"


def test_a_tool_name_that_could_be_two_tools_is_left_for_the_agent_to_reject() -> None:
    tools = [{"function": {"name": "evaluate_offer"}}, {"function": {"name": "escalate_to_vendor"}}]
    assert [call.name for call in rejected_call("e", tools)] == ["e"]


def test_a_tool_name_with_nothing_like_it_in_the_request_is_left_alone() -> None:
    call = rejected_call("sell_shoes", [{"function": {"name": "evaluate_offer"}}])[0]
    assert call.name == "sell_shoes"
