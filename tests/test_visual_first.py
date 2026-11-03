import copy
import json

import pytest

from manimind.experiments import sol_visual_first as module
from manimind.experiments import freeform_review_cycle
from manimind.experiments.visual_first_data import check_visual_source, narration_plan, validate_events, visual_timeline
from manimind.postproduce import pilot
from manimind.review.learning_quality import DIMENSIONS


def plan():
    return {"title": "Engineering fixture, not a model video", "rationale": "Fixture only", "cues": [{
        "id": "observe", "heading": "Observe", "visual": "A basic state change",
        "learning_purpose": "Test visual clock", "duration": 2,
        "anchors": [{"id": "visible", "meaning": "State becomes visible"}]}]}


def test_visual_clock_is_independent_of_speech_and_can_exist_without_audio():
    first = plan()
    first["cues"][0]["spoken"] = "A hypothetical very long narration"
    a = visual_timeline(first)
    first["cues"][0]["spoken"] = "Short"
    assert a["duration"] == visual_timeline(first)["duration"] == 2
    assert a["cues"][0]["spoken_spans"] == []


@pytest.mark.parametrize("duration", [0, -1, True, float("nan"), float("inf")])
def test_invalid_visual_durations_are_rejected(duration):
    data = plan()
    data["cues"][0]["duration"] = duration
    with pytest.raises(ValueError, match="duration"):
        visual_timeline(data)


def test_duplicate_anchors_and_unmeasured_or_out_of_range_events_are_rejected():
    data = plan()
    data["cues"][0]["anchors"] *= 2
    with pytest.raises(ValueError, match="unique"):
        visual_timeline(data)
    timeline = visual_timeline(plan())
    for rows in ([], [{"id": "unknown", "time": 1}], [{"id": "visible", "time": 2}],
                 [{"id": "visible", "time": float("nan")}], [{"id": "visible", "time": True}]):
        with pytest.raises(ValueError):
            validate_events(timeline, {"duration": 2, "events": rows})


def test_later_narration_binds_to_measured_events_without_modifying_the_clock():
    timeline = visual_timeline(plan())
    before = copy.deepcopy(timeline)
    events = {"duration": 2, "events": [{"id": "visible", "time": .75}]}
    result = narration_plan({"segments": [{"cue": "observe", "anchor": "visible", "relation": "after", "text": "A natural explanation"}]}, timeline, events)
    assert result["segments"][0]["anchor_time"] == .75
    assert timeline == before and result["audio_status"] == "not_generated"
    assert result["alignment_status"] == "semantic_intent_only_not_final_audio_timing"
    result["segments"][0]["anchor"] = "imagined"
    with pytest.raises(ValueError, match="measured event"):
        narration_plan(result, timeline, events)


def test_visual_source_validation_does_not_rewrite_bytes_or_allow_helper_io():
    source = "from manimind.experiments.visual_first_support import VisualLessonScene\nclass GeneratedLesson(VisualLessonScene):\n def construct(self): self.mark('visible')\n"
    before = source
    check_visual_source(source)
    assert source == before
    with pytest.raises(ValueError):
        check_visual_source("from manimind.experiments.visual_first_support import json")
    with pytest.raises(ValueError):
        check_visual_source(source + "\nopen('secret')")


