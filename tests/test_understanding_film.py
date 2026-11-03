import json
from pathlib import Path
import wave

import pytest

from manimind.postproduce import understanding_film as subject
from manimind.review.learning_quality import DIMENSIONS


def report():
    return {"action": "review", "stage": "visual", "status": "pass", "reviewer_role": "independent",
            "reviewer_agent": "fixture-reviewer", "bindings": {"visual": "current"},
            "release_authorized": True, "blocking_findings": [], "listening_reviewed": False, "student_tested": False,
            "viewer_test": {"can_explain": "visible reason", "missing_links": [], "transfer_question": "new case",
                            "supported_answer": "reason is supported, not student tested"},
            "quality": {name: {"rating": 4, "evidence": "3s state"} for name in DIMENSIONS},
            "editorial_checks": {name: {"status": "pass", "evidence": [{"time": 3, "finding": "actual state"}]}
                                 for name in subject.quality.CHECKS}}


@pytest.mark.parametrize("mutation", ["stage", "hash", "role", "revoke", "quality", "mechanism", "blocker"])
def test_current_editorial_quality_is_required_before_any_publication(monkeypatch, tmp_path, mutation):
    monkeypatch.setattr(subject, "bindings", lambda *_: {"visual": "current"})
    subject.common.write_json(tmp_path / "timeline.json", {"duration": 20})
    subject.common.write_json(tmp_path / "plan.json", {})
    value = report()
    if mutation == "stage": value["stage"] = "narration"
    if mutation == "hash": value["bindings"] = {"visual": "stale"}
    if mutation == "role": value["reviewer_role"] = "author"
    if mutation == "revoke": value["release_authorized"] = False
    if mutation == "quality": value["quality"]["causality"]["rating"] = 2
    if mutation == "mechanism": value["editorial_checks"]["mechanism"]["status"] = "revise"
    if mutation == "blocker": value["blocking_findings"] = ["Main evidence is not visible"]
    path = tmp_path / "review.json"
    subject.common.write_json(path, value)
    with pytest.raises(ValueError):
        subject.require_review(tmp_path, path)


def test_real_stage_appropriate_pass_can_proceed(monkeypatch, tmp_path):
    monkeypatch.setattr(subject, "bindings", lambda *_: {"visual": "current"})
    subject.common.write_json(tmp_path / "timeline.json", {"duration": 20})
    subject.common.write_json(tmp_path / "plan.json", {})
    path = tmp_path / "review.json"
    subject.common.write_json(path, report())
    assert subject.require_review(tmp_path, path)["release_authorized"] is True


def test_install_text_is_after_review_and_binds_measured_visuals(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(subject, "require_review", lambda *_: calls.append("review"))
    monkeypatch.setattr(subject.visual, "bindings", lambda *_: {"visual": "current"})
    subject.common.write_json(tmp_path / "timeline.json", {"duration": 20, "cues": [{"id": "cue"}]})
    subject.common.write_json(tmp_path / "focus-events.json", {"duration": 20, "windows": [{"id": "result", "start": 1, "end": 15}]})
    draft = tmp_path / "draft.json"
    subject.common.write_json(draft, {"segments": [{"id": "N01", "cue": "cue", "focus": "result", "text": "A fresh explanation"}]})
    target = tmp_path / "approved-text.json"
    value = subject.install_narration(tmp_path, draft, tmp_path / "review.json", target)
    assert calls == ["review"] and value["audio_status"] == "not_generated"
    assert value["visual_bindings"] == {"visual": "current"}
    with pytest.raises(FileExistsError):
        subject.install_narration(tmp_path, draft, tmp_path / "review.json", target)


def test_silent_release_has_no_work_before_both_reviews_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(subject, "require_review", lambda *_ , **__: (_ for _ in ()).throw(ValueError("not approved")))
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="not approved"):
        subject.release_silent(tmp_path, tmp_path / "text.json", tmp_path / "visual-review.json", tmp_path / "text-review.json", output)
    assert not output.exists()


def test_empty_or_truncated_alignment_cannot_pass_as_silence(monkeypatch, tmp_path):
    path = tmp_path / "alignment.json"
    plan_path = tmp_path / "plan.json"
    subject.common.write_json(plan_path, {"source": {"video": "fixture"}, "segments": [{"id": "N01"}]})
    subject.common.write_json(path, {"plan": str(plan_path), "plan_sha256": subject.common.sha(plan_path),
                                  "source": {"video": "fixture"}, "duration": 20, "segments": [], "inputs": []})
    monkeypatch.setattr(subject, "verify_speech_source", lambda _: {"duration": 20})
    with pytest.raises(ValueError, match="every current planned utterance"):
        subject.audio_bindings(path)


