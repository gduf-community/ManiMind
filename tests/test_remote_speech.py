import asyncio
import hashlib
import io
import json
from email.message import Message
from pathlib import Path
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError

import pytest

from manimind.postproduce import qwen_service as service
from manimind.postproduce import remote_speech as client


def wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(b"\0\0" * 2400)
    return stream.getvalue()


class Backend:
    def __init__(self):
        self.calls = 0
        self.manifest = {"fixture": "not a model generation"}

    def generate(self, payload):
        self.calls += 1
        return wav()


def invoke(app, path, payload=None, token="T" * 32, length=True):
    body = json.dumps(payload).encode() if payload is not None else b""
    headers = [(b"content-type", b"application/json"), (b"authorization", ("Bearer " + token).encode())]
    if length:
        headers.append((b"content-length", str(len(body)).encode()))
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "method": "POST" if payload is not None else "GET", "path": path, "raw_path": path.encode(),
             "query_string": b"", "headers": headers, "http_version": "1.1", "scheme": "http",
             "server": ("127.0.0.1", 8766), "client": ("127.0.0.1", 1234)}
    sent = []

    async def run():
        received = False

        async def receive():
            nonlocal received
            if received:
                await asyncio.Event().wait()
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)

    asyncio.run(run())
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], dict(start["headers"]), b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


@pytest.fixture
def engine(tmp_path):
    return service.SpeechEngine(Backend(), tmp_path / "cache")


def test_wave_receipt_is_measured_and_identical_request_uses_cache(engine):
    request = service.SpeechRequest(input="Fixture text")
    data, receipt = engine.synthesize(request)
    again, cached = engine.synthesize(request)
    assert data == again and engine.backend.calls == 1
    assert receipt["wav_sha256"] == hashlib.sha256(data).hexdigest()
    assert receipt["duration_seconds"] == .1 and receipt["sample_rate"] == 24000
    assert cached["cache_hit"] and not receipt["cache_hit"]
    assert "not listening" in receipt["scope"]


def test_voice_and_engine_change_invalidate_cache(engine):
    first = service.SpeechRequest(input="Fixture")
    _, a = engine.synthesize(first)
    _, b = engine.synthesize(service.SpeechRequest(input="Fixture", voice="Serena"))
    engine.backend.manifest = {"fixture": "changed"}
    _, c = engine.synthesize(first)
    assert len({a["request_id"], b["request_id"], c["request_id"]}) == 3
    assert engine.backend.calls == 3


def test_wrong_model_variant_or_missing_weights_is_not_mislabeled(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    config = model / "config.json"
    config.write_text(json.dumps({"tts_model_type": "base", "tts_model_size": "1b7"}))
    with pytest.raises(ValueError, match="CustomVoice"):
        service.validate_model_path(model)
    config.write_text(json.dumps({"tts_model_type": "custom_voice", "tts_model_size": "1b7"}))
    with pytest.raises(ValueError, match="weights"):
        service.validate_model_path(model)
    (model / "model.safetensors").write_bytes(b"fixture only")
    service.validate_model_path(model)


def test_changed_cached_bytes_are_not_accepted(engine):
    request = service.SpeechRequest(input="Fixture")
    _, record = engine.synthesize(request)
    (engine.cache / (record["request_id"] + ".wav")).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="receipt changed"):
        engine.synthesize(request)
    assert not engine.lock.locked()


def test_failed_backend_never_creates_success_receipts_and_releases_lock(engine):
    engine.backend.generate = lambda _: b"not WAV"
    with pytest.raises((wave.Error, EOFError)):
        engine.synthesize(service.SpeechRequest(input="Fixture"))
    assert not list(engine.cache.iterdir()) and not engine.lock.locked()


def test_busy_request_does_not_start_generation(engine):
    engine.lock.acquire()
    try:
        with pytest.raises(service.BusyError):
            engine.synthesize(service.SpeechRequest(input="Fixture"))
        assert engine.backend.calls == 0
    finally:
        engine.lock.release()


@pytest.mark.parametrize("payload", [{"input": " "}, {"input": "x" * 601},
    {"input": "ok", "voice": "https://not-a-voice.invalid"}, {"input": "ok", "reference_audio": "secret.wav"},
    {"input": "ok", "model": "other-model"}, {"input": "ok", "language": "unsupported"}])
