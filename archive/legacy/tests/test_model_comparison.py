"""Offline checks for identical candidate input and bounded blind-review calls."""

import json
from pathlib import Path
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from manimind.experiments import model_comparison as compare


@pytest.fixture
def comparison(tmp_path, monkeypatch):
    from manimind.llm import client

    def no_network(*args, **kwargs):
        pytest.fail("Unexpected network request")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(compare.bench, "ROOT", tmp_path)
    monkeypatch.setattr(compare, "check_components", lambda baseline: None)
    settings_path = tmp_path / "profiles.json"
    profiles = {}
    for name in ("deepseek", "mimo"):
        profiles[name] = {"model": name, "base_url": f"https://{name}.example/v1",
                          "api_key_env": name.upper() + "_TEST_KEY", "allowed_hosts": [name + ".example"],
                          "temperature": 0.6, "extra_body": {}, "pricing": None}
        monkeypatch.setenv(name.upper() + "_TEST_KEY", "private-test-value")
    compare.pilot.write_json(settings_path, {"profiles": profiles})
    monkeypatch.setattr(compare.bench, "SETTINGS", settings_path)
    baseline = tmp_path / "runtime/projects/baseline/suite.json"
    compare.pilot.write_json(baseline, {"system": compare.experiment.SYSTEM, "contract": compare.experiment.CONTRACT,
                                     "settings": {"profile": "mimo", "runs": ["untouched"], "tasks": {"truth": 42}}})
    for case in ("a", "b"):
        directory = tmp_path / "outputs/baseline" / case / "render-01"
        compare.pilot.write_json(directory / "scene-spec.json", {"title": "Neutral", "model": {"truth": 42}})
        compare.pilot.write_json(directory / "timeline.json", {"duration": 3, "fps": 30, "cues": [
            {"id": "cue", "start": 0, "duration": 3, "subtitle_lines": ["Example"], "audio_path": "PRIVATE_SOURCE_PATH"}]})
        (directory / "frames").mkdir()
        (directory / "frames/frame_2_0.jpg").write_bytes(b"fixture-image")
    config = tmp_path / "config.json"
    compare.pilot.write_json(config, {"id": "comparison", "baseline_suite": "baseline", "generation_suite": "candidate-suite",
        "generation_profile": "deepseek", "review_profiles": {"deepseek": "deepseek", "mimo": "mimo"},
        "max_review_output_tokens": 1024, "cases": [
            {"id": "case01", "run": "a", "render": "render-01", "times": [2]},
            {"id": "case02", "run": "b", "render": "render-01", "times": [2]}]})
    sdk = MagicMock()
    sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
        model="served", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"findings": []}'))])
    monkeypatch.setattr(client, "OpenAI", sdk)
    compare.prepare(config)
    return tmp_path, sdk


def test_prepare_preserves_generation_controls_and_removes_private_paths(comparison):
    root, sdk = comparison
    record = compare.load("comparison")
    settings = compare.pilot.read_json(Path(record["generation_config"]))
    assert settings == {"profile": "deepseek", "runs": ["untouched"], "tasks": {"truth": 42}}
    packet = (root / "outputs/comparison/case01/brief.json").read_text()
    assert "PRIVATE_SOURCE_PATH" not in packet
    assert "ground-truth" not in packet and "expected_verdict" not in packet
    assert not sdk.called
    with pytest.raises(ValueError, match="already exists"):
        compare.prepare(root / "config.json")


def test_providers_receive_identical_packets_without_history_or_answers(comparison):
    root, sdk = comparison
    compare.pilot.write_json(root / "runtime/projects/comparison/ground-truth.json", {"secret_answer": "NEVER_SEND_THIS"})
    compare.review("comparison", "deepseek")
    compare.review("comparison", "mimo")
    calls = sdk.return_value.chat.completions.create.call_args_list
    assert len(calls) == 4
    for i in range(2):
        assert calls[i].kwargs["messages"] == calls[i + 2].kwargs["messages"]
        sent = json.dumps(calls[i].kwargs["messages"])
        assert "NEVER_SEND_THIS" not in sent
        payload = json.loads(calls[i].kwargs["messages"][1]["content"][0]["text"])
        assert payload["history"] == []
    compare.review("comparison", "mimo")
    assert sdk.return_value.chat.completions.create.call_count == 4


def test_missing_key_stops_before_any_candidate_case(comparison, monkeypatch):
    root, sdk = comparison
    monkeypatch.delenv("DEEPSEEK_TEST_KEY")
    with pytest.raises(ValueError, match="Missing DEEPSEEK_TEST_KEY"):
        compare.review("comparison", "deepseek")
    assert not sdk.called
    assert not (root / "runtime/projects/comparison-deepseek-case01").exists()


def test_tampered_evidence_blocks_paid_call(comparison):
    root, sdk = comparison
    (root / "outputs/comparison/case01/frame-01.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed comparison evidence"):
        compare.review("comparison", "mimo")
    assert not sdk.called


def test_changed_provider_blocks_paid_call(comparison):
    _, sdk = comparison
    settings = compare.pilot.read_json(compare.bench.SETTINGS)
    settings["profiles"]["deepseek"]["model"] = "different"
    compare.pilot.write_json(compare.bench.SETTINGS, settings)
    with pytest.raises(ValueError, match="provider changed"):
        compare.review("comparison", "deepseek")
    with pytest.raises(ValueError, match="provider changed"):
        compare.init_generation("comparison")
    assert not sdk.called


def test_authentication_failure_does_not_spend_remaining_cases(comparison):
    from openai import AuthenticationError

    root, sdk = comparison
    sdk.return_value.chat.completions.create.side_effect = AuthenticationError(
        "not authorized", response=MagicMock(status_code=401), body=None)
    compare.review("comparison", "deepseek")
    assert sdk.return_value.chat.completions.create.call_count == 1
    ledger = compare.pilot.read_json(root / "runtime/sessions/comparison-deepseek-case01-generation/dialogue.json")
    assert ledger["turns"][0]["status"] == "failed"
    assert ledger["turns"][0]["calls"][0]["status_code"] == 401


def test_invalid_answer_is_retained_without_retry(comparison):
    root, sdk = comparison
    sdk.return_value.chat.completions.create.return_value.choices[0].message.content = "invalid JSON"
    compare.review("comparison", "mimo")
    compare.review("comparison", "mimo")
    assert sdk.return_value.chat.completions.create.call_count == 2
    assert (root / "runtime/sessions/comparison-mimo-case01-generation/dialogue-01-reply.txt").read_text() == "invalid JSON"
