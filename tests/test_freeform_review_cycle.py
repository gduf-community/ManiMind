import json
from pathlib import Path

import pytest

from manimind.experiments import freeform_review_cycle as module
from manimind.experiments.freeform_review_cycle import ReviewCycleExperiment, validate_review


def good_review():
    return {
        "action": "review", "status": "pass",
        "checks": {k: "pass" for k in module.CHECKS},
        "inspected_cues": [{"id": "a", "observations": [{"time": 1.0, "detail": "Visible ball"}]}],
        "issues": [], "limitations": ["Sampled frames only"],
    }


def test_valid_review_requires_actual_cue_frame():
    assert validate_review(good_review(), ["a"], {"a": [1.]}, 10)["status"] == "pass"
    with pytest.raises(ValueError, match="supplied frame"):
        validate_review(good_review(), ["a"], {"a": [2.]}, 10)


@pytest.mark.parametrize("field,value", [("status", "approved"), ("issues", None),
                                        ("limitations", None), ("inspected_cues", [])])
def test_incomplete_reviews_fail_closed(field, value):
    data = good_review()
    data[field] = value
    with pytest.raises(ValueError):
        validate_review(data, ["a"], {"a": [1.]}, 10)


def test_pass_cannot_override_failed_check_or_blocker():
    data = good_review()
    data["checks"]["narrative"] = "fail"
    with pytest.raises(ValueError, match="contradicts"):
        validate_review(data, ["a"], {"a": [1.]}, 10)
    data = good_review()
    data["issues"] = [{"severity": "blocker", "category": "narrative", "cue": "a", "time": 1,
                       "evidence": "Actual frame", "problem": "Contradiction", "suggested_revision": "Resolve it"}]
    with pytest.raises(ValueError, match="contradicts"):
        validate_review(data, ["a"], {"a": [1.]}, 10)
    data["status"] = "revise"
    assert validate_review(data, ["a"], {"a": [1.]}, 10)["status"] == "revise"


def cycle_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    agent = ReviewCycleExperiment.__new__(ReviewCycleExperiment)
    agent.id = "test"
    agent.out = tmp_path / "outputs/test"
    agent.session = tmp_path / "runtime/sessions/test-generation"
    agent.context = tmp_path / "runtime/projects/test"
    for path in (agent.out, agent.session, agent.context, agent.review_session):
        path.mkdir(parents=True)
    agent.spec_path = agent.out / "spec.json"
    agent.config = {"seed_config": "configs/parent.json", "brief": {"goal": "Public task"}}
    return agent


