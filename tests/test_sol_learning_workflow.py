import json
from pathlib import Path

import pytest

from manimind.experiments import codex_cli_team, freeform_review_cycle
from manimind.experiments import sol_learning_workflow as module
from manimind.experiments.freeform_team import TeamExperiment
from manimind.postproduce import pilot


@pytest.fixture
def sol(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    value = module.SolLearningWorkflow.__new__(module.SolLearningWorkflow)
    value.id = "test-sol-learning"
    value.out = tmp_path / "outputs" / value.id
    value.context = tmp_path / "runtime/projects" / value.id
    value.session = tmp_path / "runtime/sessions" / f"{value.id}-generation"
    value.spec_path = value.out / "spec.json"
    value.config_path = tmp_path / "sol.json"
    value.config = pilot.read_json(pilot.ROOT / "configs/sol61-team-20261023.json")
    value.config.update(project_id=value.id, workflow_profile=str(pilot.ROOT / "configs/learning-workflow-v1.json"))
    pilot.write_json(value.config_path, value.config)
    monkeypatch.setattr(value, "frozen_paths", lambda: [value.config_path])
    value.initialize()
    value.team = pilot.read_json(value.team_path)
    return value


def test_sol_uses_both_learning_gate_and_native_transport(sol):
    assert module.SolLearningWorkflow.__mro__.index(module.LearningWorkflow) < module.SolLearningWorkflow.__mro__.index(module.CodexTeamExperiment)
    protocol = sol.protocol()
    assert protocol["model"] == "gpt-6.1-sol"
    assert protocol["reasoning_effort"] == "max"
    assert protocol["workflow_profile"]["evaluation"]["minimum_total"] == 80
    assert "DeepSeek" not in sol.actor_context("creator")
    assert "FROZEN GENERIC WORKFLOW" in sol.actor_context("creator")
    sol.verify()
    assert not any(sol.role_requests(r) for r in codex_cli_team.SYSTEMS)


def test_learning_role_request_dispatches_to_sol_not_deepseek(sol, monkeypatch):
    calls = []
    monkeypatch.setattr(TeamExperiment, "role_request", lambda *a: pytest.fail("DeepSeek transport called"))
    monkeypatch.setattr(codex_cli_team.CodexTeamExperiment, "role_request",
                        lambda self, role, stage, text, images: calls.append((role, text)) or ("{}", Path("request")))
    sol.role_request("reviewer", "whole", "Cold view", [])
    assert calls[0][0] == "reviewer"
    assert "viewer_test" in calls[0][1]


def test_legacy_launcher_cannot_silently_bypass_learning_gates(sol):
    with pytest.raises(ValueError, match="sol_learning_workflow"):
        sol.launch_background()


def test_sol_received_answer_can_resume_without_rebilling(sol):
    directory = sol.role_directory("director") / "request-0001"
    directory.mkdir()
    pilot.write_json(directory / "input.json", {
        "text": sol.actor_context("director"), "system": codex_cli_team.native_system("director"), "images": []})
    (directory / "answer.txt").write_text('{"action":"read_api","args":{"symbols":["Dot"]}}')
    pilot.write_json(directory / "record.json", {
        "stage": "team-0001", "status": "received", "role": "director",
        "answer_sha256": pilot.sha256(directory / "answer.txt"),
        "input_sha256": pilot.sha256(directory / "input.json")})
    sol.team["inflight"] = {"turn": 1, "role": "director", "phase": "request"}
    answer, found = sol.received_checkpoint()
    assert found == directory and json.loads(answer)["action"] == "read_api"
    data = pilot.read_json(directory / "input.json")
    data["system"] = "Foreign role system"
    pilot.write_json(directory / "input.json", data)
    record = pilot.read_json(directory / "record.json")
    record["input_sha256"] = pilot.sha256(directory / "input.json")
    pilot.write_json(directory / "record.json", record)
    with pytest.raises(ValueError, match="context changed"):
        sol.received_checkpoint()


def test_sol_study_keeps_same_public_cases_but_no_deepseek_state():
    data = pilot.read_json(pilot.ROOT / "configs/workflow-sol61-20261023.json")
    previous = pilot.read_json(pilot.ROOT / "configs/workflow-study-20261023.json")
    assert data["cases"] == previous["cases"]
    assert data["study_id"] != previous["study_id"]
    assert data["provider_config"] == "configs/sol61-team-20261023.json"


def test_quota_baseline_is_captured_once_and_closed(sol, monkeypatch):
    closed = []

    class Reader:
        def __init__(self, directory):
            assert directory == sol.session

        def read(self):
            return {"used_percent": 17, "resets_at": 123}

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module, "RateReader", Reader)
    module.capture_baseline(sol)
    module.capture_baseline(sol)
    assert closed == [True]
    assert pilot.read_json(sol.context / "quota-snapshots.json")["snapshots"][0]["used_percent"] == 17
