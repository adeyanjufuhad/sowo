"""A vendor manages their own catalog: products and delivery zones."""

from typing import Any

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import LOAFERS_FLOOR_KOBO, ScriptedModel, call, last_tool_result, say, sign_in_vendor
from scenarios import new_chat, say_to_sowo, sell_loafers
from sqlalchemy import select
from test_multi_vendor import add_bola, chat_with

from app.models import Product, Vendor
from app.services.orders import get_quote

TOTE = {
    "sku": "tote-01",
    "name": "Leather Tote",
    "description": "A roomy bag for work",
    "size": "Large",
    "colour": "Tan",
    "basePriceKobo": 3_000_000,
    "floorPriceKobo": 2_600_000,
    "stockOnHand": 4,
}


def make_product(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/products", json={**TOTE, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["product"]


def bola_headers(env: Env) -> dict[str, str]:
    bola_id = add_bola(env)
    with env.session() as session:
        bola = session.get(Vendor, bola_id)
        assert bola is not None
        return {"Authorization": f"Bearer {sign_in_vendor(session, bola, email='bola@example.com')}"}


def ada_id(env: Env) -> str:
    with env.session() as session:
        ada = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
        assert ada is not None
        return ada.id


# -- who can do what ------------------------------------------------------------------------------------


def test_every_catalog_route_needs_a_signed_in_vendor(anonymous_client: TestClient) -> None:
    for method, path in [
        ("post", "/products"),
        ("patch", "/products/x"),
        ("delete", "/products/x"),
        ("get", "/delivery-zones"),
        ("post", "/delivery-zones"),
        ("patch", "/delivery-zones/x"),
        ("delete", "/delivery-zones/x"),
    ]:
        assert getattr(anonymous_client, method)(path).status_code == 401, (method, path)


def test_another_vendors_products_and_zones_look_like_they_do_not_exist(env: Env, client: TestClient) -> None:
    headers = bola_headers(env)
    bola_product = client.post("/products", json=TOTE, headers=headers).json()["product"]
    bola_zone = client.post("/delivery-zones", json={"area": "Abeokuta", "feeKobo": 100_000}, headers=headers).json()["zone"]

    assert client.patch(f"/products/{bola_product['id']}", json={"name": "Mine now"}).status_code == 404
    assert client.delete(f"/products/{bola_product['id']}").status_code == 404
    assert client.patch(f"/delivery-zones/{bola_zone['id']}", json={"feeKobo": 0}).status_code == 404
    assert client.delete(f"/delivery-zones/{bola_zone['id']}").status_code == 404
    assert client.get("/delivery-zones").json()["zones"] != [bola_zone]
    still = client.get("/products", headers=headers).json()["products"]
    assert [p["name"] for p in still if p["sku"] == "TOTE-01"] == ["Leather Tote"]


# -- products -------------------------------------------------------------------------------------------


def test_a_vendor_adds_a_product(client: TestClient) -> None:
    product = make_product(client)

    assert product["sku"] == "TOTE-01"  # skus are stored upper-case, which is how the assistant looks them up
    assert product["floorPriceKobo"] == 2_600_000 and product["stockOnHand"] == 4
    listed = [p for p in client.get("/products").json()["products"] if p["id"] == product["id"]]
    assert listed == [product]
    assert listed[0]["description"] == "A roomy bag for work" and listed[0]["colour"] == "Tan"


def test_a_new_product_can_be_sold_by_the_assistant_and_its_floor_stays_private(env: Env, client: TestClient) -> None:
    make_product(client, name="Leather Tote Bag", floorPriceKobo=2_611_111)
    model = ScriptedModel(
        call("search_catalog", query="tote bag"),
        call("evaluate_offer", sku="TOTE-01", offer_naira=26_000),
        lambda messages: say(f"The tote bag is {last_tool_result(messages, 'search_catalog')['results'][0]['price']}."),
    )

    reply = say_to_sowo(env, new_chat(env), "do you have a tote bag? I can pay 26k", model)

    assert reply is not None and reply.text == "The tote bag is ₦30,000."
    assert "2611111" not in model.everything_sent and "26,111" not in model.everything_sent


@pytest.mark.parametrize(
    "overrides",
    [
        {"sku": ""},
        {"sku": "has space"},
        {"sku": "x" * 65},
        {"name": "   "},
        {"name": "n" * 201},
        {"basePriceKobo": 0},
        {"basePriceKobo": -5},
        {"floorPriceKobo": 0},
        {"floorPriceKobo": 3_000_001},  # the floor can't be above the price
        {"stockOnHand": -1},
        {"stockOnHand": 1_000_001},
        {"basePriceKobo": 30_000.5},  # money is whole kobo
        {"basePriceKobo": "3000000"},
        {"imageUrl": "javascript:alert(1)"},
        {"imageUrl": "ftp://example.com/a.png"},
        {"description": "d" * 2001},
    ],
)
def test_bad_products_are_refused(client: TestClient, overrides: dict[str, Any]) -> None:
    before = client.get("/products").json()
    assert client.post("/products", json={**TOTE, **overrides}).status_code == 400
    assert client.get("/products").json() == before


def test_images_must_be_web_addresses(client: TestClient) -> None:
    product = make_product(client, imageUrl="https://cdn.example.com/tote.jpg")
    assert product["imageUrl"] == "https://cdn.example.com/tote.jpg"


def test_a_sku_is_unique_within_one_catalog_only(env: Env, client: TestClient) -> None:
    make_product(client)
    assert client.post("/products", json=TOTE).status_code == 409
    assert client.post("/products", json={**TOTE, "sku": "Tote-01"}).status_code == 409  # case doesn't matter
    assert client.post("/products", json=TOTE, headers=bola_headers(env)).status_code == 201  # another shop may


def test_a_vendor_edits_a_product(client: TestClient) -> None:
    product = make_product(client)

    changed = client.patch(
        f"/products/{product['id']}",
        json={"basePriceKobo": 3_200_000, "stockOnHand": 0, "size": None, "name": "  Big   Tote "},
    ).json()["product"]

    assert changed["basePriceKobo"] == 3_200_000 and changed["stockOnHand"] == 0
    assert changed["size"] is None and changed["name"] == "Big Tote"
    assert changed["floorPriceKobo"] == 2_600_000 and changed["colour"] == "Tan"  # untouched


def test_an_edit_that_would_put_the_floor_above_the_price_changes_nothing(client: TestClient) -> None:
    product = make_product(client)

    refused = client.patch(f"/products/{product['id']}", json={"basePriceKobo": 2_000_000})

    assert refused.status_code == 400
    assert [p for p in client.get("/products").json()["products"] if p["id"] == product["id"]] == [product]
    assert client.patch(f"/products/{product['id']}", json={"basePriceKobo": 2_000_000, "floorPriceKobo": 1_800_000}).status_code == 200


def test_renaming_a_sku_to_one_in_use_is_refused(client: TestClient) -> None:
    first = make_product(client)
    make_product(client, sku="TOTE-02")

    assert client.patch(f"/products/{first['id']}", json={"sku": "tote-02"}).status_code == 409
    assert client.patch(f"/products/{first['id']}", json={"sku": "tote-01"}).status_code == 200  # its own is fine
    assert client.patch(f"/products/{first['id']}", json={"sku": "TOTE-03"}).json()["product"]["sku"] == "TOTE-03"


def test_changed_prices_and_stock_reach_the_assistant_at_once(env: Env, client: TestClient) -> None:
    product = make_product(client)
    client.patch(f"/products/{product['id']}", json={"basePriceKobo": 3_500_000, "stockOnHand": 2})
    model = ScriptedModel(
        call("search_catalog", query="tote"),
        lambda messages: say(str(last_tool_result(messages, "search_catalog")["results"])),
    )

    reply = say_to_sowo(env, new_chat(env), "tote?", model)

    assert reply is not None and "₦35,000" in reply.text and "'in_stock': 2" in reply.text


def test_an_untouched_product_is_deleted_for_good(env: Env, client: TestClient) -> None:
    product = make_product(client)

    response = client.delete(f"/products/{product['id']}")

    assert response.json() == {"deleted": True, "archived": False}
    assert client.delete(f"/products/{product['id']}").status_code == 404
    with env.session() as session:
        assert session.get(Product, product["id"]) is None
    make_product(client)  # the sku is free again


def test_a_product_with_history_is_archived_not_deleted(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env))  # haggles over the loafers and creates an order for them
    with env.session() as session:
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None
        loafers_id = loafers.id
    orders_before = client.get("/orders").json()

    response = client.delete(f"/products/{loafers_id}")

    assert response.json() == {"deleted": False, "archived": True}
    assert "LOAF-BLK-43" not in [p["sku"] for p in client.get("/products").json()["products"]]
    assert client.patch(f"/products/{loafers_id}", json={"name": "x"}).status_code == 404
    assert client.get("/orders").json() == orders_before  # the order still names the loafers
    assert client.post("/products", json={**TOTE, "sku": "LOAF-BLK-43"}).status_code == 409  # the sku stays reserved


