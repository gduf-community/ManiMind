import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from manimind.experiments import learning_runtime as module


def test_native_import_sees_no_orchestrator_options(monkeypatch):
    original = ["runner", "--study", "study.json", "--case", "a"]
    monkeypatch.setattr(sys, "argv", original)
    seen = []
    monkeypatch.setattr(module.importlib, "import_module", lambda name: seen.append((name, sys.argv[:])))
    module.preload_runtime()
    assert seen == [("manimlib", ["runner"])]
    assert sys.argv is original


def test_import_failure_also_restores_cli(monkeypatch):
    original = ["runner", "--profile", "v1.json"]
    monkeypatch.setattr(sys, "argv", original)
    def fail(name): raise RuntimeError("Import failure")
    monkeypatch.setattr(module.importlib, "import_module", fail)
    with pytest.raises(RuntimeError): module.preload_runtime()
    assert sys.argv is original


@pytest.fixture
def checkpoint(tmp_path):
    pilot = module.pilot
    session = tmp_path / "session"
    out = tmp_path / "out"
    step = session / "team-step-0001"
    request = session / "request-0001"
    spec = out / "spec.json"
    pilot.write_json(spec, {"original": True})
    command = {"action": "read_api", "args": {"symbols": ["Arrow"]},
               "notes": "Original note", "observations": []}
    pilot.write_json(request / "input.json", {"original": "context"})
    pilot.write_json(request / "answer.txt", command)
    pilot.write_json(request / "record.json", {
        "status": "received", "role": "creator", "stage": "team-0001",
        "input_sha256": pilot.sha256(request / "input.json"),
        "answer_sha256": pilot.sha256(request / "answer.txt")})
    pilot.write_json(step / "command.json", {"role": "creator", "request": str(request),
        "answer_sha256": pilot.sha256(request / "answer.txt"), "command": command})
    path = session / "team-state.json"
    pilot.write_json(path, {"status": "interrupted", "turn": 0,
        "inflight": {"phase": "tool", "turn": 1, "role": "creator", "step": str(step)},
        "actors": {"creator": {"history": []}}, "tool_durations": []})
    value = SimpleNamespace(session=session, out=out, spec_path=spec, team_path=path,
        verify=lambda: None, role_directory=lambda role: session, report=lambda: None)
    value.save_team = lambda: pilot.write_json(path, value.team)
    return value


def test_readonly_recovery_keeps_originals_and_cannot_repeat(checkpoint, monkeypatch):
    before = module.pilot.sha256(checkpoint.spec_path)
    called = []
    monkeypatch.setattr(module, "api_reference", lambda symbols: called.append(symbols) or ["native API"])
    module.recover_read_api(checkpoint)
    assert called == [["Arrow"]]
    assert module.pilot.sha256(checkpoint.spec_path) == before
    assert checkpoint.team["turn"] == 1 and checkpoint.team["inflight"] is None
    receipt = module.pilot.read_json(checkpoint.session / "team-step-0001/readonly-recovery.json")
    assert receipt["provider_called"] is False
    with pytest.raises(ValueError): module.recover_read_api(checkpoint)
    assert called == [["Arrow"]]


def test_unknown_side_effect_tool_is_never_replayed(checkpoint, monkeypatch):
    path = checkpoint.session / "team-step-0001/command.json"
    data = module.pilot.read_json(path)
    data["command"]["action"] = "render"
    module.pilot.write_json(path, data)
    monkeypatch.setattr(module, "api_reference", lambda symbols: pytest.fail("Must not run"))
    with pytest.raises(ValueError, match="original read_api"):
        module.recover_read_api(checkpoint)


def test_active_lock_or_modified_request_blocks_recovery(checkpoint, monkeypatch):
    lock = checkpoint.session / "team.lock"
    lock.write_text("existing")
    monkeypatch.setattr(module, "api_reference", lambda symbols: pytest.fail("Must not run"))
    with pytest.raises(ValueError, match="lock"):
        module.recover_read_api(checkpoint)
    lock.unlink()
    (checkpoint.session / "request-0001/input.json").write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        module.recover_read_api(checkpoint)


def test_query_validation_error_is_preserved_as_raw_tool_result(checkpoint, monkeypatch):
    def fail(symbols): raise ValueError("Original tool validation message")
    monkeypatch.setattr(module, "api_reference", fail)
    module.recover_read_api(checkpoint)
    result = module.pilot.read_json(checkpoint.session / "team-step-0001/result.json")
    assert result == {"error_type": "ValueError", "raw_error": "Original tool validation message"}
