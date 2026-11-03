"""Offline tests of bounded model collaboration, with no paid requests."""

import json
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from manimind.experiments import model_dialogue as dialogue


@pytest.fixture
def case(monkeypatch, tmp_path):
    from manimind.llm import client

    def no_network(*args, **kwargs):
        pytest.fail("Unexpected network request")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(dialogue.bench, "ROOT", tmp_path)
    monkeypatch.setenv("MIMO_EZLOOK_API_KEY", "private-test-key")
    sdk = MagicMock()
    sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
        model="served", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"observations": []}'))],
    )
    monkeypatch.setattr(client, "OpenAI", sdk)
    purpose = tmp_path / "purpose.json"
    purpose.write_text('{"test": true}')
    dialogue.init("test", "mimo-ezlook-fast", purpose, 2)
    brief = tmp_path / "brief.txt"
    brief.write_text("Inspect actual evidence")
    return tmp_path, brief, sdk


def test_dialogue_forwards_images_records_history_and_rejects_third_call(case):
    root, brief, sdk = case
    image = root / "frame.jpg"
    image.write_bytes(b"fixture-image")
    dialogue.ask("test", brief, [image], 1024)
    content = sdk.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    dialogue.ask("test", brief, [], 1024)
    _, context, session = dialogue.bench.paths("test")
    prompt = dialogue.read_json(session / "dialogue-02-prompt.json")
    assert len(prompt["history"]) == 1
    assert "base64" not in (session / "dialogue-01-prompt.json").read_text()
    assert "private-test-key" not in json.dumps(dialogue.read_json(context / "collaboration.json"))
    with pytest.raises(ValueError, match="cap reached"):
        dialogue.ask("test", brief, [])
    assert sdk.return_value.chat.completions.create.call_count == 2


def test_bad_json_is_saved_and_counted(case):
    root, brief, sdk = case
    sdk.return_value.chat.completions.create.return_value.choices[0].message.content = "not JSON"
    with pytest.raises(json.JSONDecodeError):
        dialogue.ask("test", brief, [])
    out, _, session = dialogue.bench.paths("test")
    ledger = dialogue.read_json(session / "dialogue.json")
    assert ledger["turns"][0]["status"] == "failed"
    assert (session / "dialogue-01-reply.txt").read_text() == "not JSON"
    assert dialogue.read_json(out / "dialogue-cost.json")["requests"] == 1
    (session / "dialogue-01-reply.txt").write_text("edited failed evidence")
    with pytest.raises(ValueError, match="prior model answer"):
        dialogue.ask("test", brief, [])
    assert sdk.return_value.chat.completions.create.call_count == 1


def test_evidence_text_is_snapshotted_and_not_just_a_path(case):
    root, brief, sdk = case
    source = root / "scene.py"
    source.write_text("class Example: pass")
    dialogue.ask("test", brief, [], evidence_text=[source])
    content = sdk.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"][0]["text"]
    assert "class Example: pass" in content
    assert dialogue.sha256(source) in content


def test_changed_case_or_reply_blocks_reuse(case):
    _, brief, sdk = case
    dialogue.ask("test", brief, [])
    _, context, session = dialogue.bench.paths("test")
    (session / "dialogue-01-reply.txt").write_text("changed")
    with pytest.raises(ValueError, match="prior model answer"):
        dialogue.ask("test", brief, [])
    (context / "collaboration.json").write_text(json.dumps({"max_requests": 2}))
    with pytest.raises(ValueError, match="frozen collaboration"):
        dialogue.ask("test", brief, [])
    assert sdk.return_value.chat.completions.create.call_count == 1


@pytest.mark.parametrize("value", ["[]", "bad", "```json\n[]\n```"])
def test_dialogue_requires_object(value):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        dialogue.parse_reply(value)
