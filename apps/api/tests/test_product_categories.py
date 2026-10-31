"""A vendor groups products into categories, so the assistant can answer "which shoes do you have?"."""

from typing import Any

from conftest import Env
from fastapi.testclient import TestClient
from helpers import ScriptedModel, call, last_tool_result, say
from scenarios import new_chat, say_to_sowo
from test_catalog_management import bola_headers, make_product


def test_a_vendor_sets_changes_and_clears_a_category(client: TestClient) -> None:
    product = make_product(client, category="  Bags ")
    assert product["category"] == "Bags"
    assert [p["category"] for p in client.get("/products").json()["products"] if p["id"] == product["id"]] == ["Bags"]

    changed = client.patch(f"/products/{product['id']}", json={"category": "Handbags"}).json()["product"]
    assert changed["category"] == "Handbags"
    cleared = client.patch(f"/products/{product['id']}", json={"category": None}).json()["product"]
    assert cleared["category"] is None
    assert client.patch(f"/products/{product['id']}", json={"category": "x" * 65}).status_code == 400


def test_searching_a_category_finds_everything_in_it(env: Env, client: TestClient) -> None:
    # Neither name says "purse": only the category connects them to the buyer's word.
    make_product(client, sku="clutch-1", name="Evening Clutch", category="Purses", description="")
    make_product(client, sku="pouch-1", name="Mini Pouch", category="Purses", description="")
    make_product(client, sku="beanie-1", name="Wool Beanie", category="Headwear", description="")

    seen: dict[str, Any] = {}

    def remember(messages: list[dict[str, Any]]) -> dict[str, Any]:
        seen.update(last_tool_result(messages, "search_catalog"))
        return say("We have a few.")

    model = ScriptedModel(call("search_catalog", query="purses"), remember)
    say_to_sowo(env, new_chat(env), "which purses una get?", model)

    found = {hit["name"]: hit["category"] for hit in seen["results"]}
    assert found == {"Evening Clutch": "Purses", "Mini Pouch": "Purses"}
    assert "floor" not in model.everything_sent.casefold()


def test_singular_and_plural_both_find_the_category(env: Env, client: TestClient) -> None:
    make_product(client, sku="beanie-1", name="Wool Hat", category="Beanie", description="")
    for query in ("beanie", "beanies"):
        model = ScriptedModel(call("search_catalog", query=query), say("ok"))
        say_to_sowo(env, new_chat(env, name=f"buyer-{query}"), f"{query}?", model)
        names = [hit["name"] for hit in last_tool_result(model.requests[-1]["messages"], "search_catalog")["results"]]
        assert names == ["Wool Hat"], query


def test_the_assistant_is_told_what_kinds_of_things_the_shop_sells(env: Env, client: TestClient) -> None:
    make_product(client, sku="tote-1", category="Bags")
    make_product(client, sku="tote-2", category="bags")  # same category, other capitals: listed once
    make_product(client, sku="cap-1", category="Hats")
    client.post("/products", json={"sku": "secret-1", "name": "Other shop's thing", "category": "Jewellery",
                                   "basePriceKobo": 100_000, "floorPriceKobo": 90_000}, headers=bola_headers(env))

    model = ScriptedModel(say("Hello!"))
    say_to_sowo(env, new_chat(env), "wetin you get?", model)
    prompt = model.requests[0]["messages"][0]["content"]

    assert "We sell: Bags, Hats." in prompt
    assert "Jewellery" not in prompt


def test_no_categories_means_no_category_line(env: Env) -> None:
    model = ScriptedModel(say("Hello!"))
    say_to_sowo(env, new_chat(env), "hi", model)
    assert "We sell:" not in model.requests[0]["messages"][0]["content"]