def test_an_archived_product_is_no_longer_sold(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env))
    with env.session() as session:
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None
        loafers_id = loafers.id
    client.delete(f"/products/{loafers_id}")

    model = ScriptedModel(
        call("search_catalog", query="black loafers"),
        call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=41_000),
        lambda messages: say(
            f"{last_tool_result(messages, 'search_catalog')['results']} / {last_tool_result(messages, 'evaluate_offer')}"
        ),
    )
    chat = chat_with(env, ada_id(env), "sim-later")
    reply = say_to_sowo(env, chat, "black loafers for 41k", model)
    assert reply is not None and "no product with sku" in reply.text
    assert "LOAF-BLK-43" not in reply.text.split(" / ")[0]  # the search no longer lists it

    with env.session() as session:
        quote = get_quote(session, chat, [{"product_id": loafers_id, "qty": 1}], "Ikeja")
        assert quote["error"]["code"] == "NOT_FOUND"


def test_the_floor_price_never_appears_in_what_the_assistant_reads(env: Env, client: TestClient) -> None:
    make_product(client, floorPriceKobo=2_777_777)
    model = ScriptedModel(call("search_catalog", query="tote"), say("We have it."))

    say_to_sowo(env, new_chat(env), "tote?", model)

    assert "2777777" not in model.everything_sent and str(LOAFERS_FLOOR_KOBO) not in model.everything_sent


