import json
from types import SimpleNamespace

import pytest

from manimind.experiments import deepseek_learning_v3 as module
from manimind.experiments import freeform_review_cycle
from manimind.experiments.codex_cli_team import CodexTeamExperiment
from manimind.experiments.freeform_team import TeamExperiment
from manimind.experiments.learning_workflow import LearningWorkflow
from manimind.postproduce import pilot
from manimind.review.learning_quality import DIMENSIONS


@pytest.fixture
def value(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    item = module.DeepSeekLearningV3.__new__(module.DeepSeekLearningV3)
    item.id = "test-deepseek-high"
    item.out = tmp_path / "outputs" / item.id
    item.context = tmp_path / "runtime/projects" / item.id
    item.session = tmp_path / "runtime/sessions" / f"{item.id}-generation"
    item.spec_path = item.out / "spec.json"
    item.config_path = tmp_path / "provider.json"
    item.config = pilot.read_json(pilot.ROOT / "configs/deepseek-learning-high-20261024.json")
    item.config["workflow_profile"] = str(pilot.ROOT / "configs/learning-workflow-v3.json")
    item.config["brief"] = pilot.read_json(pilot.ROOT / "configs/workflow-deepseek-high-20261024.json")["cases"][0]["brief"]
    pilot.write_json(item.config_path, item.config)
    monkeypatch.setattr(item, "frozen_paths", lambda: [item.config_path])
    item.initialize()
    item.team = pilot.read_json(item.team_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-never-persist")
    return item


def test_same_public_task_profile_and_exact_review_algorithms(value):
    sol = pilot.read_json(pilot.ROOT / "configs/workflow-sol61-20261023.json")
    assert value.config["brief"] == sol["cases"][0]["brief"]
    assert value.profile == pilot.read_json(pilot.ROOT / "configs/learning-workflow-v3.json")
    assert CodexTeamExperiment not in type(value).__mro__
    assert type(value).review_batch is module.SolLearningV2.review_batch
    assert type(value).independent_review is module.SolLearningV3.independent_review
    context = value.actor_context("director")
    payload = json.loads(context.split("\n", 1)[0])
    assert payload["own_history"] == payload["team_messages_to_you"] == []
    assert "current_team_source" not in payload and "current_team_plan" not in payload
    assert "maximum-thinking" not in context and "high-thinking" in context
    assert value.protocol()["reasoning_effort"] == "high"


@pytest.mark.parametrize("field,changed", [
    ("reasoning_effort", "max"), ("reasoning_effort", "low"),
    ("thinking", {"type": "disabled"}), ("max_requests", 4),
    ("seed_config", "an-old-run.json"), ("base_url", "https://example.test/v1"),
    ("model", "deepseek-v4-pro")])
def test_wrong_effort_seed_caps_or_provider_are_refused(value, field, changed):
    value.config[field] = changed
    with pytest.raises(ValueError):
        value.validate_config()


def install_transport(monkeypatch, answer, calls, fail=False):
    from manimind.llm import client

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            if fail:
                raise ConnectionError("Synthetic disconnect")
            usage = SimpleNamespace(model_dump=lambda: {
                "prompt_tokens": 100, "completion_tokens": 30, "prompt_cache_hit_tokens": 40})
            yield SimpleNamespace(model="deepseek-flash", usage=usage, choices=[SimpleNamespace(
                delta=SimpleNamespace(content=json.dumps(answer), reasoning_content="synthetic"), finish_reason="stop")])

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            calls.append(kwargs)
            return Stream()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(client, "OpenAI", Client)


@pytest.mark.parametrize("role", ["director", "creator", "reviewer"])
def test_actual_transport_explicitly_uses_high_for_every_role(value, monkeypatch, role):
    calls = []
    install_transport(monkeypatch, {"action": "stop", "args": {}}, calls)
    _, directory = value.role_request(role, "test", "CURRENT PUBLIC CONTEXT", [])
    assert len(calls) == 1 and calls[0]["reasoning_effort"] == "high"
    assert len(calls[0]["messages"]) == 2
    assert calls[0]["extra_body"] == {"thinking": {"type": "enabled"}}
    original = pilot.read_json(directory / "input.json")
    record = pilot.read_json(directory / "record.json")
    assert original["reasoning_effort"] == record["reasoning_effort"] == "high"
    assert record["status"] == "received" and record["usage"][0]["cached_tokens"] == 40
    assert "test-only-never-persist" not in json.dumps(original)
    assert pilot.read_json(value.out / "cost-report.json")["reasoning_effort"] == "high"


def test_failed_transport_is_preserved_without_rebilling(value, monkeypatch):
    calls = []
    install_transport(monkeypatch, {}, calls, fail=True)
    with pytest.raises(module.ProviderStopped, match="no implicit retry"):
        value.role_request("creator", "test", "CURRENT PUBLIC CONTEXT", [])
    assert len(calls) == 1
    report = pilot.read_json(value.out / "cost-report.json")
    assert report["unknown_usage_requests"] == 1
    assert pilot.read_json(value.session / "request-0001/record.json")["status"] == "failed"


def test_foreign_pixels_cannot_reach_provider(value, tmp_path, monkeypatch):
    calls = []
    install_transport(monkeypatch, {}, calls)
    foreign = tmp_path / "old-film.jpg"
    foreign.write_bytes(b"old pixels")
    with pytest.raises(ValueError, match="this experiment"):
        value.role_request("creator", "test", "CURRENT", [foreign])
    assert not calls and not value.role_requests("creator")


def test_final_api_cold_review_excludes_script_source_and_future_metadata(value, monkeypatch):
    pilot.write_json(value.out / "timeline.json", {"duration": 10, "cues": [{
        "id": "a", "start": 0, "duration": 10, "spoken": "AUTHOR_SCRIPT_SENTINEL"}]})
    (value.out / "candidate.py").write_text("AUTHOR_SOURCE_SENTINEL")
    sheet = value.out / "sheet.jpg"
    sheet.write_bytes(b"current actual pixels")
    pilot.write_json(value.out / "review-input.json", {
        "temporal_evidence": [{"cue": "a", "frames": [{"time": .5}],
                               "sheets": [{"path": str(sheet), "sha256": pilot.sha256(sheet)}]},
                              {"cue": "later", "frames": [], "sheets": [{"path": "FUTURE_SENTINEL"}]}],
        "subtitle_audit": {"rows": [{"text": "AUTHOR_SCRIPT_SENTINEL"}], "blockers": [], "advisories": []}})
    answer = {"action": "review", "status": "pass", "checks": {k: "pass" for k in
              ("mathematics", "visual_layout", "narrative", "cue_timing")},
              "inspected_cues": [{"id": "a", "observations": [{"time": .5, "detail": "Current pixels"}]}],
              "issues": [], "limitations": ["Test only"],
              "viewer_test": {"can_explain": "A relation", "missing_links": [],
                              "transfer_question": "What changes?", "supported_answer": "Visible mechanism"},
              "quality": {k: {"rating": 4, "evidence": "Frame at 0.5s"} for k in DIMENSIONS}}
    calls = []
    install_transport(monkeypatch, answer, calls)
    value.review_batch("cycle-01-whole", value.reviewer_context(), ["a"], [{"cue": "a", "time": .5}], [], {})
    original = pilot.read_json(value.review_session / "request-0001/input.json")
    assert "SENTINEL" not in json.dumps(original)
    assert len(calls) == 1 and calls[0]["reasoning_effort"] == "high"
    assert original["images"][0]["path"] == str(sheet)


def test_batch_tools_preserve_images_without_fabricating_observations(value, monkeypatch):
    pilot.write_json(value.out / "timeline.json", {"cues": [{"id": name} for name in "abc"]})
    batches = []

    def inspect(self, ids, state):
        batches.append(ids)
        state.update(images=[f"{name}.jpg" for name in ids], pending_cues=ids)
        return [{"cue": {"id": name}} for name in ids]

    monkeypatch.setattr(LearningWorkflow, "inspect_segments", inspect)
    state = {}
    value.dispatch_role("creator", {"action": "inspect_segments", "args": {"ids": list("abc")}}, state)
    assert batches == [["a", "b"], ["c"]]
    assert state["images"] == ["a.jpg", "b.jpg", "c.jpg"]
    assert value.team["actors"]["creator"]["observed"] == []


def test_background_launch_refuses_live_or_unresolved_runner(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    pilot.write_json(config, {})
    session = tmp_path / "session"
    session.mkdir()
    state = session / "team-state.json"
    pilot.write_json(state, {"status": "ready", "inflight": None})
    item = SimpleNamespace(initialize=lambda: None, session=session, team_path=state,
                           config={"model": "deepseek-flash"})
    monkeypatch.setattr(module, "prepare_case", lambda *args: config)
    monkeypatch.setattr(module, "DeepSeekLearningV3", lambda path: item)
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)) or SimpleNamespace(pid=12345))
    args = (tmp_path / "study.json", tmp_path / "profile.json", "projectile")
    receipt = module.launch(*args)
    assert receipt["reasoning_effort"] == "high" and len(calls) == 1
    assert "manimind.experiments.deepseek_learning_v3" in calls[0][0][0]
    monkeypatch.setattr(module.os, "kill", lambda *a: None)
    with pytest.raises(ValueError, match="alive"):
        module.launch(*args)
    assert len(calls) == 1
    (session / "launcher.json").unlink()
    pilot.write_json(state, {"status": "running", "inflight": {"phase": "request"}})
    with pytest.raises(ValueError, match="clean, unlocked"):
        module.launch(*args)
    assert len(calls) == 1
