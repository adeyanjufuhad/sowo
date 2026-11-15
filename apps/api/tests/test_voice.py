"""Voice notes in: a buyer speaks, Whisper writes it down, and Sowo answers the words like typed text.

Meta's media API and Groq's Whisper are always mocked here. Examples are in Pidgin and English, the way buyers talk.
"""

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import (
    BUYER_PHONE,
    LOAFERS_FLOOR_KOBO,
    ScriptedModel,
    call,
    say,
    sign_in_vendor,
    signed,
    use_model,
    whatsapp_payload,
)
from scenarios import new_chat
from sqlalchemy import select

from app.config import Settings, get_settings
from app.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    Vendor,
    VoiceNote,
    VoiceStatus,
)
from app.services import flow, whatsapp
from app.services.voice import stt
from app.services.voice.notes import cant_hear_reply

AUDIO = b"OggS\x00fake-opus-voice-note"
DOWNLOAD_URL = "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=media-1"


# -- doubles for Meta and Groq ---------------------------------------------------------------------------------


class Meta:
    """Plays the Graph API: the media lookup, the download, and the /messages sends (recorded into env.graph)."""

    def __init__(self, env: Env, *, file_size: int | None = None, url: str = DOWNLOAD_URL, download_status: int = 200):
        self.env, self.file_size, self.url, self.download_status = env, file_size, url, download_status
        self.downloads = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.env.graph.append({"url": str(request.url), "headers": dict(request.headers), "json": body})
        if request.method == "GET" and request.url.host == "graph.facebook.com":
            assert request.headers["authorization"] == "Bearer wa-access-token"
            size = len(AUDIO) if self.file_size is None else self.file_size
            return httpx.Response(200, json={"url": self.url, "mime_type": "audio/ogg; codecs=opus", "file_size": size})
        if request.method == "GET":
            self.downloads += 1
            assert request.headers["authorization"] == "Bearer wa-access-token"
            return httpx.Response(self.download_status, content=AUDIO)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})


class Whisper:
    """Plays Groq's /audio/transcriptions."""

    def __init__(self, text: str = "", *, duration: float = 6.2, status: int = 200) -> None:
        self.text, self.duration, self.status = text, duration, status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"message": "nope"}})
        return httpx.Response(200, json={"text": self.text, "duration": self.duration, "language": "english"})


@pytest.fixture
def voice_on(env: Env, monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[Meta, Whisper]]:
    """Turn voice notes on with a Groq key, and put Meta and Whisper doubles in place."""
    monkeypatch.setenv("STT_API_KEY", "groq-test-key")
    get_settings.cache_clear()

    def install(text: str = "", *, meta: Meta | None = None, whisper: Whisper | None = None) -> tuple[Meta, Whisper]:
        meta = meta or Meta(env)
        whisper = whisper or Whisper(text)
        monkeypatch.setattr(whatsapp, "_transport_override", httpx.MockTransport(meta))
        monkeypatch.setattr(stt, "_transport_override", httpx.MockTransport(whisper))
        return meta, whisper

    return install


def voice_payload(message_id: str = "wamid.voice1") -> dict[str, Any]:
    payload = whatsapp_payload(message_id=message_id)
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    del message["text"]
    message.update({"type": "audio", "audio": {"id": "media-1", "mime_type": "audio/ogg; codecs=opus", "voice": True}})
    return payload


def post_voice(client: TestClient, message_id: str = "wamid.voice1") -> None:
    raw, headers = signed(voice_payload(message_id))
    assert client.post("/webhooks/whatsapp", content=raw, headers=headers).status_code == 200


def buyer_voice_message(env: Env) -> Message:
    with env.session() as session:
        found = session.scalar(select(Message).where(Message.kind == "voice"))
        assert found is not None
        return found


# -- the speech-to-text provider -------------------------------------------------------------------------------


def test_groq_whisper_sends_the_audio_and_reads_the_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    whisper = Whisper("Abeg how much for the black loafers?", duration=4.5)
    monkeypatch.setattr(stt, "_transport_override", httpx.MockTransport(whisper))

    transcript = stt.GroqWhisper("groq-key", "whisper-large-v3-turbo").transcribe(AUDIO, "audio/ogg; codecs=opus")

    assert transcript == stt.Transcript("Abeg how much for the black loafers?", 4.5, "english")
    request = whisper.requests[0]
    assert str(request.url) == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert request.headers["authorization"] == "Bearer groq-key"
    body = request.content
    assert b'name="model"\r\n\r\nwhisper-large-v3-turbo' in body
    assert b'filename="voice.ogg"' in body and AUDIO in body
    assert b"Pidgin" in body  # the vocabulary hint


