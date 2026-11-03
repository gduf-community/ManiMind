"""Whole-chapter inventory and create-only supervision, not media approval."""

import json
from types import SimpleNamespace

import pytest

from manimind.experiments.chapter_workflow import coverage_status, paths, stage_lock, write_once
from manimind.experiments import chapter_workflow as workflow


def unit():
    return {"lessons": [{"project_id": f"lesson-{i}"} for i in range(1, 9)]}


def test_one_lesson_cannot_complete_a_chapter():
    result = coverage_status(unit(), ["lesson-1"])
    assert not result["complete"] and result["expected"] == 8 and result["released"] == 1
    assert len(result["missing"]) == 7


def test_exact_inventory_is_still_not_media_approval():
    result = coverage_status(unit(), [f"lesson-{i}" for i in range(1, 9)])
    assert result["complete"] and not result["missing"]
    assert "not media approval" in result["scope"]


@pytest.mark.parametrize("ids", [["lesson-1", "lesson-1"], ["alien"]])
def test_duplicate_and_unknown_releases_rejected(ids):
    with pytest.raises(ValueError):
        coverage_status(unit(), ids)


def test_write_is_create_only_and_same_data_is_resume_safe(tmp_path):
    target = tmp_path / "nested/packet.json"
    write_once(target, {"stage": "draft"})
    before = target.read_bytes()
    write_once(target, {"stage": "draft"})
    assert target.read_bytes() == before
    with pytest.raises(ValueError):
        write_once(target, {"stage": "approved"})


def test_active_or_orphan_lock_is_not_replayed(tmp_path):
    with stage_lock(tmp_path, "render"):
        assert json.loads((tmp_path / "active-stage.json").read_text())["stage"] == "render"
        with pytest.raises(RuntimeError):
            with stage_lock(tmp_path, "render"):
                pass
    assert not (tmp_path / "active-stage.json").exists()
    (tmp_path / "active-stage.json").write_text('{"pid":-1}', encoding="utf-8")
    with pytest.raises(RuntimeError):
        with stage_lock(tmp_path, "render"):
            pass


def test_lock_cleans_up_after_reported_error(tmp_path):
    with pytest.raises(ValueError):
        with stage_lock(tmp_path, "render"):
            raise ValueError("retained failure")
    assert not (tmp_path / "active-stage.json").exists()


@pytest.mark.parametrize("project,version", [("../outside", "v001"), ("ok", "latest"), ("/tmp/x", "v001")])
def test_paths_reject_unsafe_or_implicit_versions(project, version):
    with pytest.raises(ValueError):
        paths(project, version)


def test_distinct_lessons_have_distinct_execution_and_media_paths():
    left, right = paths("lesson-a", "v001"), paths("lesson-b", "v001")
    assert left["session"] != right["session"] and left["visual"] != right["visual"]


def test_text_only_revision_keeps_explicit_approved_visual():
    result = paths("lesson-a", "v002", "v001")
    assert result["visual"].name == "visual-v001"
    assert result["visual_review"].name == "visual-v001.json"
    assert result["narration"].name == "narration-v002.json"
    assert result["silent"].name == "silent-v002"
    assert result["narration_review"].name == "narration-v002.json"


@pytest.mark.parametrize("requested", ['broken json', '{"title":"changed"}'])
def test_retained_render_does_not_ignore_changed_request(tmp_path, monkeypatch, requested):
    visual = tmp_path / "visual"
    visual.mkdir()
    (visual / "render.json").write_text('{}')
    (visual / "plan.json").write_text('{"title":"original"}')
    plan = tmp_path / "plan.json"
    plan.write_text(requested)
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "paths", lambda *_: {"session": tmp_path / "session", "visual": visual, "plan": plan})
    monkeypatch.setattr(workflow.unit_film, "bindings", lambda *_: pytest.fail("Changed request reached reuse"))
    with pytest.raises((ValueError, json.JSONDecodeError)):
        workflow.execute(SimpleNamespace(project="lesson-a", version="v001", stage="render"))


def test_retained_render_rechecks_exact_requested_plan(tmp_path, monkeypatch):
    visual = tmp_path / "visual"
    visual.mkdir()
    (visual / "render.json").write_text('{}')
    (visual / "plan.json").write_text('{"title":"same"}')
    plan = tmp_path / "plan.json"
    plan.write_text('{"title":"same"}')
    called = []
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "paths", lambda *_: {"session": tmp_path / "session", "visual": visual, "plan": plan})
    monkeypatch.setattr(workflow.unit_film, "bindings", lambda value: called.append(value))
    assert workflow.execute(SimpleNamespace(project="lesson-a", version="v001", stage="render"))["completed_stage"] == "render"
    assert called == [visual]


def test_retained_alignment_rejects_nonexistent_new_inputs(tmp_path, monkeypatch):
    alignment = tmp_path / "alignment"
    alignment.mkdir()
    (alignment / "alignment.json").write_text('{}')
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "paths", lambda *_: {"session": tmp_path / "session", "alignment": alignment,
                                                     "speech_plan": tmp_path / "missing-plan.json"})
    monkeypatch.setattr(workflow.unit_film, "audio_bindings", lambda *_: pytest.fail("New nonexistent inputs reached reuse"))
    with pytest.raises(FileNotFoundError):
        workflow.execute(SimpleNamespace(project="lesson-a", version="v001", stage="align", voice_plan=None,
                                         speech=tmp_path / "missing-speech", timings=tmp_path / "missing-timings.json"))


