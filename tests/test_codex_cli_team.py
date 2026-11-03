import json
from pathlib import Path

import pytest

from manimind.experiments import codex_cli_team as module
from manimind.experiments import freeform_review_cycle


@pytest.fixture
def native(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    value = module.CodexTeamExperiment.__new__(module.CodexTeamExperiment)
    value.id = "test-sol"
    value.out = tmp_path / "outputs/test-sol"
    value.context = tmp_path / "runtime/projects/test-sol"
    value.session = tmp_path / "runtime/sessions/test-sol-generation"
    value.spec_path = value.out / "spec.json"
    value.config_path = tmp_path / "sol.json"
    value.config = json.loads((module.ROOT / "configs/sol61-team-20261023.json").read_text())
    value.config["project_id"] = value.id
    value.config_path.write_text(json.dumps(value.config))
    monkeypatch.setattr(value, "frozen_paths", lambda: [value.config_path])
    value.initialize()
    value.team = module.pilot.read_json(value.team_path)
    return value


def test_native_role_contracts_only_change_identity(native):
    assert "GPT-6.1 Sol" in native.protocol()["systems"]["director"]
    assert "DeepSeek" not in native.actor_context("director")
    assert not native.protocol()["native_memory"]
    native.verify()
    assert not any(native.role_requests(r) for r in module.SYSTEMS)


def test_public_brief_is_identical_to_comparison():
    sol = module.pilot.read_json(module.ROOT / "configs/sol61-team-20261023.json")
    other = module.pilot.read_json(module.ROOT / "configs/deepseek-team-20261023.json")
    assert sol["brief"] == other["brief"]


def test_cli_does_not_inherit_chat_project_memory_or_native_tools(tmp_path):
    command = module.cli_command("codex", tmp_path, "Role\nquoted \"text\"", [tmp_path / "a.png"])
    assert command[command.index("--model") + 1] == "gpt-6.1-sol"
    assert "--ephemeral" in command and "--ignore-user-config" in command
    assert "project_doc_max_bytes=0" in command
    assert 'model_reasoning_effort="max"' in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "shell_tool" in command and "memories" in command and "plugins" in command
    assert command[-1] == "-"


def test_usage_parser_requires_successful_single_turn_and_no_tools(tmp_path):
    path = tmp_path / "events.jsonl"
    events = [{"type": "thread.started", "thread_id": "fresh"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
              {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20}}]
    path.write_text("\n".join(json.dumps(e) for e in events))
    usage, thread = module.read_events(path)
    assert usage["cached_tokens"] == 60 and thread == "fresh"
    events.insert(1, {"type": "item.completed", "item": {"type": "error", "message": "Configuration warning"}})
    path.write_text("\n".join(json.dumps(e) for e in events))
    assert module.read_events(path)[0]["prompt_tokens"] == 100
    events.insert(1, {"type": "item.completed", "item": {"type": "command_execution"}})
    path.write_text("\n".join(json.dumps(e) for e in events))
    with pytest.raises(ValueError, match="outside"):
        module.read_events(path)


def test_subscription_report_counts_all_roles_and_flags_unknown(native):
    for role in module.SYSTEMS:
        directory = native.role_directory(role) / "request-0001"
        directory.mkdir()
        module.pilot.write_json(directory / "record.json", {"usage": [] if role == "reviewer" else [
            {"prompt_tokens": 1000, "cached_tokens": 800, "completion_tokens": 100}]})
    native.report()
    data = module.pilot.read_json(native.out / "cost-report.json")
    assert data["calls"] == 3 and data["unknown_usage_requests"] == 1
    assert data["standard_credit_rate_equivalent"] == pytest.approx(.074)
    assert "CNY" not in data


def test_foreign_images_are_rejected_before_native_process(native, tmp_path):
    image = tmp_path / "old.png"
    image.write_bytes(b"old")
    with pytest.raises(ValueError, match="current-project"):
        native.role_request("director", "test", "JSON", [image])
    assert not native.role_requests("director")


def test_background_launcher_refuses_live_process(native, monkeypatch):
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: calls.append((a,k)) or SimpleNamespace(pid=12345))
    monkeypatch.setattr(module.os, "kill", lambda pid, sig: None)
    result = native.launch_background()
    assert result["pid"] == 12345
    assert calls[0][1]["start_new_session"]
    with pytest.raises(ValueError, match="still alive"):
        native.launch_background()
    assert len(calls) == 1
    assert not (native.session / "launch.lock").exists()