@pytest.mark.parametrize("status", [401, 429, 500])
def test_a_provider_error_is_a_transcription_error(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setattr(stt, "_transport_override", httpx.MockTransport(Whisper("hi", status=status)))
    with pytest.raises(stt.TranscriptionError):
        stt.GroqWhisper("k", "m").transcribe(AUDIO, "audio/ogg")


def test_silence_and_unsupported_formats_are_transcription_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    whisper = Whisper("   ")
    monkeypatch.setattr(stt, "_transport_override", httpx.MockTransport(whisper))
    with pytest.raises(stt.TranscriptionError):
        stt.GroqWhisper("k", "m").transcribe(AUDIO, "audio/ogg")
    with pytest.raises(stt.TranscriptionError):
        stt.GroqWhisper("k", "m").transcribe(AUDIO, "audio/amr")  # WhatsApp can send AMR; Whisper can't read it
    assert len(whisper.requests) == 1


@pytest.mark.parametrize(
    ("settings", "expected_key"),
    [
        ({}, None),  # no key anywhere: voice notes are off
        ({"stt_api_key": "stt-key"}, "stt-key"),
        ({"stt_api_key": "stt-key", "stt_provider": "none"}, None),
        (  # one Groq key covers the model and the transcription
            {"model_provider": "openai", "llm_base_url": "https://api.groq.com/openai/v1", "llm_model": "q", "llm_api_key": "llm-key"},
            "llm-key",
        ),
        (  # another host's key is never sent to Groq
            {"model_provider": "openai", "llm_base_url": "https://openrouter.ai/api/v1", "llm_model": "q", "llm_api_key": "llm-key"},
            None,
        ),
    ],
)
def test_which_key_transcribes(settings: dict[str, str], expected_key: str | None) -> None:
    provider = stt.speech_to_text(Settings(_env_file=None, **settings))  # type: ignore[call-arg]
    assert (provider.api_key if isinstance(provider, stt.GroqWhisper) else None) == expected_key


def test_the_cant_hear_replies_speak_the_buyers_language() -> None:
    assert "Abeg" in cant_hear_reply(VoiceStatus.FAILED, pidgin=True, max_seconds=120)
    assert "type it" in cant_hear_reply(VoiceStatus.FAILED, pidgin=False, max_seconds=120)
    assert "2 minutes" in cant_hear_reply(VoiceStatus.TOO_LONG, pidgin=False, max_seconds=120)
    assert "shorter one" in cant_hear_reply(VoiceStatus.TOO_LONG, pidgin=True, max_seconds=120)


# -- WhatsApp voice notes --------------------------------------------------------------------------------------


def test_parse_inbound_reads_the_voice_notes_media_id() -> None:
    [inbound] = whatsapp.parse_inbound(voice_payload())
    assert (inbound.kind, inbound.media_id, inbound.mime_type, inbound.text) == (
        "audio",
        "media-1",
        "audio/ogg; codecs=opus",
        "",
    )


def test_a_pidgin_voice_note_is_answered_like_typed_text(env: Env, client: TestClient, voice_on: Any) -> None:
    meta, _ = voice_on("Abeg how much for the black loafers size 43?")
    model = ScriptedModel(call("search_catalog", query="black loafers 43"), say("Na ₦45,000 for the black loafers."))
    use_model(model)

    post_voice(client)

    assert model.requests[0]["messages"][-1] == {"role": "user", "content": "Abeg how much for the black loafers size 43?"}
    assert env.texts_to(BUYER_PHONE) == ["Na ₦45,000 for the black loafers."]  # one reply, one message
    assert meta.downloads == 1
    message = buyer_voice_message(env)
    assert (message.text, message.voice_status) == ("Abeg how much for the black loafers size 43?", "TRANSCRIBED")
    with env.session() as session:
        note = session.get(VoiceNote, message.voice_note_id)
        assert note is not None and note.data == AUDIO and note.mime_type == "audio/ogg" and note.duration_ms == 6200


def test_a_spoken_english_offer_still_goes_through_the_haggling_engine(
    env: Env, client: TestClient, voice_on: Any
) -> None:
    voice_on("Can you do 35k for the black loafers?")
    model = ScriptedModel(
        call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=35000),
        say("35k is too low, the best I can do is ₦43,000."),
    )
    use_model(model)

    post_voice(client)

    assert env.texts_to(BUYER_PHONE) == ["35k is too low, the best I can do is ₦43,000."]
    assert str(LOAFERS_FLOOR_KOBO) not in model.everything_sent
    assert f"{LOAFERS_FLOOR_KOBO // 100:,}" not in model.everything_sent