@pytest.fixture
def speech_fixture(monkeypatch, tmp_path):
    segments = [{"id": f"N{i}", "cue": "demo", "focus": f"window{i}", "text": f"Sentence {i}"} for i in (1, 2)]
    focus = tmp_path / "focus-events.json"
    timeline = tmp_path / "timeline.json"
    subject.common.write_json(focus, {"duration": 20, "windows": [
        {"id": "window1", "start": 1, "end": 6}, {"id": "window2", "start": 8, "end": 14}]})
    subject.common.write_json(timeline, {"duration": 20, "cues": [{"id": "demo"}]})
    narration = tmp_path / "narration.json"
    subject.common.write_json(narration, {"segments": segments})
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"hash-only fixture, not a playable video")
    delivery_path = tmp_path / "delivery.json"
    subject.common.write_json(delivery_path, {"fixture": True})
    delivery = {"attempt": str(tmp_path), "video": str(video), "sha256": subject.common.sha(video),
                "narration": str(narration), "duration": 20, "bindings": {"focuses_sha256": subject.common.sha(focus)}}
    monkeypatch.setattr(subject, "verify_delivery", lambda _: delivery)
    plan = {"schema_version": 2, "synthetic_reference": True, "reference_source": "synthetic V01",
            "reference_sha256": subject.vox.REFERENCE_SHA256, "reference_text": subject.vox.audition.TEXT,
            "generation": subject.vox.GENERATION, "segments": segments,
            "source": {"delivery": str(delivery_path), "delivery_sha256": subject.common.sha(delivery_path),
                       "video": str(video), "video_sha256": subject.common.sha(video),
                       "focuses": str(focus), "focuses_sha256": subject.common.sha(focus)}}
    plan_path = tmp_path / "speech-plan.json"
    subject.common.write_json(plan_path, plan)
    inputs = []
    for segment in segments:
        wav = tmp_path / f"{segment['id']}.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"\x10\x00\xf0\xff" * 24000)
        receipt = wav.with_suffix(".receipt.json")
        subject.common.write_json(receipt, {
            "id": segment["id"], "segment": segment, "request": {"text": segment["text"]},
            "plan_sha256": subject.common.sha(plan_path), "wav_sha256": subject.common.sha(wav),
            "reference_sha256": plan["reference_sha256"], "first_take": True, "segment_call_count": 1,
            "acceptance": subject.vox.ACCEPTANCE, "worker_sha256": subject.common.sha(subject.vox.__file__),
            "helper_sha256": subject.vox.HELPER_SHA256})
        inputs.append({"wav": str(wav), "sha256": subject.common.sha(wav),
                       "receipt": str(receipt), "receipt_sha256": subject.common.sha(receipt)})
    rows = subject.schedule(subject.common.read_json(timeline), {"segments": segments}, subject.common.read_json(focus), [1, 1])
    alignment = {"plan": str(plan_path), "plan_sha256": subject.common.sha(plan_path), "source": plan["source"],
                 "duration": 20, "segments": rows, "inputs": inputs}
    return plan, plan_path, alignment


@pytest.mark.parametrize("target", ["focuses", "video"])
def test_speech_plan_cannot_replace_reviewed_source_with_self_reported_hash(speech_fixture, tmp_path, target):
    plan, _, _ = speech_fixture
    assert subject.verify_speech_source(plan)["duration"] == 20
    replacement = tmp_path / f"unreviewed-{target}"
    replacement.write_bytes(b"different unreviewed source")
    plan["source"][target] = str(replacement)
    plan["source"]["focuses_sha256" if target == "focuses" else "video_sha256"] = subject.common.sha(replacement)
    with pytest.raises(ValueError, match="reviewed visuals/text/focus"):
        subject.verify_speech_source(plan)


@pytest.mark.parametrize("mutation", ["id", "text", "reference", "plan", "sample_rate", "clipped", "swapped", "worker"])
def test_final_audio_gate_rechecks_each_receipt_and_pcm(speech_fixture, monkeypatch, tmp_path, mutation):
    _, _, alignment = speech_fixture
    path = tmp_path / "alignment.json"
    if mutation == "swapped":
        alignment["inputs"].reverse()
    elif mutation in {"sample_rate", "clipped"}:
        original = subject.common.pcm_info
        def invalid_pcm(source):
            info, pcm = original(source)
            info["sample_rate" if mutation == "sample_rate" else "clipped_samples"] = 24000 if mutation == "sample_rate" else 2
            return info, pcm
        monkeypatch.setattr(subject.common, "pcm_info", invalid_pcm)
    else:
        item = alignment["inputs"][0]
        receipt = subject.common.read_json(item["receipt"])
        if mutation == "id": receipt["id"] = "other"
        if mutation == "text": receipt["request"]["text"] = "different text"
        if mutation == "reference": receipt["reference_sha256"] = "wrong voice"
        if mutation == "plan": receipt["plan_sha256"] = "other plan"
        if mutation == "worker": receipt["worker_sha256"] = "other worker"
        # A self-consistent new receipt hash must not bypass its content checks.
        Path(item["receipt"]).unlink()
        subject.common.write_json(item["receipt"], receipt)
        item["receipt_sha256"] = subject.common.sha(item["receipt"])
    subject.common.write_json(path, alignment)
    with pytest.raises(ValueError, match="Speech receipt"):
        subject.audio_bindings(path)


def test_final_audio_gate_accepts_complete_unchanged_takes(speech_fixture, tmp_path):
    _, _, alignment = speech_fixture
    path = tmp_path / "alignment.json"
    subject.common.write_json(path, alignment)
    assert subject.audio_bindings(path)["alignment_sha256"] == subject.common.sha(path)
