import json

import pytest

from manimind.review import content_regression as subject
from manimind.postproduce import understanding_film as film


def contract(topic="derivative"):
    return {"schema_version": 1, "assets": {"baseline": {"path": "old.mp4", "sha256": "0" * 64, "duration": 20}},
            "units": [{"id": topic, "function": "Keep the visible reason, not just its final answer",
                       "asset": "baseline", "baseline_interval": [2, 12], "features": [
                           {"id": "reason", "kind": "state", "claim": "The step that licenses the inference"},
                           {"id": "correspondence", "kind": "process", "claim": "Trace correspondence through a change"}]}]}


def comparison(topic="derivative"):
    return {"stage": "content_regression", "status": "pass", "reviewer_role": "independent",
            "reviewer_agent": "comparison-context", "bindings": {"media": "current"},
            "release_authorized": True, "blocking_findings": [], "units": [{"id": topic, "features": [
                {"id": "reason", "outcome": "retained", "evidence": [{"time": 5, "finding": "the visible reason"}]},
                {"id": "correspondence", "outcome": "retained", "evidence": [
                    {"phase": phase, "time": time, "finding": "actual state of this semantic object"}
                    for phase, time in (("before", 6), ("during", 7), ("after", 8))]}]}]}


@pytest.mark.parametrize("topic", ["projectile", "derivative", "eigenvectors", "chemistry"])
def test_same_protocol_does_not_fix_topic_or_number_of_shots(topic):
    assert subject.validate_comparison(comparison(topic), contract(topic), {"media": "current"}, 30)["status"] == "pass"


@pytest.mark.parametrize("mutation", ["unit", "detail", "loss", "terminal_only", "stale", "author", "out_of_range", "no_rationale"])
def test_higher_quality_or_more_screen_time_cannot_bypass_content_regression(mutation):
    value = comparison()
    if mutation == "unit": value["units"] = []
    if mutation == "detail": value["units"][0]["features"].pop(0)
    if mutation == "loss": value["units"][0]["features"][0]["outcome"] = "lost"
    if mutation == "terminal_only": value["units"][0]["features"][1]["evidence"] = [{"time": 8, "finding": "formula still exists"}]
    if mutation == "stale": value["bindings"] = {"media": "old"}
    if mutation == "author": value["reviewer_role"] = "creator"
    if mutation == "out_of_range": value["units"][0]["features"][0]["evidence"][0]["time"] = 99
    if mutation == "no_rationale": value["units"][0]["features"][0]["outcome"] = "equivalent"
    value["quality_score"] = 100
    value["new_duration"] = 60
    with pytest.raises(ValueError):
        subject.validate_comparison(value, contract(), {"media": "current"}, 30)


def test_layout_or_representation_can_change_if_its_function_remains_visible():
    value = comparison()
    feature = value["units"][0]["features"][0]
    feature.update(outcome="equivalent", rationale="A geometric construction now supplies the same inference; layout need not match")
    assert subject.validate_comparison(value, contract(), {"media": "current"}, 30)["status"] == "pass"


def test_honest_loss_is_recorded_but_not_publishable():
    value = comparison()
    value.update(status="revise", release_authorized=False, blocking_findings=["The reason was replaced with a terminal answer"])
    value["units"][0]["features"][0].update(outcome="lost", evidence=[])
    assert subject.validate_comparison(value, contract(), {"media": "current"}, 30)["status"] == "revise"


def test_baseline_bytes_and_contract_are_bound(tmp_path):
    media = tmp_path / "old.mp4"
    media.write_bytes(b"baseline hash fixture, not playable media")
    value = contract()
    value["assets"]["baseline"]["sha256"] = subject.sha(media)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value))
    _, bindings = subject.contract_bindings(path, tmp_path)
    assert bindings["revision_contract_sha256"] == subject.sha(path)
    media.write_bytes(b"different media")
    with pytest.raises(ValueError, match="baseline media changed"):
        subject.contract_bindings(path, tmp_path)


@pytest.mark.parametrize("plan", [
    {"workflow_profile": "configs/visual-first-workflow-v3.json"},
    {"revision_mode": "revision"},
    {"revision_mode": "fresh", "revision_contract": "baseline.json", "revision_review": "review.json"},
])
def test_revision_intent_cannot_omit_its_required_inputs(plan):
    with pytest.raises(ValueError):
        subject.revision_required(plan)


def test_fresh_projects_are_not_forced_to_imitate_an_older_film():
    assert not subject.revision_required({"workflow_profile": "configs/visual-first-workflow-v3.json", "revision_mode": "fresh"})


def test_profile_alias_does_not_bypass_revision_declaration():
    with pytest.raises(ValueError, match="Declare fresh or revision"):
        subject.revision_required({"workflow_profile": "configs/custom-name.json"}, profile_version="understanding-first-v3")


def test_good_blind_review_still_cannot_release_a_revision_without_comparison(monkeypatch, tmp_path):
    from test_understanding_film import report
    value = report()
    film.common.write_json(tmp_path / "plan.json", {"revision_mode": "revision", "revision_contract": "missing-contract.json", "revision_review": "missing-review.json"})
    film.common.write_json(tmp_path / "timeline.json", {"duration": 20})
    review = tmp_path / "review.json"
    film.common.write_json(review, value)
    monkeypatch.setattr(film, "bindings", lambda *_: value["bindings"])
    with pytest.raises(FileNotFoundError):
        film.require_review(tmp_path, review)


def test_publisher_checks_the_actual_comparison_not_only_a_prompt(monkeypatch, tmp_path):
    plan = {"revision_mode": "revision", "revision_contract": "contract.json", "revision_review": str(tmp_path / "comparison.json")}
    film.common.write_json(tmp_path / "plan.json", plan)
    film.common.write_json(tmp_path / "timeline.json", {"duration": 30})
    value = comparison()
    value.update(status="revise", release_authorized=False, blocking_findings=["missing effective detail"])
    value["units"][0]["features"][0]["outcome"] = "lost"
    film.common.write_json(tmp_path / "comparison.json", value)
    monkeypatch.setattr(film.regression, "contract_bindings", lambda *_: (contract(), {}))
    monkeypatch.setattr(film, "bindings", lambda *_: {"media": "current"})
    with pytest.raises(ValueError, match="must pass independently"):
        film.require_regression(tmp_path)
