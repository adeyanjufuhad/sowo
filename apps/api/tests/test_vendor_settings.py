"""A vendor sets up their own shop through the dashboard API: WhatsApp number, alert phone, how buyers pay."""

from conftest import Env
from fastapi.testclient import TestClient
from helpers import VENDOR_PHONE, WHATSAPP_NUMBER_ID, ScriptedModel, say, sign_in_vendor
from scenarios import say_to_sowo
from sqlalchemy import select
from test_multi_vendor import BOLA_NUMBER_ID, add_bola, chat_with

from app.models import Vendor

BANK = {"bankName": "GTBank", "bankAccountName": "Ada Okafor", "bankAccountNumber": "0123 456 789"}


def test_settings_need_a_signed_in_vendor(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/vendor/settings").status_code == 401
    assert anonymous_client.patch("/vendor/settings", json={"ownerName": "x"}).status_code == 401


def test_a_vendor_reads_their_own_setup(client: TestClient) -> None:
    body = client.get("/vendor/settings").json()

    assert body == {
        "businessName": "Ada's Footwear",
        "ownerName": "Ada",
        "whatsappPhoneNumberId": WHATSAPP_NUMBER_ID,
        "alertPhone": VENDOR_PHONE,
        "paymentMode": "paystack",
        "bankName": None,
        "bankAccountName": None,
        "bankAccountNumber": None,
        "paymentReady": True,
        "whatsappConnected": True,
    }


def test_a_new_vendor_starts_unconnected(env: Env, anonymous_client: TestClient) -> None:
    signup = anonymous_client.post(
        "/auth/signup", json={"email": "new@example.com", "password": "a long enough password", "businessName": "New Shop"}
    )
    headers = {"Authorization": f"Bearer {signup.json()['sessionToken']}"}

    body = anonymous_client.get("/vendor/settings", headers=headers).json()

    assert body["whatsappConnected"] is False and body["whatsappPhoneNumberId"] is None
    assert body["paymentMode"] == "paystack" and body["paymentReady"] is True and body["ownerName"] is None


def test_changes_are_partial_and_normalised(client: TestClient) -> None:
    body = client.patch(
        "/vendor/settings",
        json={"alertPhone": "+234 809-111-2222", "whatsappPhoneNumberId": " 1555 000 333 ", "ownerName": "  Ada   O. "},
    ).json()

    assert body["alertPhone"] == "2348091112222"
    assert body["whatsappPhoneNumberId"] == "1555000333"
    assert body["ownerName"] == "Ada O."
    assert body["paymentMode"] == "paystack"  # untouched


def test_null_or_blank_clears_a_setting(client: TestClient) -> None:
    body = client.patch("/vendor/settings", json={"alertPhone": None, "ownerName": "   "}).json()

    assert body["alertPhone"] is None and body["ownerName"] is None
    assert body["whatsappPhoneNumberId"] == WHATSAPP_NUMBER_ID


def test_bank_transfer_needs_complete_bank_details(client: TestClient) -> None:
    refused = client.patch("/vendor/settings", json={"paymentMode": "manual"})
    assert refused.status_code == 400 and "bank" in refused.json()["error"]["message"].lower()
    assert client.get("/vendor/settings").json()["paymentMode"] == "paystack"  # nothing half-saved

    partial = client.patch("/vendor/settings", json={"paymentMode": "manual", "bankName": "GTBank"})
    assert partial.status_code == 400

    done = client.patch("/vendor/settings", json={"paymentMode": "manual", **BANK}).json()
    assert done["paymentMode"] == "manual" and done["paymentReady"] is True
    assert done["bankAccountNumber"] == "0123456789"


def test_the_bank_details_cannot_be_broken_while_in_bank_transfer_mode(client: TestClient) -> None:
    client.patch("/vendor/settings", json={"paymentMode": "manual", **BANK})

    assert client.patch("/vendor/settings", json={"bankAccountNumber": None}).status_code == 400
    assert client.patch("/vendor/settings", json={"bankAccountNumber": "12345"}).status_code == 400
    switched_back = client.patch("/vendor/settings", json={"paymentMode": "paystack", "bankAccountNumber": None})
    assert switched_back.status_code == 200 and switched_back.json()["paymentReady"] is True


def test_nonsense_values_are_refused(client: TestClient) -> None:
    for payload in (
        {"whatsappPhoneNumberId": "not-a-number"},
        {"whatsappPhoneNumberId": "123"},
        {"alertPhone": "call me"},
        {"bankAccountNumber": "12345"},
        {"ownerName": "x" * 81},
        {"bankName": "x" * 81},
        {"paymentMode": "cash"},
    ):
        assert client.patch("/vendor/settings", json=payload).status_code == 400, payload


def test_one_whatsapp_number_belongs_to_one_shop(env: Env, client: TestClient) -> None:
    add_bola(env)

    taken = client.patch("/vendor/settings", json={"whatsappPhoneNumberId": BOLA_NUMBER_ID})
    assert taken.status_code == 409
    assert client.get("/vendor/settings").json()["whatsappPhoneNumberId"] == WHATSAPP_NUMBER_ID

    again = client.patch("/vendor/settings", json={"whatsappPhoneNumberId": WHATSAPP_NUMBER_ID})  # saving your own is fine
    assert again.status_code == 200


def test_a_vendor_can_only_change_their_own_shop(env: Env, client: TestClient) -> None:
    bola_id = add_bola(env)
    with env.session() as session:
        bola = session.get(Vendor, bola_id)
        assert bola is not None
        token = sign_in_vendor(session, bola, email="bola@example.com")

    changed = client.patch(
        "/vendor/settings", json={"ownerName": "Bola O."}, headers={"Authorization": f"Bearer {token}"}
    )

    assert changed.json()["businessName"] == "Bola's Bags" and changed.json()["ownerName"] == "Bola O."
    assert client.get("/vendor/settings").json()["ownerName"] == "Ada"  # Ada's own is untouched


def test_changes_take_effect_on_the_next_message(env: Env, client: TestClient) -> None:
    with env.session() as session:
        ada = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
        assert ada is not None
        ada_id = ada.id
    first = ScriptedModel(say("Hi"))
    say_to_sowo(env, chat_with(env, ada_id, "sim-1"), "hi", first)
    assert "report_payment_sent" not in [t["function"]["name"] for t in first.requests[0]["tools"]]

    client.patch("/vendor/settings", json={"paymentMode": "manual", "ownerName": "Mama Ada", **BANK})

    second = ScriptedModel(say("Hi"))
    say_to_sowo(env, chat_with(env, ada_id, "sim-2"), "hi", second)
    assert "report_payment_sent" in [t["function"]["name"] for t in second.requests[0]["tools"]]
    assert "buyers for the owner, Mama Ada." in second.requests[0]["messages"][0]["content"]


def test_the_bank_account_never_reaches_the_model_before_the_buyer_pays(env: Env, client: TestClient) -> None:
    client.patch("/vendor/settings", json={"paymentMode": "manual", **BANK})
    with env.session() as session:
        ada = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
        assert ada is not None
        ada_id = ada.id
    model = ScriptedModel(say("Hi"))

    say_to_sowo(env, chat_with(env, ada_id), "hi", model)

    assert "0123456789" not in model.everything_sent and "GTBank" not in model.everything_sent
