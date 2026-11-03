import json
from pathlib import Path

import pytest

from manimind.experiments import learning_workflow as module
from manimind.experiments.freeform_team import TeamExperiment
from manimind.postproduce import pilot


@pytest.fixture
def study(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    original = pilot.ROOT
    provider = tmp_path / "provider.json"
    provider.write_bytes((original / "configs/deepseek-team-20261023.json").read_bytes())
    profile = tmp_path / "profile.json"
    profile.write_bytes((original / "configs/learning-workflow-v1.json").read_bytes())
    path = tmp_path / "study.json"
    data = pilot.read_json(original / "configs/workflow-study-20261023.json")
    data["provider_config"] = "provider.json"
    pilot.write_json(path, data)
    return path, profile


def test_case_context_contains_only_one_public_task(study):
    path, profile = study
    config_path = module.prepare_case(path, "projectile", profile)
    data = pilot.read_json(config_path)
    assert data["study_case"] == "projectile"
    assert "conditional" not in json.dumps(data["brief"])
    assert "parallel" not in json.dumps(data["brief"])
    before = config_path.read_bytes()
    module.prepare_case(path, "projectile", profile)
    assert config_path.read_bytes() == before


def test_changed_protocol_or_profile_cannot_overwrite_an_attempt(study):
    path, profile = study
    module.prepare_case(path, "projectile", profile)
    data = pilot.read_json(profile)
    data["author_guidance"].append("A change")
    pilot.write_json(profile, data)
    # The new config points to the same profile path; the actual run's frozen
    # profile hash is checked separately by protocol/frozen_paths.
    config_path = module.prepare_case(path, "projectile", profile)
    assert config_path.exists()
    data = pilot.read_json(path)
    data["cases"][0]["brief"]["goal"] = "Changed question"
    pilot.write_json(path, data)
    with pytest.raises(ValueError, match="study changed"):
        module.prepare_case(path, "projectile", profile)


def test_holdout_is_unavailable_before_development_freeze(study):
    path, profile = study
    with pytest.raises(FileNotFoundError):
        module.prepare_case(path, "parallel", profile)
    with pytest.raises(FileNotFoundError):
        module.freeze_holdout(path, profile)


def test_cold_view_excludes_source_and_narration(tmp_path):
    value = module.LearningWorkflow.__new__(module.LearningWorkflow)
    value.out = tmp_path
    value.config = {"brief": {"audience": "Students", "goal": "Understand a mechanism"}}
    pilot.write_json(tmp_path / "timeline.json", {"duration": 10, "cues": [{
        "id": "a", "start": 0, "duration": 10, "spoken": "AUTHOR NARRATION"}]})
    (tmp_path / "candidate.py").write_text("AUTHOR SOURCE")
    result = value.reviewer_context()
    assert "AUTHOR NARRATION" not in result and "AUTHOR SOURCE" not in result
    assert "Understand a mechanism" in result


def test_role_profile_is_part_of_recoverable_actor_context(tmp_path, monkeypatch):
    value = module.LearningWorkflow.__new__(module.LearningWorkflow)
    value.config = {"workflow_profile": str(tmp_path / "profile.json")}
    pilot.write_json(tmp_path / "profile.json", {"version": "test-profile"})
    monkeypatch.setattr(TeamExperiment, "actor_context", lambda self, role: "OWN CONTEXT")
    assert "test-profile" in value.actor_context("creator")


def test_old_frozen_implementation_is_not_edited():
    source = Path(module.__file__).read_text()
    assert "class LearningWorkflow(TeamExperiment)" in source
    assert "candidate_source" not in module.LearningWorkflow.reviewer_context.__code__.co_consts


def test_source_audit_cannot_override_cold_view_rejection(tmp_path, monkeypatch):
    from manimind.experiments.freeform_review_cycle import ReviewCycleExperiment
    value = module.LearningWorkflow.__new__(module.LearningWorkflow)
    value.out = tmp_path / "out"
    value.session = tmp_path / "session"
    value.config = {"workflow_profile": str(tmp_path / "profile.json")}
    pilot.write_json(tmp_path / "profile.json", {"version": "v1"})
    pilot.write_json(value.state_path, {})
    pilot.write_json(value.out / "review-input.json", {
        "cue_ids": ["a"], "frames": [{"path": "frame.jpg"}], "subtitle_audit": {"blockers": []}})
    path = tmp_path / "review.json"
    cold = {"segments": [{"review": {"status": "pass"}}],
            "whole": {"review": {"status": "revise"}}, "status": "revise"}
    monkeypatch.setattr(TeamExperiment, "independent_review", lambda self, cycle: (path, cold))
    monkeypatch.setattr(ReviewCycleExperiment, "reviewer_context", lambda self: "SOURCE AUDIT")
    monkeypatch.setattr(value, "review_batch", lambda *args: {"review": {"status": "pass"}})
    _, report = value.independent_review(1)
    assert report["status"] == "revise"
    assert report["segments"][-1]["review"]["status"] == "revise"
    assert report["whole"]["review"]["status"] == "pass"


def test_low_score_profile_cannot_relax_the_study_rubric(tmp_path, monkeypatch):
    value = module.LearningWorkflow.__new__(module.LearningWorkflow)
    value.config = {"workflow_profile": str(tmp_path / "profile.json")}
    data = pilot.read_json(pilot.ROOT / "configs/learning-workflow-v1.json")
    data["evaluation"]["minimum_total"] = 50
    pilot.write_json(tmp_path / "profile.json", data)
    monkeypatch.setattr(TeamExperiment, "protocol", lambda self: {})
    with pytest.raises(ValueError, match="fixed across"):
        value.protocol()


def test_changed_temporal_sheet_blocks_release(tmp_path, monkeypatch):
    value = module.LearningWorkflow.__new__(module.LearningWorkflow)
    value.out = tmp_path / "out"
    value.config = {"workflow_profile": str(tmp_path / "profile.json")}
    pilot.write_json(tmp_path / "profile.json", {"version": "v1"})
    frame = tmp_path / "sheet.jpg"
    frame.write_bytes(b"changed pixels")
    pilot.write_json(value.out / "review-input.json", {
        "workflow_profile_sha256": pilot.sha256(tmp_path / "profile.json"),
        "subtitle_audit": {"blockers": []},
        "temporal_evidence": [{"frames": [], "sheets": [{"path": str(frame), "sha256": "old"}]}]})
    called = []
    monkeypatch.setattr(TeamExperiment, "release", lambda self: called.append(True))
    with pytest.raises(ValueError, match="Temporal review pixels"):
        value.release()
    assert not called
