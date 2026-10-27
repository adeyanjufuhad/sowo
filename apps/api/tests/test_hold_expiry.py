"""Holds are released on demand: nothing polls the database in the background (Neon must be able to sleep)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from scenarios import new_chat, sell_loafers
from sqlalchemy import select

import app.main as main_module
from app.db import create_database_engine
from app.models import Order, OrderStatus, StockHold


def test_the_app_starts_no_background_database_polling() -> None:
    assert not hasattr(main_module, "hold_expiry_worker")


def test_listing_orders_releases_overdue_holds(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env, simulator=True, name="Funke"))
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None
        order.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    listed = client.get("/orders").json()["orders"]

    assert listed[0]["paymentStatus"] == "FAILED"
    with env.session() as session:
        assert session.scalar(select(Order)).status == OrderStatus.EXPIRED  # type: ignore[union-attr]
        assert session.scalar(select(StockHold)) is None


def test_a_pooled_postgres_engine_is_built_for_pgbouncer_and_idle_suspend(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_connect(*args: Any, **kwargs: Any) -> None:
        seen.update(kwargs)
        raise RuntimeError("stop here; no server is needed")

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    engine = create_database_engine("postgresql://user:pw@ep-x-pooler.eu-west-2.aws.neon.tech/sowo?sslmode=require")

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.pool._pre_ping is True  # type: ignore[attr-defined]
    assert engine.pool._recycle == 300  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        engine.raw_connection()
    assert seen["prepare_threshold"] is None
    assert seen["sslmode"] == "require"
