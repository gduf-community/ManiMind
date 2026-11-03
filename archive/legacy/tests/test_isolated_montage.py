from pathlib import Path

import pytest

from manimind.experiments import isolated_montage as montage


@pytest.fixture
def approved(tmp_path):
    card = tmp_path / "card.png"
    card.write_bytes(b"fixture")
    plan = tmp_path / "plan.json"
    montage.pilot.write_json(plan, {"parts": [
        {"kind": "card", "source": str(card), "sha256": montage.pilot.sha256(card), "seconds": 6}]})
    review = tmp_path / "review.json"
    montage.pilot.write_json(review, {
        "status": "approved", "blockers": [], "reviewer_role": "reviewer",
        "reviewer_id": "independent", "scope": "experimental_comparison_edit",
        "plan_sha256": montage.pilot.sha256(plan),
        "implementation_sha256": montage.pilot.sha256(Path(montage.__file__))})
    return plan, review, card


def test_only_approved_unchanged_edit_is_accepted(approved):
    plan, review, _ = approved
    assert len(montage.validate(plan, review)["parts"]) == 1


@pytest.mark.parametrize("mutation", [
    {"status": "rejected"}, {"blockers": ["issue"]}, {"reviewer_role": "author"},
    {"scope": "classroom_video"}, {"plan_sha256": "changed"},
    {"implementation_sha256": "changed"},
])
def test_bad_approval_is_rejected(approved, mutation):
    plan, review, _ = approved
    data = montage.pilot.read_json(review)
    data.update(mutation)
    montage.pilot.write_json(review, data)
    with pytest.raises(ValueError):
        montage.validate(plan, review)


def test_source_change_invalidates_edit(approved):
    plan, review, card = approved
    card.write_bytes(b"changed")
    with pytest.raises(ValueError, match="source changed"):
        montage.validate(plan, review)


def test_rejected_sample_cannot_use_ordinary_comparison_approval(approved):
    plan, review, _ = approved
    data = montage.pilot.read_json(plan)
    data["parts"][0]["kind"] = "diagnostic"
    montage.pilot.write_json(plan, data)
    approval = montage.pilot.read_json(review)
    approval["plan_sha256"] = montage.pilot.sha256(plan)
    montage.pilot.write_json(review, approval)
    with pytest.raises(ValueError, match="separate diagnostic"):
        montage.validate(plan, review)


def test_wrong_review_scope_cannot_relabel_diagnostic_plan(approved):
    plan, review, _ = approved
    data = montage.pilot.read_json(plan)
    data["scope"] = "experimental_diagnostic_edit"
    montage.pilot.write_json(plan, data)
    approval = montage.pilot.read_json(review)
    approval["plan_sha256"] = montage.pilot.sha256(plan)
    montage.pilot.write_json(review, approval)
    with pytest.raises(ValueError, match="approval required"):
        montage.validate(plan, review)