@pytest.fixture
def value(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    item = module.SolVisualFirst.__new__(module.SolVisualFirst)
    item.id = "test-visual-first"
    item.out = tmp_path / "out"
    item.context = tmp_path / "context"
    item.session = tmp_path / "session"
    item.spec_path = item.out / "spec.json"
    item.config_path = tmp_path / "provider.json"
    item.config = pilot.read_json(pilot.ROOT / "configs/sol61-visual-first-20261024.json")
    pilot.write_json(item.config_path, item.config)
    monkeypatch.setattr(item, "frozen_paths", lambda: [item.config_path])
    item.initialize()
    item.team = pilot.read_json(item.team_path)
    item.current_step = item.session / "test-step"
    item.current_step.mkdir()
    return item


def test_initial_visual_plan_never_invokes_tts(value, monkeypatch):
    from manimind.postproduce import freeform_pilot

    async def forbidden(*args):
        raise AssertionError("Visual planning invoked TTS")

    monkeypatch.setattr(freeform_pilot.Production, "prepare", forbidden)
    state = pilot.read_json(value.state_path)
    result = value.install_visual_plan(plan(), state)
    assert result["audio_generated"] is False and not (value.out / "audio").exists()
    assert pilot.read_json(value.out / "timeline.json")["mode"] == "visual_first_silent"
    assert "spoken_spans" in result["visual_timeline"]["cues"][0]


def test_narration_cannot_precede_genuine_visual_approval(value):
    with pytest.raises(ValueError, match="independent visual approval"):
        value.dispatch_role("director", {"action": "write_narration", "args": {"plan": {}}}, {})
    assert not (value.out / "narration-plan.json").exists()


def test_creator_cannot_approve_or_write_director_narration(value):
    for action in ("finish", "request_review", "write_narration", "write_visual_plan"):
        with pytest.raises(ValueError, match="not available"):
            value.dispatch_role("creator", {"action": action, "args": {}}, {})


def test_visual_revision_invalidates_reviews_and_archives_later_narration(value):
    value.team.update(visual_review={"path": "old"}, narration_review={"path": "old"})
    pilot.write_json(value.out / "narration-plan.json", {"segments": []})
    pilot.write_json(value.out / "visual-events.json", {"events": []})
    state = pilot.read_json(value.state_path)
    value.invalidate_visual(state)
    assert value.team["visual_review"] is value.team["narration_review"] is None
    assert (value.current_step / "before-narration-plan.json").exists()
    assert not (value.out / "narration-plan.json").exists()


def test_silent_reviewer_only_receives_public_goal_boundaries_and_pixels(value, monkeypatch):
    pilot.write_json(value.out / "timeline.json", visual_timeline(plan()))
    (value.out / "candidate.py").write_text("SOURCE_SENTINEL")
    pilot.write_json(value.spec_path, {"private_intent": "PLAN_SENTINEL"})
    pilot.write_json(value.out / "review-input.json", {
        "cue_ids": ["observe"], "duration": 2, "hashes": {"visual": "same"}, "video_sha256": "video",
        "frames": [{"cue": "observe", "time": .5, "path": "current.jpg"}], "temporal_evidence": []})
    value.team["actors"]["director"]["observed"] = ["observe"]
    monkeypatch.setattr(value, "latest_video", lambda state: (value.out / "video.mp4", 2))
    monkeypatch.setattr(value, "hashes", lambda: {"visual": "same"})
    seen = []

    def review(label, text, *args):
        seen.append(json.loads(text))
        return {"review": {"status": "revise"}}

    monkeypatch.setattr(value, "review_batch", review)
    value.review_current({})
    assert "SENTINEL" not in json.dumps(seen)
    assert seen[0]["review_mode"] == "visual"
    assert value.team["visual_phase"] == "visual_revision"


def test_finish_cannot_bypass_independent_reviews(value):
    with pytest.raises(ValueError, match="independent visual approval"):
        value.release_silent({})
    assert not (value.out / "delivery.json").exists()


def test_real_silent_runtime_smoke(value, monkeypatch):
    """Engineering fixture only: no model request, speech, or teaching-quality claim."""
    module.preload_runtime()
    state = pilot.read_json(value.state_path)
    value.install_visual_plan(plan(), state)
    value.current_step = value.session / "code-step"
    value.current_step.mkdir()
    source = """from manimlib import *
from manimind.experiments.visual_first_support import VisualLessonScene

class GeneratedLesson(VisualLessonScene):
    def construct(self):
        dot = Dot(color=TEAL)
        label = self.cn('Engineering fixture', size=24).shift(UP)
        self.add(dot, label)
        self.play(dot.animate.shift(RIGHT), run_time=1)
        self.mark('visible')
        self.until(2)
"""
    value.install_source(source, state)
    value.current_step = value.session / "render-step"
    value.current_step.mkdir()
    result = value.render_silent(state)
    assert result["receipt"]["tool_success"], result
    streams = pilot.probe(result["receipt"]["video_path"])["streams"]
    assert [s["codec_type"] for s in streams] == ["video"]
    assert validate_events(pilot.read_json(value.out / "timeline.json"),
                           pilot.read_json(value.out / "visual-events.json"))[0]["time"] == pytest.approx(1)
    assert not (value.out / "audio").exists()
    value.save_state(state)
    value.team["actors"]["director"]["observed"] = ["observe"]
    evidence = pilot.read_json(value.out / "review-input.json")
    contexts = []

    def offline_review(role, stage, text, images):
        assert role == "reviewer"
        contexts.append(text)
        directory = value.review_session / f"request-{len(contexts):04d}"
        directory.mkdir()
        answer = {"action": "review", "status": "pass",
                  "checks": {k: "pass" for k in ("mathematics", "visual_layout", "narrative", "cue_timing")},
                  "inspected_cues": [{"id": "observe", "observations": [{
                      "time": evidence["frames"][0]["time"], "detail": "Engineering fixture pixels only"}]}],
                  "issues": [], "limitations": ["Synthetic test review, not actual model approval"],
                  "viewer_test": {"can_explain": "A visible state change", "missing_links": [],
                                  "transfer_question": "Another state", "supported_answer": "Fixture only"},
                  "quality": {k: {"rating": 4, "evidence": "Engineering fixture, not teaching quality"} for k in DIMENSIONS}}
        pilot.write_json(directory / "answer.txt", answer)
        pilot.write_json(directory / "input.json", {"text": text, "images": [
            {"path": str(p), "sha256": pilot.sha256(p)} for p in images]})
        pilot.write_json(directory / "record.json", {
            "role": "reviewer", "status": "received", "usage": [],
            "input_sha256": pilot.sha256(directory / "input.json"),
            "answer_sha256": pilot.sha256(directory / "answer.txt")})
        return json.dumps(answer), directory

    monkeypatch.setattr(value, "role_request", offline_review)
    assert value.review_current(state)["raw_independent_review"]["status"] == "pass"
    assert '"current_source"' not in contexts[0] and '"visual_plan"' not in contexts[0]
    assert value.approval("visual")["kind"] == "visual"
    clock = (value.out / "timeline.json").read_bytes()
    value.current_step = value.session / "narration-step"
    value.current_step.mkdir()
    value.dispatch_role("director", {"action": "write_narration", "args": {"plan": {
        "segments": [{"cue": "observe", "anchor": "visible", "relation": "after", "text": "Fixture explanation"}]}}}, state)
    value.verify()
    assert (value.out / "timeline.json").read_bytes() == clock
    assert value.review_current(state)["raw_independent_review"]["status"] == "pass"
    assert '"current_source"' in contexts[1] and '"narration_draft"' in contexts[1]
    delivery = value.release_silent(state)
    assert delivery["audio_status"] == "not_generated" and delivery["full_decode_passed"]
    assert [s["codec_type"] for s in pilot.probe(delivery["video"])["streams"]] == ["video"]
    # Editing only speech text does not invalidate pixels, but cannot reuse text approval.
    draft = pilot.read_json(value.out / "narration-plan.json")
    draft["segments"][0]["text"] = "External edit must be rejected"
    pilot.write_json(value.out / "narration-plan.json", draft)
    assert value.approval("visual")["status"] == "pass"
    with pytest.raises(ValueError, match="Narration changed"):
        value.approval("narration")
    with pytest.raises(ValueError, match="outside its original"):
        value.verify()
