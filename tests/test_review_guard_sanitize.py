"""review_guard.sanitize: first-look packets must not expose prior judgments."""

import json

import pytest

from manimind.review_guard import sanitize


def _plan():
    return {
        "project_id": "lesson-x", "author_agent": "author-1", "author_context": "author-1",
        "prior_knowledge": ["幂函数求导"], "review_times": [1.0, 2.0],
        "transition_review_times": [{"id": "a", "before": 1.0}],
        "production_boundary": {"independent_review_required": True},
        "revision_mode": "revision",
        "revision_contract": "runtime/projects/x/content-regression-contract.json",
        "revision_review": "runtime/sessions/x/regression.json",
        "correction_scope": ["only one change"],
        "repair_request": {"original_visual_review": "/abs/visual-review-v011.json",
                           "finding": "B1 old/new state roles", "prior_decision": "revise"},
        "cues": [{"id": "c1", "old": {"x": 1}, "visual": "保留"}],
    }


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_sanitize_plan_strips_repair_and_review_fields_only():
    plan = _plan()
    clean, removed = sanitize.sanitize_plan(plan)
    assert set(removed) == {"revision_contract", "revision_review", "correction_scope", "repair_request"}
    for key in removed:
        assert key not in clean
    # neutral fields that merely look similar survive
    assert clean["prior_knowledge"] == ["幂函数求导"]
    assert clean["review_times"] == [1.0, 2.0]
    assert clean["production_boundary"] == {"independent_review_required": True}
    assert clean["cues"][0]["old"] == {"x": 1}
    assert "repair_request" in plan  # input untouched
    assert sanitize.find_forbidden_keys(clean) == []


@pytest.mark.parametrize("key", ["repair_request", "correction_scope", "revision_review", "prior_decision",
                                 "old_decisions", "visual_review", "visual_review_sha256", "blocking_findings",
                                 "finding", "author_observations", "prior_review_opinions_read"])
def test_forbidden_keys(key):
    assert sanitize.forbidden_key(key)


@pytest.mark.parametrize("key", ["review_times", "prior_knowledge", "review_checks", "old", "original_filename",
                                 "independent_review_required", "repair", "bindings", "review_requirements"])
def test_neutral_keys(key):
    assert not sanitize.forbidden_key(key)


def test_bindings_hashes_are_not_judged_by_key_name():
    packet = {"bindings": {"revision_contract_sha256": "aa", "baseline_media_sha256": "bb"}}
    assert sanitize.find_forbidden_keys(packet) == []


def test_packet_binding_attempt_with_repair_request_is_rejected(tmp_path):
    attempt = tmp_path / "outputs" / "visual-v013"
    _write(attempt / "plan.json", _plan())
    packet = _write(tmp_path / "first-look-packet.json", {
        "attempt": str(attempt), "stage": "independent_first_look_input",
        "exclude": "No prior judgments", "bindings": {"plan_sha256": "x"}})
    leaks = sanitize.scan_packet(packet, root=tmp_path)
    blocking = sanitize.blocking_leaks(leaks)
    assert {row["detail"] for row in blocking if row["kind"] == "forbidden_key"} >= {"repair_request", "correction_scope"}
    assert all(row["hops"] == 1 for row in blocking)
    with pytest.raises(ValueError, match="prior judgments"):
        sanitize.require_clean_packet(packet, root=tmp_path)


def test_reachable_review_report_is_rejected(tmp_path):
    old = _write(tmp_path / "visual-review-v011.json", {"reviewer_agent": "r1", "status": "revise"})
    packet = _write(tmp_path / "packet.json", {"context_file": str(old)})
    kinds = {row["kind"] for row in sanitize.blocking_leaks(sanitize.scan_packet(packet, root=tmp_path))}
    assert "review_report" in kinds


def test_forbid_path_and_report_target_handling(tmp_path):
    target = _write(tmp_path / "visual-review-v013.json", {"reviewer_agent": "r9"})
    other = _write(tmp_path / "neutral.json", {"x": 1})
    packet = _write(tmp_path / "packet.json", {"report_target": str(target), "notes": str(other)})
    assert sanitize.scan_packet(packet, root=tmp_path) == []  # report_target is an output, not an input
    leaks = sanitize.scan_packet(packet, root=tmp_path, forbid_paths=[other])
    assert [row["kind"] for row in leaks] == ["forbidden_path"]


def test_sanitize_packet_rebinds_to_clean_plan(tmp_path):
    attempt = tmp_path / "outputs" / "visual-v013"
    old_plan = _write(tmp_path / "runtime" / "projects" / "scene-draft-plan-v011.json", {"repair_request": {}})
    plan = _plan() | {"sources": [str(old_plan.relative_to(tmp_path)), "examples/scene.py"]}
    _write(attempt / "plan.json", plan)
    source_sha = sanitize.sha(attempt / "plan.json")
    packet = _write(tmp_path / "session" / "first-look-packet-v013.json", {
        "attempt": str(attempt), "bindings": {"plan_sha256": source_sha, "revision_contract_sha256": "ab"},
        "current_video": str(attempt / "understanding.mp4")})
    out = tmp_path / "reviewer-view"
    receipt = sanitize.sanitize_packet(packet, out, root=tmp_path)
    assert receipt["clean"], receipt["blocking_leaks"]
    view = json.loads((out / "first-look-packet-v013.json").read_text(encoding="utf-8"))
    assert "attempt" not in view and view["bindings"]["revision_contract_sha256"] == "ab"
    reviewer_plan = json.loads((out / "reviewer-plan.json").read_text(encoding="utf-8"))
    assert sanitize.find_forbidden_keys(reviewer_plan) == []
    assert reviewer_plan["sources"][0].startswith("[withheld")
    assert reviewer_plan["sources"][1] == "examples/scene.py"
    assert receipt["plan_receipt"]["source_plan_sha256"] == source_sha
    assert sanitize.sha(attempt / "plan.json") == source_sha  # source never modified
    assert str(packet) not in (out / "first-look-packet-v013.json").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        sanitize.sanitize_packet(packet, out, root=tmp_path)


def test_sanitize_packet_rejects_bindings_of_other_plan(tmp_path):
    attempt = tmp_path / "a"
    _write(attempt / "plan.json", _plan())
    packet = _write(tmp_path / "p.json", {"attempt": str(attempt), "bindings": {"plan_sha256": "0" * 64}})
    with pytest.raises(ValueError, match="another plan"):
        sanitize.sanitize_packet(packet, tmp_path / "out", root=tmp_path)


def test_cli_check_exit_codes(tmp_path, capsys):
    attempt = tmp_path / "a"
    _write(attempt / "plan.json", _plan())
    bad = _write(tmp_path / "bad.json", {"attempt": str(attempt)})
    good = _write(tmp_path / "good.json", {"stage": "independent_first_look_input"})
    assert sanitize.main(["check", str(bad), "--root", str(tmp_path)]) == 1
    assert sanitize.main(["check", str(good), "--root", str(tmp_path)]) == 0
    assert '"clean": true' in capsys.readouterr().out
