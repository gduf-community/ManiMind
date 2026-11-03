from types import SimpleNamespace

import pytest

from manimind.experiments import learning_background as module
from manimind.postproduce import pilot


@pytest.fixture
def runner(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    pilot.write_json(config, {})
    pilot.write_json(tmp_path / "profile.json", {"version": "v2"})
    session = tmp_path / "session"
    session.mkdir()
    state = session / "team-state.json"
    pilot.write_json(state, {"status": "ready", "inflight": None})
    value = SimpleNamespace(initialize=lambda: None, session=session, team_path=state)
    monkeypatch.setattr(module, "prepare_case", lambda *args: config)
    monkeypatch.setattr(module, "SolLearningV2", lambda path: value)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: calls.append((a, k)) or SimpleNamespace(pid=12345))
    return value, calls, (tmp_path / "study.json", tmp_path / "profile.json", "case")


def test_launcher_uses_sol_v2_and_refuses_duplicate_live_runner(runner, monkeypatch):
    value, calls, args = runner
    result = module.launch(*args)
    assert result["pid"] == 12345
    assert "manimind.experiments.sol_learning_v2" in calls[0][0][0]
    assert calls[0][1]["start_new_session"]
    assert result["launcher_sha256"]
    monkeypatch.setattr(module.os, "kill", lambda *args: None)
    with pytest.raises(ValueError, match="alive"):
        module.launch(*args)
    assert len(calls) == 1 and not (value.session / "launch.lock").exists()


@pytest.mark.parametrize("status,inflight,locked", [
    ("running", {"phase": "request"}, False), ("complete", None, False), ("ready", None, True)])
def test_pending_terminal_or_active_runs_never_launch(runner, status, inflight, locked):
    value, calls, args = runner
    pilot.write_json(value.team_path, {"status": status, "inflight": inflight})
    if locked:
        (value.session / "team.lock").touch()
    with pytest.raises(ValueError, match="clean, unlocked"):
        module.launch(*args)
    assert not calls


def test_launcher_does_not_remove_another_operators_launch_lock(runner):
    value, calls, args = runner
    lock = value.session / "launch.lock"
    lock.touch()
    with pytest.raises(FileExistsError):
        module.launch(*args)
    assert lock.exists() and not calls


def test_v3_launcher_cannot_accidentally_use_the_v2_engine(runner, monkeypatch):
    value, calls, args = runner
    pilot.write_json(args[1], {"version": "v3"})
    with pytest.raises(ValueError, match="must match"):
        module.launch(*args)
    monkeypatch.setattr(module, "SolLearningV3", lambda path: value)
    result = module.launch(*args, engine="sol-v3")
    assert result["engine"] == "sol-v3"
    assert "manimind.experiments.sol_learning_v3" in calls[0][0][0]
