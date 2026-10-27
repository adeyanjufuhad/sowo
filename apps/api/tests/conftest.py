"""Shared setup: a throwaway database, fixed settings, and recorders in place of WhatsApp and Paystack."""

import json
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from fastapi.testclient import TestClient
from helpers import (
    APP_SECRET,
    BUYER_PHONE,
    LOAFERS_FLOOR_KOBO,
    PAYSTACK_SECRET,
    VENDOR_PHONE,
    VERIFY_TOKEN,
    sign_in_vendor,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import app.db as database
from app.config import Settings, get_settings
from app.main import app
from app.models import Conversation, Product, Vendor
from app.seed import seed_data
from app.services import paystack, whatsapp


@dataclass
class Env:
    sessions: sessionmaker[Session]
    graph: list[dict[str, Any]] = field(default_factory=list)  # every call made to Meta's Graph API
    paystack_calls: list[dict[str, Any]] = field(default_factory=list)
    paystack_status: int = 200

    def session(self) -> Session:
        return self.sessions()

    def texts_to(self, phone: str) -> list[str]:
        """Messages sent over WhatsApp to `phone`, oldest first."""
        return [
            call["json"]["text"]["body"]
            for call in self.graph
            if call["json"].get("to") == phone and call["json"].get("type") == "text"
        ]

    def conversation(self, phone: str = BUYER_PHONE) -> Conversation:
        with self.session() as session:
            found = session.scalar(select(Conversation).where(Conversation.customer_phone == phone))
            assert found is not None
            return found


def _record(into: list[dict[str, Any]], respond: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        into.append({"url": str(request.url), "headers": dict(request.headers), "json": body})
        return respond(request)

    return httpx.MockTransport(handler)


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An empty database migrated to the latest schema, built once; each test starts from a copy."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    engine = database.create_database_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        command.upgrade(database.alembic_config(connection), "head")
    engine.dispose()
    return path


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, migrated_template: Path) -> Iterator[Env]:
    shutil.copy(migrated_template, tmp_path / "api.db")
    engine = database.create_database_engine(f"sqlite:///{tmp_path / 'api.db'}")
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    database.init_db()
    with sessions() as session:
        seed_data(session)
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None
        loafers.floor_price_kobo = LOAFERS_FLOOR_KOBO
        session.commit()

    # Never read a developer's real .env during tests.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name, value in {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'api.db'}",
        "WHATSAPP_VERIFY_TOKEN": VERIFY_TOKEN,
        "WHATSAPP_APP_SECRET": APP_SECRET,
        "WHATSAPP_ACCESS_TOKEN": "wa-access-token",
        "WHATSAPP_PHONE_NUMBER_ID": "1555000111",
        "WHATSAPP_ECHO_MODE": "false",
        "PAYSTACK_SECRET_KEY": PAYSTACK_SECRET,
        "VENDOR_ALERT_PHONE": VENDOR_PHONE,
        "REPLY_DELAY_SECONDS": "0",
        "SIMULATOR_ENABLED": "true",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()

    recorded = Env(sessions=sessions)
    monkeypatch.setattr(
        whatsapp,
        "_transport_override",
        _record(recorded.graph, lambda _: httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})),
    )

    def paystack_response(request: httpx.Request) -> httpx.Response:
        if recorded.paystack_status != 200:
            return httpx.Response(recorded.paystack_status, json={"status": False, "message": "nope"})
        reference = json.loads(request.content)["reference"]
        return httpx.Response(
            200,
            json={"status": True, "data": {"authorization_url": f"https://checkout.paystack.test/{reference}"}},
        )

    monkeypatch.setattr(paystack, "_transport_override", _record(recorded.paystack_calls, paystack_response))
    yield recorded
    get_settings.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client(env: Env) -> Iterator[TestClient]:
    """A client that is not signed in."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(env: Env) -> Iterator[TestClient]:
    """A client signed in as Ada, the vendor who owns the seeded shop."""
    with env.session() as session:
        ada = session.scalar(select(Vendor))
        assert ada is not None
        token = sign_in_vendor(session, ada)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
        yield test_client


@pytest.fixture
def manual(env: Env, monkeypatch: pytest.MonkeyPatch) -> Env:
    """Buyers pay by bank transfer to Ada's account; Ada confirms it in the dashboard."""
    for name, value in {
        "PAYMENT_MODE": "manual",
        "VENDOR_BANK_NAME": "GTBank",
        "VENDOR_ACCOUNT_NAME": "Ada Okafor",
        "VENDOR_ACCOUNT_NUMBER": "0123456789",
        "MANUAL_PAYMENT_HOLD_MINUTES": "180",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    return env


@pytest.fixture(autouse=True)
def cheap_password_hashing(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Argon2 is deliberately slow. Tests use the same algorithm with minimal cost so the suite stays quick."""
    from argon2 import PasswordHasher

    from app.services import auth

    monkeypatch.setattr(auth, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    auth._dummy_hash.cache_clear()
    yield
    auth._dummy_hash.cache_clear()
