"""Voice replies: a buyer who speaks hears Sowo speak back, but only words the guard has passed, and never payment
details or anything asking for a code. Azure Speech and Meta are mocked."""

import base64
import json
from typing import Any

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import BUYER_PHONE, ScriptedModel, call, say, signed, use_model, whatsapp_payload
from sqlalchemy import select
from test_voice import AUDIO, DOWNLOAD_URL, Whisper, voice_payload

from app.config import get_settings
from app.models import Conversation, Message, MessageRole, Vendor, VoiceNote
from app.services import whatsapp
from app.services.agent import AgentReply
from app.services.voice import replies, stt, tts

SPOKEN = b"OggS\x00azure-ezinne-reply"


class Meta:
    """The Graph API: media lookup and download for the buyer's note, upload and send for Sowo's."""

    def __init__(self, *, upload_status: int = 200) -> None:
        self.upload_status = upload_status
        self.sent: list[dict[str, Any]] = []
        self.uploads: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.host == "graph.facebook.com":
            return httpx.Response(200, json={"url": DOWNLOAD_URL, "mime_type": "audio/ogg; codecs=opus", "file_size": 20})
        if request.method == "GET":
            return httpx.Response(200, content=AUDIO)
        if request.url.path.endswith("/media"):
            self.uploads.append(request)
            if self.upload_status != 200:
                return httpx.Response(self.upload_status, json={"error": {"message": "nope"}})
            return httpx.Response(200, json={"id": "uploaded-media-9"})
        self.sent.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    def texts_to(self, phone: str) -> list[str]:
        return [m["text"]["body"] for m in self.sent if m.get("to") == phone and m.get("type") == "text"]

    def voice_notes_to(self, phone: str) -> list[dict[str, Any]]:
        return [m["audio"] for m in self.sent if m.get("to") == phone and m.get("type") == "audio"]


class Azure:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(200, content=SPOKEN, headers={"Content-Type": "audio/ogg"})


