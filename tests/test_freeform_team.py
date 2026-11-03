import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from manimind.experiments import freeform_team as module
from manimind.experiments import freeform_review_cycle
from manimind.experiments.freeform_team import TeamExperiment, ProviderStopped
from test_freeform_max_effort import fake_provider


@pytest.fixture
def team(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    value = TeamExperiment.__new__(TeamExperiment)
    value.id = "fresh-team"
    value.out = tmp_path / "outputs/fresh-team"
    value.context = tmp_path / "runtime/projects/fresh-team"
    value.session = tmp_path / "runtime/sessions/fresh-team-generation"
    value.spec_path = value.out / "spec.json"
    value.config_path = tmp_path / "config.json"
    value.config = json.loads((module.ROOT / "configs/deepseek-team-20261023.json").read_text())
    value.config["project_id"] = value.id
    value.config_path.write_text(json.dumps(value.config))
    monkeypatch.setattr(value, "frozen_paths", lambda: [value.config_path])
    value.initialize()
    value.team = module.pilot.read_json(value.team_path)
    value.current_step = value.session / "test-step"
    value.current_step.mkdir()
    return value


def test_fresh_three_role_initialization_is_idempotent(team):
    before = team.team_path.read_bytes()
    team.initialize()
    assert before == team.team_path.read_bytes()
    assert not team.spec_path.exists()
    assert not (team.out / "candidate.py").exists()
    assert not team.cycle_path.exists()
    assert team.team["active_role"] == "director"
    assert len({team.role_directory(r) for r in module.SYSTEMS}) == 3
    assert all(team.role_directory(r).is_dir() for r in module.SYSTEMS)
    team.verify()


@pytest.mark.parametrize("role", ["director", "creator", "reviewer"])
def test_all_roles_send_max_reasoning_without_sdk_retries(team, monkeypatch, role):
    calls = fake_provider(monkeypatch)
    raw, directory = team.role_request(role, "team-0001", "Public JSON task", [])
    assert len(calls) == 1 and json.loads(raw)["action"] == "review"
    assert calls[0]["reasoning_effort"] == "max"
    assert calls[0]["extra_body"] == {"thinking": {"type": "enabled"}}
    assert calls[0]["messages"][0]["content"] == module.SYSTEMS[role]
    assert len(calls[0]["messages"]) == 2
    record = module.pilot.read_json(directory / "record.json")
    assert record["role"] == role and record["status"] == "received"
    assert record["usage"][0]["cached_tokens"] == 20
    assert "test-only-never-persist" not in (directory / "input.json").read_text()
    assert "private" not in (directory / "answer.txt").read_text()


def test_contexts_preserve_role_boundaries_and_public_input(team):
    team.team["actors"]["director"]["history"] = [{"notes": "DIRECTOR-PRIVATE"}]
    team.team["actors"]["creator"]["history"] = [{"notes": "CREATOR-PRIVATE"}]
    assert "DIRECTOR-PRIVATE" not in team.actor_context("creator")
    assert "CREATOR-PRIVATE" not in team.actor_context("director")
    assert "projectile-story-20261020" not in team.actor_context("director")
    module.pilot.write_json(team.out / "timeline.json", {"duration": 10, "cues": [
        {"id": "a", "spoken": "CURRENT NARRATION", "start": 0, "duration": 10,
         "author_assessment": "DO NOT SHARE"}]})
    (team.out / "candidate.py").write_text("class GeneratedLesson: pass")
    review = team.reviewer_context()
    assert "CURRENT NARRATION" in review
    assert all(x not in review for x in ["DIRECTOR-PRIVATE", "CREATOR-PRIVATE", "DO NOT SHARE"])


def test_delegation_and_handoff_retain_exact_message(team):
    state = module.pilot.read_json(team.state_path)
    for role, action, target in [("director", "delegate", "creator"), ("creator", "handoff", "director")]:
        message = "Original instructions. No coordinator edits."
        result = team.dispatch_role(role, {"action": action, "args": {"message": message}}, state)
        assert team.team["active_role"] == target
        assert team.team["actors"][target]["incoming"][-1]["message"] == message
        assert result["message_unchanged"]


@pytest.mark.parametrize("role,action", [("director", "write_code"), ("director", "replace_code"),
                                        ("creator", "request_review"), ("creator", "finish")])
def test_role_permissions_cannot_bypass_ownership(team, role, action):
    with pytest.raises(ValueError, match="not available"):
        team.dispatch_role(role, {"action": action}, {})


def test_new_media_invalidates_both_roles_and_approval(team):
    state = module.pilot.read_json(team.state_path)
    for actor in team.team["actors"].values():
        actor.update(observed=["a"], images=["frame"], pending_cues=["a"])
    team.team["approval_current"] = True
    team.invalidate(state)
    assert not team.team["approval_current"]
    assert all(not a["observed"] and not a["images"] for a in team.team["actors"].values())


def test_director_must_make_own_current_frame_observations(team):
    module.pilot.write_json(team.out / "timeline.json", {"cues": [{"id": "a"}]})
    module.pilot.write_json(team.out / "review-input.json", {})
    team.team["actors"]["creator"]["observed"] = ["a"]
    state = {"latest_render": {"tool_success": True, "success": True}, "observed": ["a"]}
    with pytest.raises(ValueError, match="observations missing"):
        team.dispatch_role("director", {"action": "request_review"}, state)
    assert team.team["cycle"] == 0


def test_external_images_and_truncated_responses_are_not_used(team, monkeypatch, tmp_path):
    calls = fake_provider(monkeypatch, finish="length")
    image = tmp_path / "old.jpg"
    image.write_bytes(b"old")
    with pytest.raises(ValueError, match="Only this experiment"):
        team.role_request("director", "test", "JSON", [image])
    assert not calls
    with pytest.raises(ProviderStopped):
        team.role_request("director", "test", "JSON", [])
    assert len(calls) == 1
    assert module.pilot.read_json(team.role_requests("director")[0])["status"] == "failed"


def test_costs_include_all_roles_failures_and_unknown_usage(team):
    for role in module.SYSTEMS:
        directory = team.role_directory(role) / "request-0001"
        directory.mkdir()
        module.pilot.write_json(directory / "record.json", {"elapsed_seconds": 2, "usage": [] if
            role == "reviewer" else [{"prompt_tokens": 1000, "completion_tokens": 200, "cached_tokens": 500}]})
    team.report()
    first = module.pilot.read_json(team.out / "cost-report.json")
    team.report()
    assert first == module.pilot.read_json(team.out / "cost-report.json")
    assert first["calls"] == 3 and first["unknown_usage_requests"] == 1
    assert first["known_peak_uncached_estimate_CNY"] == pytest.approx(.0072)
    assert first["request_elapsed_seconds"] == 6


def test_inflight_blocks_duplicate_billing(team, monkeypatch):
    calls = fake_provider(monkeypatch)
    team.team["inflight"] = {"phase": "tool"}
    team.save_team()
    with pytest.raises(ValueError, match="Unresolved"):
        team.run_team()
    assert not calls


def test_completed_request_recovery_does_not_call_provider_again(team, monkeypatch):
    calls = fake_provider(monkeypatch)
    text = team.actor_context("director")
    raw, directory = team.role_request("director", "team-0001", text, [])
    team.team["inflight"] = {"phase": "request", "turn": 1, "role": "director"}
    assert team.received_checkpoint() == (raw, directory)
    assert len(calls) == 1
    team.team["actors"]["director"]["history"].append({"notes": "changed"})
    with pytest.raises(ValueError, match="context changed"):
        team.received_checkpoint()


def approved_candidate(team, monkeypatch):
    frame = team.out / "frame.jpg"
    frame.write_bytes(b"actual fixture frame")
    evidence = {"hashes": {"source": "current"}, "video_path": str(team.out / "raw.mp4"),
                "duration": 10, "cue_ids": ["a"],
                "frames": [{"cue": "a", "time": 1., "path": str(frame), "sha256": module.pilot.sha256(frame)}]}
    module.pilot.write_json(team.out / "review-input.json", evidence)
    module.pilot.write_json(team.out / "timeline.json", {"duration": 10, "cues": [
        {"id": "a", "start": 0, "duration": 10}]})
    value = {"action": "review", "status": "pass", "checks": {k: "pass" for k in freeform_review_cycle.CHECKS},
             "inspected_cues": [{"id": "a", "observations": [{"time": 1., "detail": "Visible fixture"}]}],
             "issues": [], "limitations": ["Sampled frames only"]}
    request = team.review_session / "request-0001"
    request.mkdir()
    module.pilot.write_json(request / "answer.txt", value)
    module.pilot.write_json(request / "input.json", {"images": [evidence["frames"][0]]})
    module.pilot.write_json(request / "record.json", {"role": "reviewer", "status": "received",
        "input_sha256": module.pilot.sha256(request / "input.json"),
        "answer_sha256": module.pilot.sha256(request / "answer.txt")})
    judgment = {"request": str(request), "answer_sha256": module.pilot.sha256(request / "answer.txt"), "review": value}
    cycle = team.review_session / "cycle-01"
    cycle.mkdir()
    module.pilot.write_json(cycle / "evidence.json", evidence)
    report = {"status": "pass", "cycle": 1, "hashes": evidence["hashes"], "segments": [judgment],
              "whole": judgment, "inspected_frames": [str(frame)], "limitations": ["Not audio reviewed"],
              "evidence_sha256": module.pilot.sha256(cycle / "evidence.json")}
    module.pilot.write_json(cycle / "report.json", report)
    team.team.update(review_path=str(cycle / "report.json"), review_sha256=module.pilot.sha256(cycle / "report.json"))
    assemblies = []
    def assemble():
        assemblies.append(True)
        (team.out / "projectile-story.mp4").write_bytes(b"fixture video")
    monkeypatch.setattr(module.media, "Production", lambda path: SimpleNamespace(
        hashes=lambda video: {"source": "current"}, assemble=assemble))
    return report, assemblies


def test_release_requires_independent_review(team):
    with pytest.raises(ValueError, match="Independent review required"):
        team.release()


def test_release_translates_real_verdict_without_semantic_edits(team, monkeypatch):
    report, assemblies = approved_candidate(team, monkeypatch)
    team.release()
    approved = module.pilot.read_json(team.context / "review.json")
    assert approved["checks"] == report["whole"]["review"]["checks"]
    assert approved["origin"]["mechanical_translation"] == "pass to approved, no semantic edits"
    assert assemblies == [True] and team.team["status"] == "complete"


@pytest.mark.parametrize("change", ["revise", "stale", "forged", "unseen", "pixels"])
def test_release_rejects_failed_stale_or_unproven_approval(team, monkeypatch, change):
    report, assemblies = approved_candidate(team, monkeypatch)
    if change == "revise": report["status"] = "revise"
    if change == "stale": report["hashes"] = {"source": "old"}
    if change == "forged": report["whole"]["review"]["limitations"] = ["Altered verdict"]
    if change == "unseen": module.pilot.write_json(team.review_session / "request-0001/input.json", {"images": []})
    if change == "pixels": (team.out / "frame.jpg").write_bytes(b"different pixels")
    module.pilot.write_json(Path(team.team["review_path"]), report)
    team.team["review_sha256"] = module.pilot.sha256(Path(team.team["review_path"]))
    with pytest.raises(ValueError): team.release()
    assert not assemblies


def test_three_role_routing_can_run_to_model_stop_without_real_api(team, monkeypatch):
    commands = [
        ("director", {"action": "delegate", "args": {"message": "Original delegation"}}),
        ("creator", {"action": "handoff", "args": {"message": "Original report"}}),
        ("director", {"action": "stop", "args": {"reason": "Fixture complete"}}),
    ]
    def request(role, stage, text, images):
        expected, command = commands.pop(0)
        assert role == expected
        directory = team.role_directory(role) / stage
        directory.mkdir()
        raw = json.dumps(command)
        (directory / "answer.txt").write_text(raw)
        return raw, directory
    monkeypatch.setattr(team, "role_request", request)
    team.run_team()
    state = module.pilot.read_json(team.team_path)
    assert state["turn"] == 3 and state["status"] == "model_stopped"
    assert not state["inflight"] and not (team.session / "team.lock").exists()