def test_invalid_or_unintended_capabilities_are_rejected(payload):
    with pytest.raises(ValueError):
        service.SpeechRequest(**payload)


def test_health_and_generation_both_require_authentication(engine):
    app = service.create_app(engine, "T" * 32)
    assert invoke(app, "/health", token="wrong")[0] == 401
    assert invoke(app, "/v1/audio/speech", {"input": "Fixture"}, token="wrong")[0] == 401
    assert engine.backend.calls == 0
    status, _, data = invoke(app, "/health")
    assert status == 200 and json.loads(data)["status"] == "ready"


def test_http_wave_hash_cache_and_body_limits(engine):
    app = service.create_app(engine, "T" * 32)
    status, headers, data = invoke(app, "/v1/audio/speech", {"input": "Fixture"})
    assert status == 200 and data == wav()
    assert headers[b"x-audio-sha256"].decode() == hashlib.sha256(data).hexdigest()
    assert invoke(app, "/v1/audio/speech", {"input": "Fixture"})[1][b"x-cache-hit"] == b"1"
    assert invoke(app, "/v1/audio/speech", {"input": "x" * 40000})[0] == 413
    assert invoke(app, "/v1/audio/speech", {"input": "Fixture"}, length=False)[0] == 413
    assert invoke(app, "/v1/audio/speech", {"input": "Fixture", "path": "/etc/passwd"})[0] == 422


def test_http_busy_is_explicit_and_weak_tokens_are_refused(engine):
    with pytest.raises(ValueError):
        service.create_app(engine, "weak")
    app = service.create_app(engine, "T" * 32)
    engine.lock.acquire()
    try:
        assert invoke(app, "/v1/audio/speech", {"input": "Fixture"})[0] == 503
        assert engine.backend.calls == 0
    finally:
        engine.lock.release()


@pytest.mark.parametrize("url", ["http://192.168.1.1:8766", "http://example.invalid", "https://localhost", "http://user:secret@localhost", "http://localhost?q=secret"])
def test_client_refuses_unencrypted_non_tunnel_destinations(tmp_path, url):
    with pytest.raises(ValueError, match="loopback"):
        client.audio_request(url, tmp_path / "missing-token", {}, tmp_path / "audio.wav")


def test_client_validates_wave_and_preserves_request_without_secret(tmp_path, monkeypatch):
    token = tmp_path / "private-token"
    token.write_text("T" * 32)
    target = tmp_path / "audio.wav"
    payload = {"input": "Original narration", "voice": "Uncle_Fu"}
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Audio-SHA256"] = hashlib.sha256(wav()).hexdigest()
    class Reply(io.BytesIO):
        pass
    def open_request(request, timeout):
        assert json.loads(request.data) == payload
        assert request.get_header("Authorization") == "Bearer " + "T" * 32
        result = Reply(wav())
        result.headers = headers
        return result
    monkeypatch.setattr(client.urllib.request, "build_opener", lambda *_: type("Opener", (), {"open": staticmethod(open_request)})())
    record = client.audio_request("http://127.0.0.1:17666", token, payload, target)
    assert record["request"] == payload and record["duration_seconds"] == .1
    assert "T" * 32 not in target.with_suffix(".receipt.json").read_text()
    with pytest.raises(ValueError, match="not overwritten"):
        client.audio_request("http://127.0.0.1:17666", token, payload, target)
    target.unlink()
    target.with_suffix(".receipt.json").unlink()
    headers.replace_header("X-Audio-SHA256", "wrong")
    with pytest.raises(ValueError, match="hash mismatch"):
        client.audio_request("http://127.0.0.1:17666", token, payload, target)
    assert not target.exists()


def test_client_never_forwards_private_token_through_redirect(tmp_path):
    seen = []

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/not-authorized")
            self.end_headers()

        def do_GET(self):
            seen.append(self.path)
            self.send_response(500)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = tmp_path / "private-token"
    token.write_text("T" * 32)
    try:
        with pytest.raises(HTTPError) as error:
            client.audio_request(f"http://127.0.0.1:{server.server_port}", token, {"input": "Fixture"}, tmp_path / "audio.wav")
        assert error.value.code == 302
        assert seen == ["/v1/audio/speech"]
        assert not (tmp_path / "audio.wav").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
