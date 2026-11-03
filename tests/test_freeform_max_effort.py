import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from manimind.experiments import freeform_max_effort as module
from manimind.experiments.freeform_max_effort import MaxEffortExperiment, ProviderStopped


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr(module.review_module, "ROOT", tmp_path)
    value = MaxEffortExperiment.__new__(MaxEffortExperiment)
    value.id = "fresh-max"
    value.out = tmp_path / "outputs/fresh-max"
    value.context = tmp_path / "runtime/projects/fresh-max"
    value.session = tmp_path / "runtime/sessions/fresh-max-generation"
    value.spec_path = value.out / "spec.json"
    value.config_path = tmp_path / "config.json"
    value.config = json.loads((module.ROOT / "configs/deepseek-max-effort-20261021.json").read_text())
    value.config["project_id"] = value.id
    value.config_path.write_text(json.dumps(value.config))
    monkeypatch.setattr(value, "frozen_paths", lambda: [value.config_path])
    value.initialize()
    return value


def test_fresh_initialization_does_not_adopt_any_candidate(agent):
    assert not agent.spec_path.exists()
    assert not (agent.out / "candidate.py").exists()
    assert module.pilot.read_json(agent.cycle_path)["phase"] == "author"
    protocol = module.pilot.read_json(agent.context / "max-effort-protocol.json")
    assert protocol["seed"] is None and protocol["fresh_context"]
    assert set(protocol["caps"].values()) == {None}
    agent.verify()


@pytest.mark.parametrize("key,value", [
    ("seed_config", "old.json"), ("thinking", {"type": "disabled"}),
    ("reasoning_effort", "high"), ("max_requests", 48),
    ("max_renders", 8), ("max_cost_CNY", 10), ("max_review_cycles", 3),
])
def test_configuration_rejects_seed_or_hidden_low_limits(agent, key, value):
    agent.config[key] = value
    with pytest.raises(ValueError):
        agent.validate_config()


def test_author_receives_only_own_unedited_review(agent):
    state = module.pilot.read_json(agent.state_path)
    feedback = agent.review_session / "feedback.json"
    feedback.write_text('{"review":"OWN RUN REVIEW"}')
    module.pilot.write_json(agent.cycle_path, {
        "feedback": str(feedback), "feedback_sha256": module.pilot.sha256(feedback)})
    context = agent.context_text(state)
    assert feedback.read_text() in context
    assert "NO monetary" in context
    assert "projectile-story-20261020" not in context
    feedback.write_text("coordinator change")
    with pytest.raises(ValueError, match="feedback changed"):
        agent.context_text(state)


def test_costs_are_idempotent_and_include_failed_requests(agent):
    for parent, status, usage in (
        (agent.session, "received", [{"prompt_tokens": 1000, "completion_tokens": 200, "cached_tokens": 500}]),
        (agent.review_session, "failed", []),
    ):
        path = parent / "request-0001"
        path.mkdir()
        module.pilot.write_json(path / "record.json", {"status": status, "usage": usage})
    agent.report()
    first = module.pilot.read_json(agent.out / "cost-report.json")
    agent.report()
    assert first == module.pilot.read_json(agent.out / "cost-report.json")
    assert first["known_peak_uncached_estimate_CNY"] == pytest.approx(.0036)
    assert first["known_offpeak_cached_estimate_CNY"] == pytest.approx(.00131)
    assert first["unknown_usage_requests"] == 1
    assert first["financial_limit"] is None


def fake_provider(monkeypatch, finish="stop"):
    from manimind.llm import client
    calls = []

    class Stream:
        def __enter__(self):
            return iter([
                SimpleNamespace(model="deepseek-flash", usage=None, choices=[SimpleNamespace(
                    delta=SimpleNamespace(content=None, reasoning_content="private"), finish_reason=None)]),
                SimpleNamespace(model="deepseek-flash", usage=SimpleNamespace(model_dump=lambda: {
                    "prompt_tokens": 100, "completion_tokens": 50, "prompt_cache_hit_tokens": 20}),
                    choices=[SimpleNamespace(delta=SimpleNamespace(content='{"action":"review"}',
                                                                   reasoning_content=None), finish_reason=finish)]),
            ])

        def __exit__(self, *args):
            return False

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
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-never-persist")
    return calls


