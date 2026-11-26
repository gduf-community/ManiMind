"""review_guard.gates: first look and regression are separate gates; merge combines."""

import json
from pathlib import Path

import pytest

from manimind.review_guard import gates, identity
from manimind.review_guard import report as schema

BINDINGS = {"plan_sha256": "a" * 64, "visual_sha256": "b" * 64, "source_contract": "continuous-meaning-units-v1"}


def passing_visual(bindings=BINDINGS, agent="rev-a", context="ctx-a"):
    value = schema.skeleton("visual", bindings, agent, context)
    del value["incomplete_reason"]
    value.update(status="pass", release_authorized=True)
    value["viewer_test"] = {"can_explain": "内层先变，外层再变", "missing_links": [],
                            "transfer_question": "(2x+1)^5 的导数", "supported_answer": "画面给出连接"}
    value["quality"] = {name: {"rating": 4, "evidence": "12.0s 实看"} for name in schema.QUALITY_DIMENSIONS}
    value["editorial_checks"] = {name: {"status": "pass", "evidence": [{"time": 12.0, "finding": "可见"}]}
                                 for name in schema.EDITORIAL_CHECKS}
    value["editorial_checks"]["meaning_alignment"]["status"] = "not_applicable"
    return value


class FakeBackend(gates.UnitFilmBackend):
    """Real frozen ``_review``/editorial checks; synthetic attempt bindings."""

    def __init__(self, tmp_path, *, revision=True, regression_ok=True):
        super().__init__()
        self.tmp, self.revision, self.regression_ok = Path(tmp_path), revision, regression_ok

    def plan(self, attempt):
        return {"project_id": "lesson-04", "author_agent": "author-1", "author_context": "author-1"}

    def bindings(self, attempt):
        return dict(BINDINGS)

    def editorial(self, report, attempt, stage):
        return self.quality.validate_editorial_review(report, duration=60.0, stage=stage)

    def regression_required(self, attempt):
        return self.revision

    def regression_report_path(self, attempt):
        return self.tmp / "regression.json"

    def require_regression(self, attempt):
        report = json.loads(self.regression_report_path(attempt).read_text(encoding="utf-8"))
        self.unit_film._review(report, "content_regression", self.bindings(attempt), authors=self.authors(attempt))
        if not self.regression_ok:
            raise ValueError("Independent content regression must pass")
        return self.regression_report_path(attempt)


def _regression(agent="rev-b", context="ctx-b"):
    value = passing_visual(agent=agent, context=context)
    value["stage"] = "content_regression"
    return value


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def attempt(tmp_path):
    path = tmp_path / "visual-v013"
    path.mkdir()
    return path


def test_first_look_passes_without_regression_report(tmp_path, attempt):
    backend = FakeBackend(tmp_path)
    report = _write(tmp_path / "visual-review.json", passing_visual())
    first = gates.first_look_gate(attempt, report, backend=backend)
    assert first["status"] == "pass", first
    second = gates.regression_gate(attempt, backend=backend)
    assert second["status"] == "blocked" and "not written yet" in second["reason"]
    merged = gates.merge_gate(attempt, report, backend=backend)
    assert merged["status"] == "blocked" and merged["parts"]["first_look"]["status"] == "pass"


def test_merge_passes_with_distinct_reviewers(tmp_path, attempt):
    backend = FakeBackend(tmp_path)
    report = _write(tmp_path / "visual-review.json", passing_visual())
    _write(tmp_path / "regression.json", _regression())
    assert gates.merge_gate(attempt, report, backend=backend)["status"] == "pass"


@pytest.mark.parametrize("agent, context", [("rev-a", "ctx-z"), ("rev-z", "ctx-a"), ("ctx-a", "rev-q")])
def test_merge_rejects_shared_reviewer_identity(tmp_path, attempt, agent, context):
    backend = FakeBackend(tmp_path)
    report = _write(tmp_path / "visual-review.json", passing_visual())
    _write(tmp_path / "regression.json", _regression(agent, context))
    merged = gates.merge_gate(attempt, report, backend=backend)
    assert merged["status"] == "fail" and "different reviewer" in merged["reason"]


def test_fresh_lesson_regression_not_required(tmp_path, attempt):
    backend = FakeBackend(tmp_path, revision=False)
    report = _write(tmp_path / "visual-review.json", passing_visual())
    assert gates.regression_gate(attempt, backend=backend)["status"] == "not_required"
    assert gates.merge_gate(attempt, report, backend=backend)["status"] == "pass"


def test_failing_regression_does_not_change_first_look(tmp_path, attempt):
    backend = FakeBackend(tmp_path, regression_ok=False)
    report = _write(tmp_path / "visual-review.json", passing_visual())
    _write(tmp_path / "regression.json", _regression())
    assert gates.first_look_gate(attempt, report, backend=backend)["status"] == "pass"
    assert gates.regression_gate(attempt, backend=backend)["status"] == "fail"
    assert gates.merge_gate(attempt, report, backend=backend)["status"] == "fail"


def test_first_look_fails_on_author_self_review_and_stale_bindings(tmp_path, attempt):
    backend = FakeBackend(tmp_path)
    own = _write(tmp_path / "own.json", passing_visual(agent="author-1", context="ctx-x"))
    assert gates.first_look_gate(attempt, own, backend=backend)["status"] == "fail"
    stale = _write(tmp_path / "stale.json", passing_visual(bindings={**BINDINGS, "plan_sha256": "0" * 64}))
    assert gates.first_look_gate(attempt, stale, backend=backend)["status"] == "fail"
    assert gates.first_look_gate(attempt, tmp_path / "missing.json", backend=backend)["status"] == "blocked"


def test_first_look_gate_rejects_reviewer_reused_from_other_lesson(tmp_path, attempt):
    backend = FakeBackend(tmp_path)
    registry = tmp_path / "review-identities.json"
    identity.register(registry, "rev-a", "ctx-a", "lesson-03", "visual-v011", "visual")
    report = _write(tmp_path / "visual-review.json", passing_visual())
    result = gates.first_look_gate(attempt, report, backend=backend, registry=registry)
    assert result["status"] == "fail" and "lesson-03" in result["reason"]
    fresh = tmp_path / "fresh.json"
    identity.register(fresh, "rev-a", "ctx-a", "lesson-04", "visual-v013", "visual")
    assert gates.first_look_gate(attempt, report, backend=backend, registry=fresh)["status"] == "pass"
