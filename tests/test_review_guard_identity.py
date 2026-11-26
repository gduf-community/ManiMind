"""review_guard.identity: one reviewer context per lesson/version/stage."""

import json

import pytest

from manimind.review_guard import identity


def test_same_reviewer_second_lesson_is_rejected(tmp_path):
    registry = tmp_path / "review-identities.json"
    identity.register(registry, "rev-a", "ctx-a", "lesson-03", "visual-v011", "visual")
    with pytest.raises(ValueError, match="already reviewed lesson-03"):
        identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v013", "visual")
    assert len(json.loads(registry.read_text(encoding="utf-8"))["entries"]) == 1


def test_same_lesson_other_version_or_stage_is_rejected(tmp_path):
    registry = tmp_path / "r.json"
    identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v011", "visual")
    with pytest.raises(ValueError):
        identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v013", "visual")
    with pytest.raises(ValueError):
        identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v011", "content_regression")


def test_relabeling_agent_or_context_does_not_create_fresh_identity(tmp_path):
    registry = tmp_path / "r.json"
    identity.register(registry, "rev-a", "ctx-a", "lesson-03", "v1", "visual")
    with pytest.raises(ValueError):
        identity.register(registry, "rev-new", "ctx-a", "lesson-04", "v1", "visual")
    with pytest.raises(ValueError):
        identity.register(registry, "rev-a", "ctx-new", "lesson-04", "v1", "visual")
    with pytest.raises(ValueError):  # context reused as agent id
        identity.register(registry, "ctx-a", "other", "lesson-04", "v1", "visual")


def test_idempotent_same_assignment_and_fresh_reviewer_allowed(tmp_path):
    registry = tmp_path / "r.json"
    first = identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v013", "visual")
    again = identity.register(registry, "rev-a", "ctx-a", "lesson-04", "visual-v013", "visual")
    assert first == again
    identity.register(registry, "rev-b", "ctx-b", "lesson-04", "visual-v013", "content_regression")
    value = identity.load(registry)
    assert [e["reviewer_agent"] for e in value["entries"]] == ["rev-a", "rev-b"]
    assert value["writer"] and value["lifecycle"] and value["invalidation"]


@pytest.mark.parametrize("bad", ["", " rev", None])
def test_explicit_identity_required(tmp_path, bad):
    with pytest.raises(ValueError):
        identity.register(tmp_path / "r.json", bad, "ctx", "lesson", "v1", "visual")


def test_unknown_stage_rejected(tmp_path):
    with pytest.raises(ValueError, match="stage"):
        identity.register(tmp_path / "r.json", "a", "b", "lesson", "v1", "first_look")


def test_cli(tmp_path, capsys):
    registry = str(tmp_path / "r.json")
    base = ["--agent", "a", "--context", "b", "--version", "v1", "--stage", "visual"]
    assert identity.main(["register", registry, "--lesson", "L3", *base]) == 0
    assert identity.main(["check", registry, "--lesson", "L4", *base]) == 1
    assert '"allowed": false' in capsys.readouterr().out
