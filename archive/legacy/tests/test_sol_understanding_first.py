import copy
import json
from pathlib import Path

import pytest

from manimind.experiments.sol_understanding_first import SolUnderstandingFirst, SolVisualFirst
from manimind.review.understanding_quality import CHECKS
from manimind.review.learning_quality import DIMENSIONS


def judgment():
    return {"action": "review", "status": "pass", "release_authorized": True,
            "blocking_findings": [], "listening_reviewed": False, "student_tested": False,
            "viewer_test": {"can_explain": "a reason", "missing_links": [], "transfer_question": "new case", "supported_answer": "supported"},
            "quality": {key: {"rating": 4, "evidence": "2s"} for key in DIMENSIONS},
            "editorial_checks": {key: {"status": "pass", "evidence": [{"time": 2, "finding": "visible evidence"}]} for key in CHECKS}}


def experiment(tmp_path):
    value = SolUnderstandingFirst.__new__(SolUnderstandingFirst)
    value.out = tmp_path
    (tmp_path / "timeline.json").write_text(json.dumps({"duration": 20}))
    return value


def test_new_contract_reaches_author_context_without_new_template(monkeypatch):
    monkeypatch.setattr(SolVisualFirst, "actor_context", lambda *_: "current-profile-and-creative-tools")
    value = SolUnderstandingFirst.__new__(SolUnderstandingFirst)
    context = value.actor_context("creator")
    assert "current-profile-and-creative-tools" in context and "editorial_checks" in context
    assert "fixed shot" not in context


def test_actual_review_request_injects_and_validates_editorial_rules(tmp_path):
    value = experiment(tmp_path)
    captured = []
    def request(role, stage, text, images):
        captured.append(text)
        return json.dumps(judgment()), tmp_path
    value.role_request = request
    result, _ = value.reviewer_request("cycle-1-visual-whole", "public goals", [])
    assert "editorial_checks" in captured[0] and result["status"] == "pass"


def test_old_style_pass_cannot_bypass_new_publication_validator(monkeypatch, tmp_path):
    value = experiment(tmp_path)
    report = judgment()
    report["editorial_checks"]["mechanism"]["status"] = "revise"
    monkeypatch.setattr(SolVisualFirst, "approval", lambda *_: {"judgment": {"review": report}})
    with pytest.raises(ValueError, match="Pass contradicts editorial"):
        value.approval("visual")


def test_new_adapter_and_contract_are_frozen_without_editing_legacy(monkeypatch):
    monkeypatch.setattr(SolVisualFirst, "frozen_paths", lambda _: [Path("old-executor.py")])
    value = SolUnderstandingFirst.__new__(SolUnderstandingFirst)
    names = {path.name for path in value.frozen_paths()}
    assert {"old-executor.py", "sol_understanding_first.py", "understanding_quality.py", "semantic_focus.py"} <= names
