import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import chatbot as api
from app.services.chatbot import tts
from app.services.chatbot.captions import make_translator
from app.services.chatbot.factory import ChatbotServices


class Resp:
    def __init__(self, code=200, content=b"MP3"): self.status_code, self.content = code, content


def test_clean_for_tts_removes_markdown_links_emojis():
    assert tts.clean_for_tts("**Fève** 🌱 voir https://x.org  ok") == "Fève voir ok"


def test_tts_requires_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(tts.TTSNotConfigured):
        tts.synthesize("salut")


def test_tts_calls_elevenlabs_with_model_and_key_in_header(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k"); monkeypatch.setenv("ELEVENLABS_VOICE_ID", "V1")
    seen = {}
    def post(url, **kw): seen.update(url=url, **kw); return Resp()
    assert tts.synthesize("salut", post=post) == b"MP3"
    assert seen["url"].endswith("/v1/text-to-speech/V1") and seen["headers"]["xi-api-key"] == "k"
    assert seen["json"]["model_id"] == "eleven_multilingual_v2"


def test_tts_upstream_error_does_not_leak_body(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    with pytest.raises(tts.TTSError) as e:
        tts.synthesize("salut", post=lambda *a, **k: Resp(401, b"secret account detail"))
    assert "secret" not in str(e.value)
    def boom(*a, **k): raise requests.ConnectionError("x")
    with pytest.raises(tts.TTSError):
        tts.synthesize("salut", post=boom)


def test_translator_caps_length_and_skips_empty():
    calls = []
    tr = make_translator(lambda s, u: calls.append(u) or " hello ")
    assert tr("") == "" and tr("x" * 900) == "hello" and len(calls[0]) == 500


class FakeOrch:
    def handle(self, db, user, text, **kw): return {"text": "ok:" + text, "figures": [], "needs_info": [], "intent": "irrigation", "mode": None}


def client(authenticated=True):
    app = FastAPI(); app.include_router(api.router, prefix="/api/v1/chatbot")
    app.dependency_overrides[api.get_chatbot] = lambda: ChatbotServices(FakeOrch(), lambda t: "EN:" + t)
    app.dependency_overrides[api.get_db] = lambda: None
    if authenticated:
        app.dependency_overrides[api.get_current_user] = lambda: {"id": 1}
    return TestClient(app, raise_server_exceptions=False)


def test_live_page_is_served_and_has_no_streamlit():
    r = client(False).get("/api/v1/chatbot/live")
    assert r.status_code == 200 and "SpeechRecognition" in r.text and "streamlit" not in r.text.lower()


def test_endpoints_fail_closed_without_auth():
    c = client(False)
    for path, body in (("/captions", {"text": "a"}), ("/message", {"text": "a"}), ("/speak", {"text": "a"})):
        assert c.post("/api/v1/chatbot" + path, json=body).status_code == 401   # JWT obligatoire


def test_message_captions_and_speak_ok(monkeypatch):
    c = client()
    assert c.post("/api/v1/chatbot/message", json={"text": "hi"}).json()["text"] == "ok:hi"
    assert c.post("/api/v1/chatbot/captions", json={"text": "hi"}).json() == {"en": "EN:hi"}
    monkeypatch.setattr(api, "synthesize", lambda t: b"MP3DATA")
    r = c.post("/api/v1/chatbot/speak", json={"text": "hi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"MP3DATA"


def test_speak_maps_errors_to_http(monkeypatch):
    c = client()
    def not_cfg(t): raise tts.TTSNotConfigured("x")
    monkeypatch.setattr(api, "synthesize", not_cfg)
    assert c.post("/api/v1/chatbot/speak", json={"text": "hi"}).status_code == 503
    def down(t): raise tts.TTSError("x")
    monkeypatch.setattr(api, "synthesize", down)
    assert c.post("/api/v1/chatbot/speak", json={"text": "hi"}).status_code == 502


def test_input_validation():
    c = client()
    assert c.post("/api/v1/chatbot/message", json={"text": "a", "lang": "xx"}).status_code == 422
    assert c.post("/api/v1/chatbot/speak", json={"text": "a" * 2000}).status_code == 422