@pytest.mark.parametrize("change", ["path", "bytes", "missing"])
def test_retained_narration_checks_requested_draft(tmp_path, monkeypatch, change):
    visual = tmp_path / "visual"
    visual.mkdir()
    original = tmp_path / "draft.json"
    original.write_text('{"units":[]}')
    review = tmp_path / "visual-review.json"
    review.write_text('{}')
    (visual / "plan.json").write_text(json.dumps({"narration_draft": str(original)}))
    narration = tmp_path / "narration.json"
    narration.write_text(json.dumps({"source_draft": str(original), "source_draft_sha256": workflow.common.sha(original),
                                    "visual_review": str(review), "visual_review_sha256": workflow.common.sha(review)}))
    requested = original
    if change == "path":
        requested = tmp_path / "other.json"
        requested.write_bytes(original.read_bytes())
    elif change == "bytes":
        original.write_text('{"units":["changed"]}')
    else:
        requested = tmp_path / "missing.json"
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "paths", lambda *_: {"session": tmp_path / "session", "visual": visual,
                                                     "narration": narration, "visual_review": review})
    monkeypatch.setattr(workflow.unit_film, "bindings", lambda *_: pytest.fail("Mismatched request reached reused narration"))
    with pytest.raises((ValueError, FileNotFoundError)):
        workflow.execute(SimpleNamespace(project="lesson-a", version="v002", visual_version="v001",
                                         narration_draft=requested, stage="install"))


def test_retained_silent_checks_selected_paths_and_bindings(tmp_path, monkeypatch):
    p = {key: tmp_path / key for key in ("silent", "visual", "narration", "visual_review", "narration_review")}
    for key in ("visual", "narration", "visual_review", "narration_review"):
        p[key].touch()
    retained = {"attempt": str(p["visual"]), "narration": str(p["narration"]),
                "visual_review": str(p["visual_review"]), "narration_review": str(p["narration_review"]),
                "bindings": {"current": True}}
    monkeypatch.setattr(workflow.unit_film, "verify_delivery", lambda *_: retained)
    monkeypatch.setattr(workflow.unit_film, "bindings", lambda *_: {"current": True})
    assert workflow.selected_silent(p) == retained
    with pytest.raises(FileNotFoundError):
        workflow.selected_silent({**p, "visual": tmp_path / "missing-visual"})
    alternate = tmp_path / "different-visual"
    alternate.touch()
    with pytest.raises(ValueError, match="Requested visual"):
        workflow.selected_silent({**p, "visual": alternate})
    monkeypatch.setattr(workflow.unit_film, "bindings", lambda *_: {"current": False})
    with pytest.raises(ValueError, match="bindings differ"):
        workflow.selected_silent(p)


def test_retained_speech_plan_checks_requested_reference(tmp_path, monkeypatch):
    p = {"session": tmp_path / "session", "speech_plan": tmp_path / "speech-plan.json", "silent": tmp_path / "silent"}
    p["silent"].mkdir()
    delivery = p["silent"] / "delivery.json"
    delivery.write_text('{}')
    original = tmp_path / "original.wav"
    original.write_bytes(b"original")
    requested = tmp_path / "other.wav"
    requested.write_bytes(b"other")
    p["speech_plan"].write_text(json.dumps({"source": {"delivery": str(delivery), "delivery_sha256": workflow.common.sha(delivery)},
                                          "reference_source": str(original), "reference_sha256": workflow.common.sha(original)}))
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "paths", lambda *_: p)
    monkeypatch.setattr(workflow, "selected_silent", lambda *_: {})
    monkeypatch.setattr(workflow.unit_film, "verify_speech_source", lambda *_: pytest.fail("Wrong selected reference reached reuse"))
    with pytest.raises(ValueError, match="source/reference differs"):
        workflow.execute(SimpleNamespace(project="lesson-a", version="v002", reference=requested, stage="speech-plan"))


def test_prepare_preserves_explicit_revised_scientific_brief(tmp_path, monkeypatch):
    project = tmp_path / "runtime/projects/lesson-a"
    project.mkdir(parents=True)
    context = project / "context.json"
    context.write_text('{}')
    brief = project / "science-v002.json"
    brief.write_text(json.dumps({"project_id": "lesson-a", "lesson_design": {"new_understanding": ["revised scope"]}}))
    catalogue = tmp_path / "catalogue.csv"
    catalogue.touch()
    draft = project / "draft-v002.json"
    draft.write_text(json.dumps({"scientific_brief": str(brief), "author_agent": "author", "author_context": "author"}))
    p = {"project": project, "context": context, "draft": draft, "plan": project / "plan.json",
         "brief": project / "unused-v001.json", "session": tmp_path / "session"}
    monkeypatch.setenv("CODEX_THREAD_ID", "test-controller")
    monkeypatch.setattr(workflow, "ROOT", tmp_path)
    monkeypatch.setattr(workflow, "UNIT", project / "unit.json")
    monkeypatch.setattr(workflow.curriculum, "__file__", str(tmp_path / "curriculum.py"))
    monkeypatch.setattr(workflow, "paths", lambda *_: p)
    monkeypatch.setattr(workflow.curriculum, "verify_context", lambda *_: {
        "audience": "learner", "entry_assumptions": [], "sources": {"catalogue": str(catalogue)},
        "current_lesson": {"new_understanding": "fallback"}})
    workflow.execute(SimpleNamespace(project="lesson-a", version="v002", stage="prepare"))
    retained = json.loads(p["plan"].read_text())
    assert retained["scientific_brief"] == str(brief.relative_to(tmp_path))
    assert retained["understanding_goals"] == ["revised scope"]
    assert str(brief.relative_to(tmp_path)) in retained["sources"]