# -- delivery zones -------------------------------------------------------------------------------------


def test_a_vendor_manages_their_delivery_zones(client: TestClient) -> None:
    zone = client.post("/delivery-zones", json={"area": "  Ibadan  ", "feeKobo": 400_000}).json()["zone"]
    assert zone["area"] == "Ibadan" and zone["feeKobo"] == 400_000
    assert zone in client.get("/delivery-zones").json()["zones"]

    changed = client.patch(f"/delivery-zones/{zone['id']}", json={"feeKobo": 0, "area": "Ibadan North"}).json()["zone"]
    assert changed == {"id": zone["id"], "area": "Ibadan North", "feeKobo": 0}  # free delivery is allowed

    assert client.delete(f"/delivery-zones/{zone['id']}").status_code == 204
    assert zone["id"] not in [z["id"] for z in client.get("/delivery-zones").json()["zones"]]
    assert client.delete(f"/delivery-zones/{zone['id']}").status_code == 404


def test_the_listing_is_sorted_and_only_ours(client: TestClient) -> None:
    areas = [z["area"] for z in client.get("/delivery-zones").json()["zones"]]
    assert areas == sorted(areas) and "Ikeja" in areas


@pytest.mark.parametrize(
    "payload",
    [
        {"area": "", "feeKobo": 100},
        {"area": "   ", "feeKobo": 100},
        {"area": "a" * 101, "feeKobo": 100},
        {"area": "Ibadan", "feeKobo": -1},
        {"area": "Ibadan", "feeKobo": 50_000_001},
        {"area": "Ibadan", "feeKobo": 1.5},
        {"area": "Ibadan"},
    ],
)
def test_bad_zones_are_refused(client: TestClient, payload: dict[str, Any]) -> None:
    before = client.get("/delivery-zones").json()
    assert client.post("/delivery-zones", json=payload).status_code == 400
    assert client.get("/delivery-zones").json() == before


def test_an_area_cannot_be_added_twice(env: Env, client: TestClient) -> None:
    assert client.post("/delivery-zones", json={"area": "ikeja", "feeKobo": 1}).status_code == 409  # Ada has Ikeja
    other = client.post("/delivery-zones", json={"area": "Mushin", "feeKobo": 1}).json()["zone"]
    assert client.patch(f"/delivery-zones/{other['id']}", json={"area": "YABA"}).status_code == 409
    assert client.post("/delivery-zones", json={"area": "Ikeja", "feeKobo": 1}, headers=bola_headers(env)).status_code == 201


def test_a_new_zone_is_delivered_to_and_a_removed_one_is_not(env: Env, client: TestClient) -> None:
    client.post("/delivery-zones", json={"area": "Mushin", "feeKobo": 180_000})
    ikeja = next(z for z in client.get("/delivery-zones").json()["zones"] if z["area"] == "Ikeja")
    client.delete(f"/delivery-zones/{ikeja['id']}")
    chat = new_chat(env)

    model = ScriptedModel(say("Hi"))
    say_to_sowo(env, chat, "hi", model)
    system = model.requests[0]["messages"][0]["content"]
    assert "Mushin" in system and "Ikeja" not in system

    with env.session() as session:
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None
        item = [{"product_id": loafers.id, "qty": 1}]
        assert get_quote(session, chat, item, "mushin")["deliveryFeeKobo"] == 180_000
        assert get_quote(session, chat, item, "Ikeja")["error"]["code"] == "UNKNOWN_DELIVERY_AREA"


def test_removing_a_zone_does_not_disturb_orders_already_placed(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env))
    orders_before = client.get("/orders").json()
    ikeja = next(z for z in client.get("/delivery-zones").json()["zones"] if z["area"] == "Ikeja")

    assert client.delete(f"/delivery-zones/{ikeja['id']}").status_code == 204
    assert client.get("/orders").json() == orders_before