def test_reviewer_context_omits_author_assessment_and_history(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    (agent.out / "timeline.json").write_text(json.dumps({"duration": 10, "cues": [
        {"id": "a", "spoken": "Narration", "start": 0, "duration": 10, "author_assessment": "secret"}]}))
    (agent.out / "candidate.py").write_text("class GeneratedLesson: pass")
    (agent.out / "author-self-review.json").write_text("DO NOT SHARE")
    (agent.context / "review.json").write_text("OLD CRITIQUE")
    text = agent.reviewer_context()
    assert "Narration" in text and "GeneratedLesson" in text
    assert all(s not in text for s in ("secret", "DO NOT SHARE", "OLD CRITIQUE"))


def test_role_costs_include_failed_calls_without_double_count(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    def author_report(self):
        module.pilot.write_json(self.out / "cost-report.json", {
            "known_peak_uncached_estimate_CNY": .1, "prompt_tokens": 10,
            "completion_tokens": 5, "unknown_usage_requests": 0})
    monkeypatch.setattr(module.AgentExperiment, "report", author_report)
    directory = agent.review_session / "request-001"
    directory.mkdir()
    module.pilot.write_json(directory / "record.json", {
        "status": "failed", "usage": [{"prompt_tokens": 100, "completion_tokens": 50}]})
    agent.report()
    first = module.pilot.read_json(agent.out / "cost-report.json")
    agent.report()
    assert module.pilot.read_json(agent.out / "cost-report.json") == first
    assert first["known_peak_uncached_estimate_CNY"] == pytest.approx(.1006)
    assert first["prompt_tokens"] == 110 and first["completion_tokens"] == 55
    assert first["reviewer_calls"] == 1 and first["unknown_usage_requests"] == 0
    module.pilot.write_json(directory / "record.json", {"status": "started", "usage": []})
    agent.report()
    assert module.pilot.read_json(agent.out / "cost-report.json")["unknown_usage_requests"] == 1


def test_author_receives_unedited_feedback_and_tampering_is_rejected(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    agent.config["max_output_tokens"] = 100
    monkeypatch.setattr(agent, "check_budget", lambda *args: None)
    monkeypatch.setattr(module.AgentExperiment, "context_text", lambda self, state: "PUBLIC AUTHOR CONTEXT")
    report = agent.review_session / "report.json"
    report.write_text('{"original":"Independent verdict"}')
    module.pilot.write_json(agent.cycle_path, {"feedback": str(report), "feedback_sha256": module.pilot.sha256(report)})
    assert report.read_text() in agent.context_text({})
    report.write_text("changed")
    with pytest.raises(ValueError, match="feedback changed"):
        agent.context_text({})


def test_first_author_call_counts_existing_reviewer_spending(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    agent.config.update(max_cost_CNY=1, max_output_tokens=100)
    def report():
        module.pilot.write_json(agent.out / "cost-report.json", {
            "known_peak_uncached_estimate_CNY": 1, "unknown_usage_requests": 0})
    monkeypatch.setattr(agent, "report", report)
    with pytest.raises(ValueError, match="Shared cost"):
        agent.request("agent_001", "test")
    assert not agent.requests()


def test_budget_preflight_does_not_advance_author_cursor(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    agent.config.update(max_cost_CNY=.1, max_requests=2, max_output_tokens=100)
    monkeypatch.setattr(agent, "initialize", lambda: None)
    monkeypatch.setattr(agent, "verify", lambda: None)
    monkeypatch.setattr(module.AgentExperiment, "context_text", lambda self, state: "PUBLIC TASK")
    module.pilot.write_json(agent.cycle_path, {"feedback": None})
    agent.save_state({"status": "running", "turn": 0, "renders": 0, "images": []})
    def report():
        module.pilot.write_json(agent.out / "cost-report.json", {
            "known_peak_uncached_estimate_CNY": .1, "unknown_usage_requests": 0})
    monkeypatch.setattr(agent, "report", report)
    with pytest.raises(module.RequestBudgetStopped):
        module.AgentExperiment.run(agent)
    assert module.pilot.read_json(agent.state_path)["turn"] == 0
    assert not agent.requests() and not list(agent.session.glob("step-*"))


def test_interrupted_review_does_not_resend_or_claim_completion(tmp_path, monkeypatch):
    agent = cycle_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(agent, "initialize", lambda: None)
    module.pilot.write_json(agent.cycle_path, {"phase": "reviewing", "cycle": 1})
    with pytest.raises(ValueError, match="Unresolved prior stage"):
        agent.run_cycles()
    assert not (agent.session / "review-cycle.lock").exists()
    assert not (agent.out / "review-cycle-report.json").exists()


@pytest.mark.parametrize("final_verdict,expected", [
    ("pass", "awaiting_external_review"), ("revise", "review_budget_exhausted")])
def test_review_feedback_loop_is_bounded_and_never_publishes(tmp_path, monkeypatch, final_verdict, expected):
    agent = cycle_fixture(tmp_path, monkeypatch)
    agent.config["max_review_cycles"] = 3
    module.pilot.write_json(agent.cycle_path, {"phase": "seed", "cycle": 0, "feedback": None})
    monkeypatch.setattr(agent, "initialize", lambda: None)
    monkeypatch.setattr(agent, "seed", lambda: agent.save_state({"status": "running"}))
    calls = []
    def author(self):
        calls.append("author")
        self.save_state({"status": "submitted_for_independent_review"})
    def reviewer(cycle):
        calls.append(f"review-{cycle}")
        path = agent.review_session / f"report-{cycle}.json"
        data = {"status": final_verdict if cycle == 3 else "revise"}
        module.pilot.write_json(path, data)
        return path, data
    monkeypatch.setattr(module.AgentExperiment, "run", author)
    monkeypatch.setattr(agent, "independent_review", reviewer)
    monkeypatch.setattr(agent, "report", lambda: module.pilot.write_json(agent.out / "cost-report.json", {}))
    agent.run_cycles()
    assert calls == ["review-1", "author", "review-2", "author", "review-3"]
    assert module.pilot.read_json(agent.cycle_path)["phase"] == expected
    assert not (agent.context / "review.json").exists()
    assert module.pilot.read_json(agent.out / "review-cycle-report.json")["release_allowed"] is False


def test_config_keeps_seed_task_model_and_mode_unchanged():
    root = Path(__file__).resolve().parents[1]
    seed = json.loads((root / "configs/deepseek-autonomous-20261020.json").read_text())
    config = json.loads((root / "configs/deepseek-review-cycle-20261021.json").read_text())
    for key in ("brief", "model", "thinking", "temperature", "max_output_tokens"):
        assert config[key] == seed[key]
    assert config["max_review_cycles"] == 3
    assert config["max_cost_CNY"] == 10