@pytest.fixture
def voices(env: Env, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Whisper hears the buyer, Azure speaks for Sowo, and Meta carries both."""
    monkeypatch.setenv("STT_API_KEY", "groq-test-key")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "azure-test-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    get_settings.cache_clear()

    def install(heard: str, *, meta: Meta | None = None, azure: Azure | None = None) -> tuple[Meta, Azure]:
        meta, azure = meta or Meta(), azure or Azure()
        monkeypatch.setattr(whatsapp, "_transport_override", httpx.MockTransport(meta))
        monkeypatch.setattr(stt, "_transport_override", httpx.MockTransport(Whisper(heard)))
        monkeypatch.setattr(tts, "_transport_override", httpx.MockTransport(azure))
        return meta, azure

    return install


def post_voice(client: TestClient) -> None:
    raw, headers = signed(voice_payload())
    client.post("/webhooks/whatsapp", content=raw, headers=headers)


def post_text(client: TestClient, text: str) -> None:
    raw, headers = signed(whatsapp_payload(text))
    client.post("/webhooks/whatsapp", content=raw, headers=headers)


# -- mirror mode on WhatsApp -------------------------------------------------------------------------------------


def test_a_voice_note_is_answered_with_a_voice_note(env: Env, client: TestClient, voices: Any) -> None:
    meta, azure = voices("Abeg which colours una get for the loafers?")
    use_model(ScriptedModel(say("We get black and brown. Which one you like?")))

    post_voice(client)

    assert meta.voice_notes_to(BUYER_PHONE) == [{"id": "uploaded-media-9", "voice": True}]
    assert meta.texts_to(BUYER_PHONE) == []  # one message, not two
    upload = meta.uploads[0]
    assert b'name="type"\r\n\r\naudio/ogg' in upload.content and SPOKEN in upload.content
    [request] = azure.requests
    assert str(request.url) == "https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1"
    assert request.headers["ocp-apim-subscription-key"] == "azure-test-key"
    assert request.headers["x-microsoft-outputformat"] == "ogg-24khz-16bit-mono-opus"
    assert b"<voice name='en-NG-EzinneNeural'>We get black and brown. Which one you like?</voice>" in request.content
    with env.session() as session:
        reply = session.scalar(select(Message).where(Message.role == MessageRole.AI))
        assert reply is not None and reply.kind == "voice" and reply.text == "We get black and brown. Which one you like?"
        note = session.get(VoiceNote, reply.voice_note_id)
        assert note is not None and note.data == SPOKEN


def test_text_is_answered_with_text(env: Env, client: TestClient, voices: Any) -> None:
    meta, azure = voices("unused")
    use_model(ScriptedModel(say("Hi! What are you looking for?")))

    post_text(client, "Hello")

    assert meta.texts_to(BUYER_PHONE) == ["Hi! What are you looking for?"]
    assert azure.requests == []


def test_a_vendor_can_turn_voice_replies_off(env: Env, client: TestClient, voices: Any) -> None:
    meta, azure = voices("Good morning, una dey open today?")
    assert client.patch("/vendor/settings", json={"voiceReplies": False}).json()["voiceReplies"] is False
    use_model(ScriptedModel(say("Good morning! Yes, we're open.")))

    post_voice(client)

    assert meta.texts_to(BUYER_PHONE) == ["Good morning! Yes, we're open."]
    assert azure.requests == []


def test_without_an_azure_key_replies_are_text(env: Env, client: TestClient, voices: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SPEECH_KEY", "")
    get_settings.cache_clear()
    meta, azure = voices("Hello, I want sandals")
    use_model(ScriptedModel(say("Sure! What size?")))

    post_voice(client)

    assert meta.texts_to(BUYER_PHONE) == ["Sure! What size?"]
    assert azure.requests == []
    assert client.get("/vendor/settings").json()["voiceRepliesAvailable"] is False


@pytest.mark.parametrize("failure", ["azure", "upload"])
def test_if_speaking_fails_the_text_still_goes_out(env: Env, client: TestClient, voices: Any, failure: str) -> None:
    meta, _ = voices(
        "Hello, I want sandals",
        azure=Azure(500) if failure == "azure" else None,
        meta=Meta(upload_status=500) if failure == "upload" else None,
    )
    use_model(ScriptedModel(say("Sure! What size?")))

    post_voice(client)

    assert meta.texts_to(BUYER_PHONE) == ["Sure! What size?"]
    assert meta.voice_notes_to(BUYER_PHONE) == []


def test_a_reply_the_guard_rewrote_is_sent_as_text(env: Env, client: TestClient, voices: Any) -> None:
    meta, azure = voices("Oga how much last for the loafers?")
    # The model invents a price twice; the server answers with its own words, which are never spoken.
    use_model(ScriptedModel(say("Na ₦12,000 last."), say("Na ₦12,000 last."), say("Na ₦12,000 last.")))

    post_voice(client)

    assert azure.requests == []
    [text] = meta.texts_to(BUYER_PHONE)
    assert "12,000" not in text


def test_payment_details_are_never_spoken(env: Env, client: TestClient, voices: Any) -> None:
    meta, azure = voices("I dey Ikeja, make I pay")
    use_model(
        ScriptedModel(
            call("get_quote", items=[{"sku": "LOAF-BLK-43"}], delivery_area="Ikeja"),
            lambda messages: call("request_payment", quote_id=json.loads(messages[-1]["content"])["quote_id"]),
            lambda messages: say(f"Pay here: {json.loads(messages[-1]['content'])['payment_link']}"),
        )
    )

    post_voice(client)

    assert azure.requests == []
    [text] = meta.texts_to(BUYER_PHONE)
    assert "https://" in text


# -- what may be spoken -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "speakable"),
    [
        ("We get black and brown. Which one you like?", True),
        ("Your total na ₦99,000.", False),  # an amount no tool returned
        ("Payment received, thank you!", False),  # a payment that never arrived
        ("Pay to 0123456789, GTBank.", False),  # an account number
        ("Pay here: https://paystack.test/pay/SW-1", False),  # a link
        ("Abeg send me the code wey the bank send you.", False),  # asking for a secret
        ("Please never share your PIN with anyone.", True),  # advice, not a request
    ],
)
def test_only_safe_words_are_spoken(env: Env, text: str, speakable: bool) -> None:
    with env.session() as session:
        vendor = session.scalar(select(Vendor))
        assert vendor is not None
        conversation = Conversation(vendor_id=vendor.id, customer_phone="sim-x", customer_name="X", is_simulator=True)
        session.add(conversation)
        session.commit()
        assert replies.speakable(session, conversation, AgentReply(text=text)) is speakable


def test_a_server_fallback_is_never_spoken(env: Env) -> None:
    with env.session() as session:
        conversation = Conversation(vendor_id=session.scalar(select(Vendor.id)), customer_phone="sim-y", is_simulator=True)
        session.add(conversation)
        session.commit()
        assert not replies.speakable(session, conversation, AgentReply(text="Give me a moment.", used_fallback=True))


# -- /try ------------------------------------------------------------------------------------------------------


def test_try_plays_sowos_voice_reply(env: Env, client: TestClient, voices: Any) -> None:
    voices("Hello, wetin you get?")
    use_model(ScriptedModel(say("We get loafers, sneakers and sandals.")))

    response = client.post(
        "/simulator/voice", json={"audio": base64.b64encode(b"webm").decode(), "mimeType": "audio/webm"}
    ).json()

    _buyer, reply = response["messages"]
    assert reply["voice"] == {"status": "TRANSCRIBED", "hasAudio": True}
    assert reply["body"] == "We get loafers, sneakers and sandals."
    audio = client.get(f"/simulator/conversations/{response['conversation']['id']}/messages/{reply['id']}/audio")
    assert audio.content == SPOKEN and audio.headers["content-type"] == "audio/ogg"


def test_settings_show_whether_voice_replies_can_work(client: TestClient, voices: Any) -> None:
    settings = client.get("/vendor/settings").json()
    assert (settings["voiceReplies"], settings["voiceRepliesAvailable"]) == (True, True)