def test_a_spoken_price_agreed_in_words_is_sent_back_to_the_haggling_engine(
    env: Env, client: TestClient, voice_on: Any
) -> None:
    voice_on("Oga abeg sell am give me 20k")
    model = ScriptedModel(
        say("Okay ₦20,000 it is!"),  # agrees without asking the server: the guard sends it back
        call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=20000),
        say("20k too low for this one o. Wetin you fit pay?"),
    )
    use_model(model)

    post_voice(client)

    assert "evaluate_offer" in model.requests[1]["messages"][-1]["content"]  # the same nudge typed text gets
    assert env.texts_to(BUYER_PHONE) == ["20k too low for this one o. Wetin you fit pay?"]
    with env.session() as session:
        reply = session.scalar(select(Message).where(Message.role == MessageRole.AI))
        assert reply is not None and reply.tool_calls[0]["output"] == {"decision": "REJECT"}


def test_a_file_too_big_is_never_downloaded(env: Env, client: TestClient, voice_on: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_MAX_BYTES", "1000")
    get_settings.cache_clear()
    meta, whisper = voice_on("never heard", meta=Meta(env, file_size=5_000_000))
    use_model(ScriptedModel())  # the model is not asked

    post_voice(client)

    assert meta.downloads == 0 and whisper.requests == []
    assert buyer_voice_message(env).voice_status == "TOO_LONG"
    assert env.texts_to(BUYER_PHONE) == [cant_hear_reply(VoiceStatus.TOO_LONG, pidgin=False, max_seconds=120)]


def test_a_voice_note_longer_than_the_limit_is_not_answered(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on(whisper=Whisper("A very long story about shoes", duration=600))
    use_model(ScriptedModel())

    post_voice(client)

    message = buyer_voice_message(env)
    assert (message.voice_status, message.text) == ("TOO_LONG", "")
    assert env.texts_to(BUYER_PHONE) == [cant_hear_reply(VoiceStatus.TOO_LONG, pidgin=False, max_seconds=120)]


def test_when_whisper_fails_a_pidgin_buyer_is_asked_in_pidgin_to_type(env: Env, client: TestClient, voice_on: Any) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    with env.session() as session:
        conversation = session.get(Conversation, chat)
        assert conversation is not None
        flow.add_message(session, conversation, MessageRole.BUYER, "Abeg wetin una get for shoes?")
    voice_on(whisper=Whisper(status=500))
    use_model(ScriptedModel())

    post_voice(client)

    assert env.texts_to(BUYER_PHONE) == [cant_hear_reply(VoiceStatus.FAILED, pidgin=True, max_seconds=120)]
    assert env.conversation().status == ConversationStatus.ACTIVE  # the chat carries on; the buyer can type


def test_with_no_speech_provider_the_buyer_is_asked_to_type(
    env: Env, client: TestClient, voice_on: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STT_PROVIDER", "none")
    get_settings.cache_clear()
    _, whisper = voice_on("not used")
    use_model(ScriptedModel())

    post_voice(client)

    assert whisper.requests == []
    assert buyer_voice_message(env).voice_status == "FAILED"
    assert env.texts_to(BUYER_PHONE) == [cant_hear_reply(VoiceStatus.FAILED, pidgin=False, max_seconds=120)]


@pytest.mark.parametrize("url", ["https://evil.example/steal", "http://lookaside.fbsbx.com/plain-http"])
def test_media_links_off_metas_hosts_are_not_followed(env: Env, client: TestClient, voice_on: Any, url: str) -> None:
    meta, _ = voice_on("never heard", meta=Meta(env, url=url))
    use_model(ScriptedModel())

    post_voice(client)

    assert meta.downloads == 0
    assert buyer_voice_message(env).voice_status == "FAILED"


def test_a_failed_download_gets_the_polite_reply(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on("never heard", meta=Meta(env, download_status=404))
    use_model(ScriptedModel())

    post_voice(client)

    assert env.texts_to(BUYER_PHONE) == [cant_hear_reply(VoiceStatus.FAILED, pidgin=False, max_seconds=120)]


def test_the_same_voice_note_delivered_twice_is_heard_once(env: Env, client: TestClient, voice_on: Any) -> None:
    _, whisper = voice_on("Hello, I want sneakers")
    use_model(ScriptedModel(say("Hi! Which size?")))

    post_voice(client)
    post_voice(client)

    assert len(whisper.requests) == 1
    assert env.texts_to(BUYER_PHONE) == ["Hi! Which size?"]


def test_a_paused_chat_keeps_the_transcript_but_sowo_stays_quiet(env: Env, client: TestClient, voice_on: Any) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    with env.session() as session:
        conversation = session.get(Conversation, chat)
        assert conversation is not None
        conversation.status, conversation.ai_paused = ConversationStatus.PAUSED, True
        session.commit()
    voice_on("Ada, I want to exchange my shoes")
    use_model(ScriptedModel())

    post_voice(client)

    assert buyer_voice_message(env).text == "Ada, I want to exchange my shoes"
    assert env.texts_to(BUYER_PHONE) == []


# -- the dashboard ---------------------------------------------------------------------------------------------


def test_the_dashboard_shows_the_transcript_and_plays_the_audio(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on("I want the white sneakers in size 44")
    use_model(ScriptedModel(say("Let me check size 44 for you.")))
    post_voice(client)
    chat = env.conversation().id

    listing = client.get(f"/conversations/{chat}/messages").json()
    voice = listing["messages"][0]
    assert voice["sender"] == "BUYER" and voice["body"] == "I want the white sneakers in size 44"
    assert voice["voice"] == {"status": "TRANSCRIBED", "durationMs": 6200, "hasAudio": True}
    assert listing["messages"][1]["voice"] is None

    audio = client.get(f"/conversations/{chat}/messages/{voice['id']}/audio")
    assert audio.status_code == 200 and audio.content == AUDIO
    assert audio.headers["content-type"] == "audio/ogg"
    assert audio.headers["cache-control"].startswith("private")


def test_a_voice_note_nobody_could_hear_shows_in_the_chats_list(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on(whisper=Whisper(status=500))
    use_model(ScriptedModel())
    post_voice(client)

    [chat] = client.get("/conversations").json()["conversations"]
    messages = client.get(f"/conversations/{chat['id']}/messages").json()["messages"]
    assert messages[0]["voice"]["status"] == "FAILED" and messages[0]["body"] == ""
    assert chat["preview"] == cant_hear_reply(VoiceStatus.FAILED, pidgin=False, max_seconds=120)


def test_another_vendor_cannot_play_a_buyers_voice(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on("Hello")
    use_model(ScriptedModel(say("Hi!")))
    post_voice(client)
    chat = env.conversation().id
    message = buyer_voice_message(env).id
    with env.session() as session:
        bola = Vendor(name="Bola's Bags")
        session.add(bola)
        session.commit()
        token = sign_in_vendor(session, bola, email="bola@example.com")

    response = client.get(f"/conversations/{chat}/messages/{message}/audio", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


# -- the /try simulator ----------------------------------------------------------------------------------------


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_a_recording_from_try_takes_the_same_path(client: TestClient, voice_on: Any) -> None:
    _, whisper = voice_on("How much for the black loafers?")
    use_model(ScriptedModel(call("search_catalog", query="black loafers"), say("The black loafers are ₦45,000.")))

    response = client.post("/simulator/voice", json={"audio": b64(b"webm-bytes"), "mimeType": "audio/webm;codecs=opus"})

    assert response.status_code == 200
    buyer, reply = response.json()["messages"]
    assert buyer["body"] == "How much for the black loafers?" and buyer["voice"]["status"] == "TRANSCRIBED"
    assert reply["body"] == "The black loafers are ₦45,000."
    assert b'filename="voice.webm"' in whisper.requests[0].content

    chat = response.json()["conversation"]["id"]
    audio = client.get(f"/simulator/conversations/{chat}/messages/{buyer['id']}/audio")
    assert audio.status_code == 200 and audio.content == b"webm-bytes"


def test_a_try_recording_nobody_can_hear_gets_the_polite_reply(client: TestClient, voice_on: Any) -> None:
    voice_on(whisper=Whisper(status=503))
    use_model(ScriptedModel())

    response = client.post("/simulator/voice", json={"audio": b64(b"mp4-bytes"), "mimeType": "audio/mp4"})

    buyer, reply = response.json()["messages"]
    assert buyer["voice"]["status"] == "FAILED"
    assert reply["body"] == cant_hear_reply(VoiceStatus.FAILED, pidgin=False, max_seconds=120)


def test_try_refuses_bad_or_oversized_recordings(client: TestClient, voice_on: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    voice_on("unused")
    use_model(ScriptedModel())
    assert client.post("/simulator/voice", json={"audio": "not base64!", "mimeType": "audio/webm"}).status_code == 400
    monkeypatch.setenv("VOICE_MAX_BYTES", "10")
    get_settings.cache_clear()
    assert client.post("/simulator/voice", json={"audio": b64(b"x" * 100), "mimeType": "audio/webm"}).status_code == 413


def test_try_audio_is_only_served_for_simulator_chats(env: Env, client: TestClient, voice_on: Any) -> None:
    voice_on("Hello")
    use_model(ScriptedModel(say("Hi!")))
    post_voice(client)  # a real WhatsApp buyer's voice
    chat, message = env.conversation().id, buyer_voice_message(env).id

    assert client.get(f"/simulator/conversations/{chat}/messages/{message}/audio").status_code == 404


def test_try_voice_is_off_with_the_simulator(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_ENABLED", "false")
    get_settings.cache_clear()
    assert client.post("/simulator/voice", json={"audio": b64(b"x"), "mimeType": "audio/webm"}).status_code == 404
