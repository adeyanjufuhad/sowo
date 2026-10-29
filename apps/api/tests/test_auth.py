"""Vendor accounts, sessions, and keeping each vendor's data to themselves."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import VENDOR_EMAIL, VENDOR_PASSWORD, sign_in_vendor
from scenarios import new_chat, sell_loafers
from sqlalchemy import select

from app.models import Order, Vendor, VendorSession
from app.services import auth

PASSWORD = "a long enough passphrase"


def signup(client: TestClient, email: str = "bola@example.com", name: str = "Bola's Bags", password: str = PASSWORD) -> Any:
    return client.post("/auth/signup", json={"email": email, "password": password, "businessName": name})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# -- signing up and in ---------------------------------------------------------------------------------


def test_signing_up_creates_a_vendor_and_a_session(env: Env, anonymous_client: TestClient) -> None:
    response = signup(anonymous_client)

    assert response.status_code == 201
    body = response.json()
    assert body["vendor"]["name"] == "Bola's Bags" and body["vendor"]["email"] == "bola@example.com"
    assert anonymous_client.get("/auth/me", headers=bearer(body["sessionToken"])).json()["vendor"]["id"] == body["vendor"]["id"]


def test_neither_the_password_nor_the_token_is_stored_as_given(env: Env, anonymous_client: TestClient) -> None:
    token = signup(anonymous_client).json()["sessionToken"]

    with env.session() as session:
        vendor = session.scalar(select(Vendor).where(Vendor.email == "bola@example.com"))
        stored = session.scalar(select(VendorSession).where(VendorSession.vendor_id == vendor.id))  # type: ignore[union-attr]
    assert vendor is not None and stored is not None
    assert vendor.password_hash and vendor.password_hash.startswith("$argon2id$") and PASSWORD not in vendor.password_hash
    assert stored.token_hash != token and len(stored.token_hash) == 64


def test_the_default_hasher_is_argon2id() -> None:
    from argon2 import PasswordHasher

    assert PasswordHasher().hash("x").startswith("$argon2id$")
    assert auth._hasher.hash("x").startswith("$argon2id$")


def test_emails_are_matched_ignoring_case_and_spaces(env: Env, anonymous_client: TestClient) -> None:
    signup(anonymous_client, email="  Bola@Example.COM ")

    assert signup(anonymous_client, email="bola@example.com", name="Another").status_code == 409
    assert anonymous_client.post("/auth/login", json={"email": "BOLA@example.com", "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"email": "not-an-email"}, "valid email"),
        ({"password": "short"}, "at least 10"),
        ({"password": "x" * 129}, "at most 128"),
        ({"businessName": "   "}, "business name"),
        ({"businessName": "x" * 121}, "business name"),
    ],
)
def test_bad_signups_are_refused_with_a_reason(env: Env, anonymous_client: TestClient, changes: dict[str, str], message: str) -> None:
    payload = {"email": "bola@example.com", "password": PASSWORD, "businessName": "Bola's Bags", **changes}

    response = anonymous_client.post("/auth/signup", json=payload)

    assert response.status_code == 400 and message in response.json()["error"]["message"]
    with env.session() as session:
        assert session.scalar(select(Vendor).where(Vendor.email == "bola@example.com")) is None


def test_a_business_name_can_only_be_taken_once(env: Env, anonymous_client: TestClient) -> None:
    assert signup(anonymous_client, name="Ada's Footwear").status_code == 409  # the seeded shop


def test_logging_in_with_the_right_password_starts_a_session(env: Env, anonymous_client: TestClient) -> None:
    signup(anonymous_client)

    response = anonymous_client.post("/auth/login", json={"email": "bola@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert anonymous_client.get("/auth/me", headers=bearer(response.json()["sessionToken"])).status_code == 200


def test_a_wrong_password_and_an_unknown_email_look_the_same(env: Env, anonymous_client: TestClient) -> None:
    signup(anonymous_client)

    wrong = anonymous_client.post("/auth/login", json={"email": "bola@example.com", "password": "not the password"})
    unknown = anonymous_client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"error": {"code": "UNAUTHORIZED", "message": "Incorrect email or password"}}


def test_an_unknown_email_still_costs_a_password_check(env: Env, anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class CountingHasher:
        def __init__(self, inner: Any) -> None:
            self.inner, self.verifies = inner, 0

        def verify(self, *args: Any, **kwargs: Any) -> bool:
            self.verifies += 1
            return self.inner.verify(*args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

    counting = CountingHasher(auth._hasher)
    monkeypatch.setattr(auth, "_hasher", counting)

    anonymous_client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})

    assert counting.verifies == 1  # so response time doesn't reveal which emails have accounts


def test_a_vendor_without_a_password_cannot_log_in(env: Env, anonymous_client: TestClient) -> None:
    """The seeded shop exists but has no login until someone claims it."""
    response = anonymous_client.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert response.status_code == 401

    with env.session() as session:
        vendor = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
        assert vendor is not None and vendor.password_hash is None


# -- sessions ------------------------------------------------------------------------------------------


def test_logging_out_ends_only_that_session(env: Env, anonymous_client: TestClient) -> None:
    signup(anonymous_client)
    first = anonymous_client.post("/auth/login", json={"email": "bola@example.com", "password": PASSWORD}).json()["sessionToken"]
    second = anonymous_client.post("/auth/login", json={"email": "bola@example.com", "password": PASSWORD}).json()["sessionToken"]

    assert anonymous_client.post("/auth/logout", headers=bearer(first)).json() == {"ok": True}

    assert anonymous_client.get("/auth/me", headers=bearer(first)).status_code == 401
    assert anonymous_client.get("/auth/me", headers=bearer(second)).status_code == 200


def test_an_expired_session_is_refused_and_removed(env: Env, anonymous_client: TestClient) -> None:
    token = signup(anonymous_client).json()["sessionToken"]
    with env.session() as session:
        session.query(VendorSession).update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
        session.commit()

    assert anonymous_client.get("/auth/me", headers=bearer(token)).status_code == 401
    with env.session() as session:
        assert session.scalar(select(VendorSession)) is None


def test_using_a_session_does_not_write_on_every_request(env: Env) -> None:
    with env.session() as session:
        vendor = session.scalar(select(Vendor))
        assert vendor is not None
        token, _ = auth.create_session(session, vendor)
        created = session.scalar(select(VendorSession)).last_used_at  # type: ignore[union-attr]
        now = datetime.now(UTC)

        auth.find_vendor(session, token, now=now + timedelta(minutes=1))
        assert session.scalar(select(VendorSession)).last_used_at == created  # type: ignore[union-attr]

        auth.find_vendor(session, token, now=now + timedelta(minutes=6))
        assert session.scalar(select(VendorSession)).last_used_at != created  # type: ignore[union-attr]


# -- nothing is readable without logging in ------------------------------------------------------------

DASHBOARD_ROUTES = [
    ("GET", "/conversations"),
    ("GET", "/conversations/x/messages"),
    ("POST", "/conversations/x/pause"),
    ("POST", "/conversations/x/resume"),
    ("POST", "/conversations/x/messages"),
    ("GET", "/orders"),
    ("GET", "/products"),
    ("POST", "/orders/x/mark-paid"),
    ("GET", "/auth/me"),
    ("POST", "/auth/logout"),
]


@pytest.mark.parametrize(("method", "path"), DASHBOARD_ROUTES)
def test_dashboard_routes_need_a_session(env: Env, anonymous_client: TestClient, method: str, path: str) -> None:
    response = anonymous_client.request(method, path, json={"body": "hi"} if method == "POST" else None)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Bearer", "Bearer ", "Basic abc", "Bearer not-a-real-token", "token"])
def test_a_malformed_or_unknown_credential_is_refused(env: Env, anonymous_client: TestClient, header: str) -> None:
    assert anonymous_client.get("/orders", headers={"Authorization": header}).status_code == 401


def test_health_and_webhooks_stay_public(env: Env, anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/health").status_code == 200
    # Webhooks are protected by their own signatures, not a login: a bad one is "forbidden", not "sign in".
    bad = anonymous_client.post("/webhooks/whatsapp", content=b"{}", headers={"X-Hub-Signature-256": "sha256=0"})
    assert bad.status_code == 403
    bad = anonymous_client.post("/webhooks/paystack", content=b"{}", headers={"x-paystack-signature": "0"})
    assert bad.status_code == 403


# -- each vendor sees only their own data --------------------------------------------------------------


@pytest.fixture
def two_shops(env: Env, client: TestClient, anonymous_client: TestClient) -> dict[str, Any]:
    """Ada (signed in as `client`) has a finished sale. Bola signs up with an empty shop."""
    chat = new_chat(env, simulator=True, name="Funke")
    sell_loafers(env, chat)
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None
        order_id = order.id
    bola = signup(anonymous_client).json()["sessionToken"]
    return {"chat": chat, "order": order_id, "bola": bearer(bola)}


def test_a_new_vendor_sees_none_of_another_vendors_data(client: TestClient, two_shops: dict[str, Any]) -> None:
    bola = two_shops["bola"]

    assert client.get("/conversations").json()["conversations"] != []  # Ada does see hers
    assert client.get("/conversations", headers=bola).json()["conversations"] == []
    assert client.get("/orders", headers=bola).json()["orders"] == []
    assert client.get("/products", headers=bola).json()["products"] == []
    assert client.get("/products").json()["products"] != []


def test_another_vendors_ids_look_like_they_do_not_exist(client: TestClient, two_shops: dict[str, Any]) -> None:
    bola, chat, order = two_shops["bola"], two_shops["chat"], two_shops["order"]

    assert client.get(f"/conversations/{chat}/messages", headers=bola).status_code == 404
    assert client.post(f"/conversations/{chat}/pause", headers=bola).status_code == 404
    assert client.post(f"/conversations/{chat}/resume", headers=bola).status_code == 404
    assert client.post(f"/conversations/{chat}/messages", json={"body": "hello"}, headers=bola).status_code == 404
    assert client.post(f"/orders/{order}/mark-paid", headers=bola).status_code == 404


def test_another_vendor_cannot_change_anything(env: Env, client: TestClient, two_shops: dict[str, Any]) -> None:
    bola, chat = two_shops["bola"], two_shops["chat"]
    client.post(f"/conversations/{chat}/pause", headers=bola)
    client.post(f"/conversations/{chat}/messages", json={"body": "hello"}, headers=bola)

    listing = client.get(f"/conversations/{chat}/messages").json()
    assert listing["conversation"]["status"] == "AI_ACTIVE"
    assert all(message["sender"] != "VENDOR" for message in listing["messages"])


def test_signing_in_as_the_seeded_vendor_works_once_claimed(env: Env, anonymous_client: TestClient) -> None:
    with env.session() as session:
        ada = session.scalar(select(Vendor))
        assert ada is not None
        sign_in_vendor(session, ada)

    response = anonymous_client.post("/auth/login", json={"email": VENDOR_EMAIL, "password": VENDOR_PASSWORD})

    assert response.status_code == 200 and response.json()["vendor"]["name"] == "Ada's Footwear"


# -- claiming a vendor that has no login yet -----------------------------------------------------------


def test_an_existing_vendor_can_be_given_a_login(env: Env, anonymous_client: TestClient) -> None:
    from app.claim_vendor import claim

    with env.session() as session:
        claim(session, "Ada's Footwear", " Ada@Example.com ", "a good long password")

    response = anonymous_client.post("/auth/login", json={"email": "ada@example.com", "password": "a good long password"})
    assert response.status_code == 200


def test_claiming_refuses_bad_input_and_never_takes_over_an_account(env: Env) -> None:
    from app.claim_vendor import claim

    with env.session() as session:
        with pytest.raises(ValueError, match="No vendor"):
            claim(session, "Nobody", "x@example.com", "a good long password")
        with pytest.raises(ValueError, match="valid email"):
            claim(session, "Ada's Footwear", "nope", "a good long password")
        with pytest.raises(ValueError, match="password"):
            claim(session, "Ada's Footwear", "ada@example.com", "short")
        claim(session, "Ada's Footwear", "ada@example.com", "a good long password")
        with pytest.raises(ValueError, match="already has a login"):
            claim(session, "Ada's Footwear", "other@example.com", "a different long password")


def test_replacing_a_login_changes_the_details_and_signs_out_every_session(env: Env, anonymous_client: TestClient) -> None:
    from app.claim_vendor import claim

    with env.session() as session:
        claim(session, "Ada's Footwear", "ada@example.com", "a good long password")

    first = anonymous_client.post("/auth/login", json={"email": "ada@example.com", "password": "a good long password"})
    assert first.status_code == 200
    old_token = first.json()["sessionToken"]

    with env.session() as session:
        claim(session, "Ada's Footwear", "demo@example.com", "a demo passphrase", replace=True)
        # The vendor may keep its own address and only change the password.
        claim(session, "Ada's Footwear", "demo@example.com", "a newer passphrase", replace=True)

    assert anonymous_client.get("/auth/me", headers=bearer(old_token)).status_code == 401
    assert anonymous_client.post("/auth/login", json={"email": "ada@example.com", "password": "a good long password"}).status_code == 401
    response = anonymous_client.post("/auth/login", json={"email": "demo@example.com", "password": "a newer passphrase"})
    assert response.status_code == 200 and response.json()["vendor"]["name"] == "Ada's Footwear"


def test_replacing_never_takes_another_vendors_email(env: Env, anonymous_client: TestClient) -> None:
    from app.claim_vendor import claim

    assert signup(anonymous_client, email="bola@example.com").status_code == 201
    with env.session() as session:
        claim(session, "Ada's Footwear", "ada@example.com", "a good long password")
        with pytest.raises(ValueError, match="already used by another vendor"):
            claim(session, "Ada's Footwear", "bola@example.com", "a good long password", replace=True)
