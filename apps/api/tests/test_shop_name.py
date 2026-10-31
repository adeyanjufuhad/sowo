"""A shop renames itself, and the /try simulator shows the shop it really sells for, by its current name."""

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import ScriptedModel, say, use_model
from test_catalog_management import bola_headers

from app.config import get_settings


def rename(client: TestClient, name: object) -> object:
    return client.patch("/vendor/settings", json={"businessName": name})


def test_a_vendor_renames_their_shop(client: TestClient) -> None:
    response = rename(client, "  Ada's   Shoe Palace ")
    assert response.status_code == 200, response.text
    assert response.json()["businessName"] == "Ada's Shoe Palace"
    assert client.get("/vendor/settings").json()["businessName"] == "Ada's Shoe Palace"
    assert client.get("/auth/me").json()["vendor"]["name"] == "Ada's Shoe Palace"  # the dashboard header


def test_a_shop_name_cannot_be_blank_too_long_or_someone_elses(env: Env, client: TestClient) -> None:
    bola_headers(env)  # adds Bola's shop
    assert rename(client, "   ").status_code == 400
    assert rename(client, None).status_code == 400
    assert rename(client, "x" * 121).status_code == 400
    assert rename(client, "Bola's Bags").status_code == 409
    assert client.get("/vendor/settings").json()["businessName"] == "Ada's Footwear"


def test_leaving_the_name_out_leaves_it_alone(client: TestClient) -> None:
    assert client.patch("/vendor/settings", json={"ownerName": "Ada"}).json()["businessName"] == "Ada's Footwear"


def test_the_simulator_names_the_demo_shop_and_its_owner(client: TestClient, anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/simulator/shop").json() == {"businessName": "Ada's Footwear", "ownerName": "Ada"}

    client.patch("/vendor/settings", json={"ownerName": ""})
    # With no owner's name, buyers hear the business name, and so does the simulator.
    assert anonymous_client.get("/simulator/shop").json()["ownerName"] == "Ada's Footwear"


def test_renaming_the_demo_shop_keeps_try_working(client: TestClient, anonymous_client: TestClient) -> None:
    anonymous_client.get("/simulator/shop")  # the demo finds the shop by SIMULATOR_VENDOR_NAME and remembers it
    assert rename(client, "Adeyanju's Store").status_code == 200

    assert anonymous_client.get("/simulator/shop").json()["businessName"] == "Adeyanju's Store"
    use_model(ScriptedModel(say("Welcome!")))
    reply = anonymous_client.post("/simulator/messages", json={"body": "Hello"})
    assert reply.status_code == 200, reply.text


def test_taking_the_old_name_does_not_take_over_the_demo(env: Env, client: TestClient, anonymous_client: TestClient) -> None:
    anonymous_client.get("/simulator/shop")
    rename(client, "Adeyanju's Store")
    signup = anonymous_client.post(
        "/auth/signup", json={"email": "copycat@example.com", "password": "a long password 123", "businessName": "Ada's Footwear"}
    )
    assert signup.status_code == 201, signup.text

    assert anonymous_client.get("/simulator/shop").json()["businessName"] == "Adeyanju's Store"


def test_pointing_the_setting_at_another_shop_moves_the_demo(
    env: Env, client: TestClient, anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    anonymous_client.get("/simulator/shop")
    bola_headers(env)
    monkeypatch.setenv("SIMULATOR_VENDOR_NAME", "Bola's Bags")
    get_settings.cache_clear()

    assert anonymous_client.get("/simulator/shop").json()["businessName"] == "Bola's Bags"


def test_the_shop_endpoint_is_off_with_the_simulator(anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_ENABLED", "false")
    get_settings.cache_clear()
    assert anonymous_client.get("/simulator/shop").status_code == 404