@pytest.mark.parametrize("role", ["author", "reviewer"])
def test_both_roles_actually_send_max_thinking_and_usage_is_retained(agent, monkeypatch, role):
    calls = fake_provider(monkeypatch)
    raw, directory = agent.stream_request(role, "test", "Public JSON request", [])
    assert json.loads(raw)["action"] == "review"
    sent = calls[0]
    assert sent["reasoning_effort"] == "max"
    assert sent["extra_body"] == {"thinking": {"type": "enabled"}}
    assert sent["max_tokens"] == 393216 and sent["stream"]
    assert len(sent["messages"]) == 2
    record = module.pilot.read_json(directory / "record.json")
    assert record["status"] == "received"
    assert record["thinking_chars"] > 0 and record["usage"][0]["cached_tokens"] == 20
    assert "test-only-never-persist" not in (directory / "input.json").read_text()


def test_truncated_stream_is_not_executed_or_silently_retried(agent, monkeypatch):
    calls = fake_provider(monkeypatch, finish="length")
    with pytest.raises(ProviderStopped):
        agent.request("test", "Public JSON request")
    assert len(calls) == 1
    record = module.pilot.read_json(agent.requests()[0])
    assert record["status"] == "failed" and record["usage"]
    assert (agent.requests()[0].parent / "answer.txt").exists()


def test_images_from_other_projects_are_rejected_before_provider_call(agent, monkeypatch, tmp_path):
    calls = fake_provider(monkeypatch)
    old_frame = tmp_path / "reference.jpg"
    old_frame.write_bytes(b"not this run")
    with pytest.raises(ValueError, match="belong to this isolated"):
        agent.request("test", "JSON", [old_frame])
    assert not calls and not agent.requests()


def test_no_render_count_cap(agent, monkeypatch):
    monkeypatch.setattr(module, "check_agent_source", lambda source: None)
    (agent.out / "candidate.py").write_text("candidate")
    module.pilot.write_json(agent.spec_path, {"placeholder": True})
    production = SimpleNamespace(session=agent.session)
    monkeypatch.setattr(module.media, "Production", lambda path: production)
    monkeypatch.setattr(agent, "render", lambda quality: None)
    monkeypatch.setattr(agent, "latest_video", lambda state: (agent.out / "video.mp4", 10))
    agent.current_step = agent.session / "step"
    agent.current_step.mkdir()
    state = module.pilot.read_json(agent.state_path)
    state["renders"] = 100000
    agent.dispatch({"action": "render", "args": {}}, state)
    assert state["renders"] == 100001


def test_review_pass_does_not_publish_and_revisions_are_not_cycle_capped(agent, monkeypatch):
    monkeypatch.setattr(agent, "initialize", lambda: None)
    states = []
    def author():
        state = module.pilot.read_json(agent.state_path)
        state["status"] = "submitted_for_independent_review"
        agent.save_state(state)
        states.append(state)
        return state
    def review(cycle):
        path = agent.review_session / f"cycle-{cycle}.json"
        report = {"status": "pass" if cycle == 5 else "revise"}
        module.pilot.write_json(path, report)
        return path, report
    monkeypatch.setattr(agent, "run_author", author)
    monkeypatch.setattr(agent, "independent_review", review)
    agent.run_cycles()
    assert len(states) == 5
    assert module.pilot.read_json(agent.cycle_path)["phase"] == "awaiting_external_review"
    assert not (agent.context / "review.json").exists()
    assert not module.pilot.read_json(agent.out / "review-cycle-report.json")["release_allowed"]
