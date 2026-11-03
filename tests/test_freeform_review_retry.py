import json
from pathlib import Path

import pytest

from manimind.experiments import freeform_review_retry as module
from manimind.experiments.freeform_review_cycle import CHECKS


def test_schema_repair_uses_original_answer_and_error_once(tmp_path, monkeypatch):
    agent = module.ReviewRetryExperiment.__new__(module.ReviewRetryExperiment)
    agent.id = "schema-test"
    agent.out = tmp_path / "out"
    agent.out.mkdir()
    review_dir = tmp_path / "reviews"
    review_dir.mkdir()
    monkeypatch.setattr(type(agent), "review_session", property(lambda self: review_dir))
    (agent.out / "timeline.json").write_text(json.dumps({"duration": 10, "cues": [{"id": "a", "start": 0, "duration": 10}]}))
    calls = []
    def invalid(self, *args):
        directory = review_dir / "request-001"
        directory.mkdir()
        (directory / "answer.txt").write_text('{"issues":[{"problem":"ORIGINAL"}]}')
        module.pilot.write_json(directory / "record.json", {"status": "received"})
        module.pilot.write_json(directory / "input.json", {"text": "ORIGINAL PROMPT", "images": []})
        raise ValueError("Malformed evidence-backed review issue")
    monkeypatch.setattr(module.ReviewCycleExperiment, "review_batch", invalid)
    def repaired(label, text, images):
        calls.append((label, text, images))
        directory = review_dir / "request-002"
        directory.mkdir()
        result = {"action": "review", "status": "pass", "checks": {k: "pass" for k in CHECKS},
                  "inspected_cues": [{"id": "a", "observations": [{"time": 1., "detail": "Actual pixels"}]}],
                  "issues": [], "limitations": []}
        (directory / "answer.txt").write_text(json.dumps(result))
        return result, directory
    monkeypatch.setattr(agent, "reviewer_request", repaired)
    result = agent.review_batch("one", "context", ["a"], [{"cue": "a", "time": 1.}], [], {})
    assert len(calls) == 1 and calls[0][0] == "one-schema-repair"
    assert '"problem":"ORIGINAL"' in calls[0][1]
    assert "Malformed evidence-backed review issue" in calls[0][1]
    assert "ORIGINAL PROMPT" in calls[0][1]
    assert result["schema_repair_of"].endswith("request-001")


def test_no_response_does_not_trigger_format_repair(tmp_path, monkeypatch):
    agent = module.ReviewRetryExperiment.__new__(module.ReviewRetryExperiment)
    monkeypatch.setattr(agent, "review_requests", lambda: [])
    def failed(*args):
        raise ValueError("No request sent")
    monkeypatch.setattr(module.ReviewCycleExperiment, "review_batch", failed)
    with pytest.raises(ValueError, match="No request sent"):
        agent.review_batch("x", "x", [], [], [], {})
