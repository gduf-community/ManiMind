"""review_guard.report: fixed status enum, playback coverage, skeleton and precheck."""

import json

import pytest

from manimind.review_guard import report as schema

BINDINGS = {"plan_sha256": "a" * 64, "visual_sha256": "b" * 64, "source_contract": "continuous-meaning-units-v1"}


def passing_visual(bindings=BINDINGS, agent="rev-a", context="ctx-a"):
    value = schema.skeleton("visual", bindings, agent, context)
    del value["incomplete_reason"]
    value.update(status="pass", release_authorized=True)
    value["viewer_test"] = {"can_explain": "内层先变，外层再变", "missing_links": [],
                            "transfer_question": "(2x+1)^5 的导数", "supported_answer": "画面给出两层变化率的连接"}
    value["quality"] = {name: {"rating": 4, "evidence": "12.0s 实看"} for name in schema.QUALITY_DIMENSIONS}
    value["editorial_checks"] = {name: {"status": "pass", "evidence": [{"time": 12.0, "finding": "可见"}]}
                                 for name in schema.EDITORIAL_CHECKS}
    value["editorial_checks"]["meaning_alignment"]["status"] = "not_applicable"
    value["playback_coverage"] = {"level": "sampled", "segments": [], "tool_limitations": "无 1x 播放器"}
    return value


def test_skeleton_has_gate_fields_and_is_incomplete():
    value = schema.skeleton("visual", BINDINGS, "rev-a", "ctx-a")
    assert value["status"] == "incomplete" and value["release_authorized"] is False
    for key in ("stage", "bindings", "reviewer_role", "reviewer_agent", "reviewer_context", "blocking_findings",
                "listening_reviewed", "student_tested", "action", "viewer_test", "quality", "editorial_checks"):
        assert key in value
    result = schema.precheck(value, expected_bindings=BINDINGS)
    assert result["valid"] and not result["gate_ready"]


def test_status_enum_is_fixed():
    assert schema.STATUSES == ("pass", "revise", "incomplete", "blocked")
    value = passing_visual()
    value["status"] = "conditional_pass"
    assert any("status must be one of" in e for e in schema.precheck(value)["errors"])


def test_passing_report_is_gate_ready_and_compatible_with_frozen_review():
    from manimind.postproduce import unit_film
    value = passing_visual()
    result = schema.precheck(value, expected_bindings=BINDINGS, stage="visual", duration=60.0)
    assert result["valid"] and result["gate_ready"], result["errors"]
    # Same field names/meaning the frozen gate reads.
    unit_film._review(value, "visual", BINDINGS, authors=[("author-1", "author-1")])


@pytest.mark.parametrize("mutate, fragment", [
    (lambda v: v.update(stage="first_look"), "stage must be one of"),
    (lambda v: v.update(reviewer_role="author"), "reviewer_role"),
    (lambda v: v.update(reviewer_agent=" rev-a"), "reviewer_agent"),
    (lambda v: v.update(agentID="someone-else"), "agentID"),
    (lambda v: v.update(bindings={**BINDINGS, "plan_sha256": "c" * 64}), "changed=['plan_sha256']"),
    (lambda v: v.update(bindings={}), "bindings must be"),
    (lambda v: v.update(listening_reviewed=True), "listening_reviewed"),
    (lambda v: v.update(blocking_findings=["x"]), "cannot carry blocking"),
    (lambda v: v.update(release_authorized=False), "release_authorized=true"),
])
def test_precheck_rejects_structural_errors(mutate, fragment):
    value = passing_visual()
    mutate(value)
    errors = schema.precheck(value, expected_bindings=BINDINGS)["errors"]
    assert any(fragment in e for e in errors), errors


def test_revise_blocked_incomplete_requirements():
    value = passing_visual()
    value.update(status="revise", release_authorized=False)
    value["editorial_checks"]["mechanism"]["status"] = "revise"
    assert any("revise needs" in e for e in schema.precheck(value)["errors"])
    value["blocking_findings"] = ["数值传递段未区分旧/新状态"]
    assert schema.precheck(value)["valid"]
    blocked = schema.skeleton("content_regression", BINDINGS, "r", "c")
    blocked.update(status="blocked")
    del blocked["incomplete_reason"]
    assert any("blocked_reason" in e for e in schema.precheck(blocked)["errors"])
    blocked["blocked_reason"] = "baseline media missing"
    assert schema.precheck(blocked)["valid"]
    assert not schema.precheck(blocked)["gate_ready"]


def test_playback_coverage_is_non_blocking_but_honest():
    value = passing_visual()
    del value["playback_coverage"]
    result = schema.precheck(value)
    assert result["gate_ready"] and any("playback_coverage" in w for w in result["warnings"])
    value["playback_coverage"] = {"level": "continuous_1x_partial", "segments": [{"start": 0, "end": 30}]}
    assert schema.precheck(value, duration=60)["gate_ready"]
    value["playback_coverage"] = {"level": "continuous_1x_complete", "segments": [{"start": 0, "end": 30}]}
    assert any("stop at 30.00s" in e for e in schema.precheck(value, duration=60)["errors"])
    value["playback_coverage"]["segments"].append({"start": 30.2, "end": 60})
    assert schema.precheck(value, duration=60)["gate_ready"]
    value["playback_coverage"] = {"level": "realtime", "segments": []}
    assert not schema.precheck(value)["valid"]


def test_editorial_schema_errors_surface_from_frozen_validator():
    value = passing_visual()
    value["editorial_checks"].pop("transfer")
    assert any("editorial schema" in e for e in schema.precheck(value)["errors"])


def test_cli_skeleton_and_precheck(tmp_path, capsys):
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({"bindings": BINDINGS, "attempt": "/x/visual-v013"}), encoding="utf-8")
    out = tmp_path / "visual-review.json"
    assert schema.main(["skeleton", "--packet", str(packet), "--stage", "visual",
                        "--agent", "rev-a", "--context", "ctx-a", "--out", str(out)]) == 0
    with pytest.raises(FileExistsError):
        schema.main(["skeleton", "--packet", str(packet), "--stage", "visual",
                     "--agent", "rev-a", "--context", "ctx-a", "--out", str(out)])
    assert schema.main(["precheck", str(out), "--packet", str(packet)]) == 0
    out.write_text(json.dumps(passing_visual() | {"bindings": {"plan_sha256": "z"}}), encoding="utf-8")
    assert schema.main(["precheck", str(out), "--packet", str(packet)]) == 1
    capsys.readouterr()


def test_cli_precheck_with_identity_registry(tmp_path, capsys):
    from manimind.review_guard import identity
    registry = tmp_path / "r.json"
    identity.register(registry, "rev-a", "ctx-a", "lesson-03", "visual-v011", "visual")
    report = tmp_path / "visual-review.json"
    report.write_text(json.dumps(passing_visual()), encoding="utf-8")
    assert schema.main(["precheck", str(report), "--registry", str(registry),
                        "--lesson", "lesson-04", "--version", "visual-v013"]) == 1
    assert "identity" in capsys.readouterr().out
