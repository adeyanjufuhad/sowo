"""Logging, rate limits and the readiness check."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import observability
from app.config import Settings, get_settings
from app.ratelimit import SlidingWindowLimiter
from tests.helpers import BUYER_PHONE, WHATSAPP_NUMBER_ID, whatsapp_payload

PASSWORD = "a long enough password"


def sign_up(client: TestClient, email: str = "bola@example.com", name: str = "Bola's Bags") -> object:
    return client.post("/auth/signup", json={"email": email, "password": PASSWORD, "businessName": name})


# -- the limiter -------------------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_limiter_allows_up_to_the_limit_then_says_how_long_to_wait() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(clock=clock)
    assert [limiter.hit("a", 3, 60) for _ in range(3)] == [0, 0, 0]
    clock.now += 20
    assert limiter.hit("a", 3, 60) == pytest.approx(40)
    assert limiter.hit("b", 3, 60) == 0  # other keys are unaffected
    clock.now += 41  # the first hit is now outside the window
    assert limiter.hit("a", 3, 60) == 0


def test_a_refused_hit_is_not_counted() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(clock=clock)
    limiter.hit("a", 1, 60)
    for _ in range(5):
        assert limiter.hit("a", 1, 60) > 0
    clock.now += 61
    assert limiter.hit("a", 1, 60) == 0


def test_the_limiter_cannot_grow_without_bound() -> None:
    limiter = SlidingWindowLimiter(clock=Clock(), max_keys=100)
    for index in range(1000):
        limiter.hit(f"key-{index}", 5, 60)
    assert len(limiter._hits) <= 100


# -- rate limits on the routes -----------------------------------------------------------------------------


def test_sign_in_and_sign_up_are_limited_per_address(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    get_settings.cache_clear()
    bad = {"email": "nobody@example.com", "password": PASSWORD}
    assert [anonymous_client.post("/auth/login", json=bad).status_code for _ in range(3)] == [401, 401, 401]
    refused = anonymous_client.post("/auth/login", json=bad)
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "RATE_LIMITED"
    assert int(refused.headers["retry-after"]) >= 1
    assert sign_up(anonymous_client).status_code == 429  # sign-up and sign-in share the allowance


def test_other_routes_are_not_limited_by_the_auth_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "1")
    get_settings.cache_clear()
    assert all(client.get("/products").status_code == 200 for _ in range(5))


def test_failed_sign_ins_are_also_limited_per_email(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    get_settings.cache_clear()
    assert sign_up(anonymous_client).status_code == 201
    wrong = {"email": "bola@example.com", "password": "not the password"}
    assert [anonymous_client.post("/auth/login", json=wrong).status_code for _ in range(3)] == [401, 401, 401]
    blocked = anonymous_client.post("/auth/login", json=wrong)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "RATE_LIMITED"
    # Even the right password waits, so guessing can't continue; another account is unaffected.
    assert anonymous_client.post("/auth/login", json={**wrong, "password": PASSWORD}).status_code == 429
    assert anonymous_client.post("/auth/login", json={"email": "other@example.com", "password": "x" * 12}).status_code == 401


def test_a_good_sign_in_clears_the_failure_count(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "3")
    get_settings.cache_clear()
    sign_up(anonymous_client)
    email = "bola@example.com"
    for _ in range(2):
        assert anonymous_client.post("/auth/login", json={"email": email, "password": "wrong password"}).status_code == 401
    assert anonymous_client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    for _ in range(2):
        assert anonymous_client.post("/auth/login", json={"email": email, "password": "wrong password"}).status_code == 401


def test_the_address_comes_from_the_trusted_header_when_one_is_named(
    anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "1")
    monkeypatch.setenv("CLIENT_IP_HEADER", "x-forwarded-for")
    get_settings.cache_clear()
    bad = {"email": "nobody@example.com", "password": PASSWORD}
    assert anonymous_client.post("/auth/login", json=bad, headers={"x-forwarded-for": "198.51.100.1"}).status_code == 401
    assert anonymous_client.post("/auth/login", json=bad, headers={"x-forwarded-for": "198.51.100.2, 10.0.0.1"}).status_code == 401
    assert anonymous_client.post("/auth/login", json=bad, headers={"x-forwarded-for": "198.51.100.1"}).status_code == 429


def test_the_forwarded_header_is_ignored_unless_it_is_named(
    anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "1")
    get_settings.cache_clear()
    bad = {"email": "nobody@example.com", "password": PASSWORD}
    anonymous_client.post("/auth/login", json=bad, headers={"x-forwarded-for": "198.51.100.1"})
    assert anonymous_client.post("/auth/login", json=bad, headers={"x-forwarded-for": "198.51.100.2"}).status_code == 429


def test_webhooks_are_limited_before_their_signature_is_checked(
    anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_WEBHOOKS_PER_MINUTE", "2")
    get_settings.cache_clear()
    unsigned = {"content": b"{}", "headers": {"content-type": "application/json"}}
    assert [anonymous_client.post("/webhooks/whatsapp", **unsigned).status_code for _ in range(2)] == [403, 403]
    assert anonymous_client.post("/webhooks/whatsapp", **unsigned).status_code == 429
    assert anonymous_client.post("/webhooks/paystack", **unsigned).status_code == 429  # one allowance for both


def test_limits_can_be_switched_off(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "1")
    monkeypatch.setenv("LOGIN_MAX_FAILURES", "1")
    get_settings.cache_clear()
    bad = {"email": "nobody@example.com", "password": PASSWORD}
    assert [anonymous_client.post("/auth/login", json=bad).status_code for _ in range(5)] == [401] * 5


# -- readiness ---------------------------------------------------------------------------------------------


def test_health_answers_without_the_database(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    def unavailable() -> None:
        raise AssertionError("/health must not open a database session")

    main.app.dependency_overrides[main.get_db] = unavailable
    assert anonymous_client.get("/health").json() == {"status": "ok"}


def test_ready_checks_the_database(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/ready")
    assert response.status_code == 200 and response.json() == {"status": "ready"}


def test_ready_says_unavailable_when_the_database_is_down(
    anonymous_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    from app import main

    class Broken:
        def execute(self, *_: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("password=hunter2 host=db.internal"))

    def broken():
        yield Broken()

    main.app.dependency_overrides[main.get_db] = broken
    with caplog.at_level(logging.ERROR):
        response = anonymous_client.get("/ready")
    assert response.status_code == 503 and response.json() == {"status": "unavailable"}
    assert "hunter2" not in caplog.text and "db.internal" not in caplog.text
    assert "OperationalError" in caplog.text


# -- logging -----------------------------------------------------------------------------------------------


def test_redaction_masks_phone_numbers_and_secrets() -> None:
    line = "to +2348012345678 and 2348012345678 via 1555000111; Bearer abc.def-123 sk_live_AbCd123 ref SOWO_12ab; 42 items"
    redacted = observability.redact(line)
    assert "2348012345678" not in redacted and "1555000111" not in redacted
    assert "abc.def-123" not in redacted and "AbCd123" not in redacted
    assert "***678" in redacted and "***111" in redacted
    assert "SOWO_12ab" in redacted and "42 items" in redacted


def _lines(caplog_text: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in caplog_text.splitlines() if line.startswith("{")]


def test_each_request_is_one_json_line_with_an_id_and_no_ids_from_the_url(
    anonymous_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    observability.configure_logging(Settings(_env_file=None))
    try:
        response = anonymous_client.get("/conversations/conv_secret_123/messages?phone=2348012345678", headers={"x-request-id": "trace-1"})
        assert response.headers["x-request-id"] == "trace-1"
        captured = capsys.readouterr().err
    finally:
        logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not getattr(h, "_sowo", False)]
    entry = next(item for item in _lines(captured) if item["logger"] == "app.request")
    assert entry["request_id"] == "trace-1"
    assert entry["method"] == "GET" and entry["status"] == 401 and entry["path"] == "/conversations/{conversation_id}/messages"
    assert "conv_secret_123" not in captured and "2348012345678" not in captured and "phone=" not in captured


def test_a_made_up_request_id_is_replaced(anonymous_client: TestClient) -> None:
    for supplied in ("has spaces", "x" * 200, "<script>"):
        response = anonymous_client.get("/health", headers={"x-request-id": supplied})
        assert response.headers["x-request-id"] != supplied
        assert len(response.headers["x-request-id"]) == 32


def test_health_checks_are_not_logged_but_failures_are(anonymous_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        anonymous_client.get("/health")
        assert not [record for record in caplog.records if record.name == "app.request"]
        anonymous_client.get("/orders")
    assert [record.fields["status"] for record in caplog.records] == [401]  # type: ignore[attr-defined]


def test_a_crash_is_logged_with_its_request_id_and_answered_without_details(
    env: object, caplog: pytest.LogCaptureFixture
) -> None:
    from app import main

    @main.app.get("/_boom")
    def boom() -> None:
        raise RuntimeError("secret detail 2348012345678")

    try:
        with TestClient(main.app, raise_server_exceptions=False) as test_client, caplog.at_level(logging.ERROR):
            response = test_client.get("/_boom")
    finally:
        main.app.router.routes = [route for route in main.app.router.routes if getattr(route, "path", "") != "/_boom"]
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL", "message": "Something went wrong on our side"}}
    assert "secret detail" not in response.text
    assert any(record.levelno == logging.ERROR and record.name == "app.request" for record in caplog.records)


def test_a_webhook_message_is_still_handled_under_the_new_middleware(env: object, anonymous_client: TestClient) -> None:
    from tests.helpers import signed

    body, headers = signed(whatsapp_payload("hi", phone=BUYER_PHONE, phone_number_id=WHATSAPP_NUMBER_ID))
    assert anonymous_client.post("/webhooks/whatsapp", content=body, headers=headers).status_code == 200
