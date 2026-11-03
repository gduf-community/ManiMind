import json
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from manimind.scene_spec import experiment as ex
from manimind.scene_spec.schema import SpecError


@pytest.fixture
def suite(monkeypatch, tmp_path):
    from manimind.llm import client
    def no_network(*args, **kwargs):
        pytest.fail("Unexpected paid request")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setenv("MIMO_EZLOOK_API_KEY", "test-private-key")
    monkeypatch.setattr(ex, "ROOT", tmp_path)
    config = ex.pilot.read_json(ex.CONFIG)
    config["max_generation_requests"] = 2
    config_path = tmp_path / "config.json"
    ex.pilot.write_json(config_path, config)
    task = config["tasks"]["original"]
    sdk = MagicMock()
    sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
        model="candidate", usage=SimpleNamespace(prompt_tokens=100, completion_tokens=200, total_tokens=300),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(ex.fixture(task))))])
    monkeypatch.setattr(client, "OpenAI", sdk)
    ex.init("suite", config_path)
    return tmp_path, sdk


def test_independent_trials_have_same_prompt_and_frozen_budget(suite):
    root, sdk = suite
    ex.generate("suite", "poly-a")
    ex.generate("suite", "poly-b")
    out, context, session = ex.paths("suite")
    assert ex.pilot.read_json(session / "poly-a-01-prompt.json") == ex.pilot.read_json(session / "poly-b-01-prompt.json")
    with pytest.raises(ValueError, match="budget"):
        ex.generate("suite", "poly-c")
    assert sdk.return_value.chat.completions.create.call_count == 2
    assert ex.pilot.read_json(out / "generation-cost.json")["requests"] == 2
    assert "test-private-key" not in (context / "suite.json").read_text()
    assert not list(root.rglob("*.py"))
    assert not list(root.rglob("*.mp4"))
    request = sdk.return_value.chat.completions.create.call_args.kwargs
    assert request["max_completion_tokens"] == 4096
    assert request["extra_body"]["thinking"]["type"] == "disabled"


def test_failed_json_retained_and_explicit_repair_only(suite):
    _, sdk = suite
    response = sdk.return_value.chat.completions.create.return_value.choices[0].message
    valid = response.content
    response.content = "not-json"
    with pytest.raises(SpecError):
        ex.generate("suite", "poly-a")
    out, _, session = ex.paths("suite")
    assert (session / "poly-a-01-reply.txt").read_text() == "not-json"
    assert ex.pilot.read_json(session / "requests.json")["requests"][0]["status"] == "failed"
    with pytest.raises(ValueError, match="feedback"):
        ex.generate("suite", "poly-a")
    feedback = session / "feedback.txt"
    feedback.write_text("Return valid JSON matching the frozen contract")
    response.content = valid
    ex.generate("suite", "poly-a", feedback)
    assert ex.latest_spec("suite", "poly-a")[-1]["attempt"] == 2
    assert (out / "poly-a/attempt-01").exists()
    assert sdk.return_value.chat.completions.create.call_count == 2


@pytest.mark.parametrize("change", ["reply", "spec", "suite", "prompt"])
def test_tampered_inputs_cannot_render_or_continue(suite, change):
    _, sdk = suite
    ex.generate("suite", "poly-a")
    out, context, session = ex.paths("suite")
    target = {"reply": session / "poly-a-01-reply.txt", "spec": out / "poly-a/attempt-01/scene-spec.json",
              "suite": context / "suite.json", "prompt": session / "poly-a-01-prompt.json"}[change]
    target.write_text(target.read_text() + " ")
    with pytest.raises(ValueError, match="Changed|changed"):
        ex.latest_spec("suite", "poly-a")
    assert sdk.return_value.chat.completions.create.call_count == 1


def test_stale_audio_cache_rejected(tmp_path):
    task = {"test": True}
    ex.pilot.write_json(tmp_path / "timeline.json", {})
    (tmp_path / "narration.wav").write_bytes(b"fixture")
    ex.pilot.write_json(tmp_path / "provenance.json", {"task": task, "audio_sha256": "wrong", "timeline_sha256": "wrong"})
    with pytest.raises(ValueError, match="stale"):
        ex.prepare_assets(task, tmp_path)


@pytest.mark.parametrize("defect", ["missing", "blocked", "stale", "no_frames", "no_identity"])
def test_assembly_cannot_bypass_independent_review(monkeypatch, tmp_path, defect):
    out, context, directory = (tmp_path / name for name in ["out", "context", "render"])
    out.mkdir()
    context.mkdir()
    current = {"video": "video-hash"}
    frame = out / "frame.png"
    frame.write_bytes(b"pixel-evidence")
    indexed = [{"path": str(frame), "sha256": ex.pilot.sha256(frame)}]
    evidence = {"suite": "suite", "run_id": "poly-a", "hashes": current, "frames": indexed}
    review = {"reviewer_role": "reviewer", "reviewer_id": "independent-test-reviewer", "status": "approved", "blockers": [],
              "hashes": current, "checks": {name: "pass" for name in ["mathematics", "visual_layout", "narrative", "cue_timing"]},
              "inspected_frames": [str(frame)]}
    if defect == "blocked":
        review["status"] = "blocked"
    elif defect == "stale":
        review["hashes"] = {"video": "older-hash"}
    elif defect == "no_frames":
        review["inspected_frames"] = []
    elif defect == "no_identity":
        review.pop("reviewer_id")
    ex.pilot.write_json(out / "review-input.json", evidence)
    if defect != "missing":
        ex.pilot.write_json(context / "review.json", review)
    monkeypatch.setattr(ex, "render_directory", lambda *args: (out, context, directory, {}))
    monkeypatch.setattr(ex, "check_audit", lambda *args: {"status": "pass"})
    monkeypatch.setattr(ex, "hashes", lambda *args: current)
    run = MagicMock(side_effect=AssertionError("Mux must not start before approval"))
    monkeypatch.setattr(ex.pilot, "run", run)
    with pytest.raises((ValueError, FileNotFoundError)):
        ex.assemble("suite", "poly-a")
    run.assert_not_called()


def test_report_does_not_turn_valid_json_into_delivery_success(suite, monkeypatch):
    from manimind.scene_spec import report
    root, _ = suite
    ex.generate("suite", "poly-a")
    ex.generate("suite", "poly-b")
    _, context, _ = ex.paths("suite")
    case_context, case_session = root / "case-context", root / "case-session"
    monkeypatch.setattr(ex.bench, "paths", lambda _case: (root / "case-output", case_context, case_session))
    profile = ex.pilot.read_json(context / "suite.json")["profile"]
    ex.pilot.write_json(case_context / "collaboration.json", {"profile": profile, "purpose": {"suite": "suite"}})
    ex.pilot.write_json(case_session / "dialogue.json", {"turns": []})
    summary = report.build("suite", "case")
    assert summary["counts"]["first_schema_valid"] == 2
    assert summary["counts"]["first_attempt_approved"] == 0
    assert summary["counts"]["delivery_verified"] == 0
    assert summary["same_task_prompts_identical"] == {"original": True}
    assert summary["generation_requests"] == summary["cost"]["requests"] == 2
    assert summary["cost"]["estimated_model_cost"] is None
    assert "test-private-key" not in json.dumps(summary)
    ex.pilot.write_json(case_session / "dialogue.json", {"turns": [{"case_sha256": "changed"}]})
    with pytest.raises(ValueError, match="Changed collaboration"):
        report.build("suite", "case")
