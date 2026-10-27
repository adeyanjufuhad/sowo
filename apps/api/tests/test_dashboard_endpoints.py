from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import sign_in_vendor
from sqlalchemy.orm import sessionmaker

import app.db as database
from app.main import app
from app.models import (
    Conversation,
    Message,
    MessageRole,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Vendor,
)


@pytest.fixture
def dashboard_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, dict[str, str]]]:
    engine = database.create_database_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    database.init_db()

    with sessions() as session:
        vendor = Vendor(name="Dashboard Vendor")
        session.add(vendor)
        session.flush()
        product = Product(
            vendor_id=vendor.id,
            sku="LOAF-BLK-43",
            name="Black Leather Loafers, size 43",
            description="Leather loafers",
            size="43",
            colour="Black",
            price_kobo=4500000,
            floor_price_kobo=4000000,
            stock=3,
            image_url="",
        )
        buyer = Conversation(vendor_id=vendor.id, customer_phone="2348012345678", customer_name="Funke", is_simulator=False)
        simulator = Conversation(vendor_id=vendor.id, customer_phone="demo-buyer", customer_name="Demo buyer", is_simulator=True)
        session.add_all([product, buyer, simulator])
        session.flush()
        session.add_all(
            [
                Message(conversation_id=buyer.id, role=MessageRole.BUYER, text="I need size 43"),
                Message(
                    conversation_id=buyer.id,
                    role=MessageRole.AI,
                    text="We have it.",
                    tool_calls=[
                        {
                            "tool": "search_catalog",
                            "input": {"query": "size 43"},
                            "output": {"results": [{"productId": product.id, "priceKobo": 4500000}]},
                        }
                    ],
                ),
            ]
        )
        order = Order(
            conversation_id=buyer.id,
            status=OrderStatus.PENDING,
            paystack_reference="SW-DASHBOARD-1",
            delivery_fee_kobo=250000,
            total_kobo=4750000,
            delivery_area="Ikeja",
        )
        session.add(order)
        session.flush()
        session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=1, unit_price_kobo=4500000))
        session.commit()
        identifiers = {"buyer": buyer.id, "simulator": simulator.id, "product": product.id}
        token = sign_in_vendor(session, vendor)

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        yield client, identifiers


def test_list_conversations_uses_contract_shape(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.get("/conversations")

    assert response.status_code == 200
    conversation = next(item for item in response.json()["conversations"] if item["id"] == identifiers["buyer"])
    assert conversation == {
        "id": identifiers["buyer"],
        "customerName": "Funke",
        "platform": "WHATSAPP",
        "status": "AI_ACTIVE",
        "lastMessageAt": conversation["lastMessageAt"],
        "preview": "We have it.",
    }


def test_list_messages_includes_ai_tool_calls(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.get(f"/conversations/{identifiers['buyer']}/messages")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [message["sender"] for message in messages] == ["BUYER", "AI"]
    assert messages[1]["toolCalls"] == [
        {"tool": "search_catalog", "input": {"query": "size 43"}, "output": {"results": [{"productId": identifiers["product"], "priceKobo": 4500000}]}}
    ]


def test_missing_conversation_uses_contract_error_shape(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, _ = dashboard_client
    response = client.get("/conversations/missing/messages")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Conversation missing not found"}}


def test_pause_and_resume_change_state(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    paused = client.post(f"/conversations/{identifiers['buyer']}/pause")
    resumed = client.post(f"/conversations/{identifiers['buyer']}/resume")

    assert paused.status_code == 200
    assert paused.json()["conversation"]["status"] == "HUMAN_TAKEOVER"
    assert resumed.status_code == 200
    assert resumed.json()["conversation"]["status"] == "AI_ACTIVE"


def test_vendor_reply_pauses_and_stores_message(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.post(
        f"/conversations/{identifiers['simulator']}/messages", json={"body": "Ada here, I can help."}
    )

    assert response.status_code == 200
    assert response.json()["conversation"]["status"] == "HUMAN_TAKEOVER"
    assert response.json()["message"]["sender"] == "VENDOR"
    assert response.json()["message"]["body"] == "Ada here, I can help."


def test_vendor_reply_rejects_empty_body(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.post(f"/conversations/{identifiers['buyer']}/messages", json={"body": "   "})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_list_orders_matches_contract_fields(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.get("/orders")

    assert response.status_code == 200
    order = response.json()["orders"][0]
    assert order["customerName"] == "Funke"
    assert order["items"] == [
        {
            "productId": identifiers["product"],
            "sku": "LOAF-BLK-43",
            "name": "Black Leather Loafers, size 43",
            "quantity": 1,
            "unitPriceKobo": 4500000,
        }
    ]
    assert order["paymentStatus"] == "PENDING"
    assert order["fulfillmentStatus"] == "UNFULFILLED"


def test_list_products_includes_vendor_floor_price_only_here(dashboard_client: tuple[TestClient, dict[str, str]]) -> None:
    client, identifiers = dashboard_client
    response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == {
        "products": [
            {
                "id": identifiers["product"],
                "sku": "LOAF-BLK-43",
                "name": "Black Leather Loafers, size 43",
                "basePriceKobo": 4500000,
                "floorPriceKobo": 4000000,
                "stockOnHand": 3,
                "imageUrl": "",
                "description": "Leather loafers",
                "size": "43",
                "colour": "Black",
            }
        ]
    }
