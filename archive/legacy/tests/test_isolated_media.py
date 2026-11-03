from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from manimind.components import pipeline
from manimind.experiments import isolated_comparison as comparison
from manimind.experiments import isolated_media as media
from manimind.postproduce import pilot


def answer():
    shot = {
        "id": "shot", "title": "Test", "goal": "Media infrastructure fixture", "duration": 18,
        "caption": ["Unchanged caption"],
        "axes": {"x_range": [0, 2, 1], "y_range": [0, 2, 1], "x_label": "x", "y_label": "y", "equal_units": True},
        "parameters": {},
        "components": [{"id": "point", "kind": "point", "label": "P", "color": "cyan", "position": [1, 1]}],
        "keyframes": [{"at": 0, "values": {}}, {"at": .8, "values": {}}, {"at": 1, "values": {}}],
    }
    shots = [{**deepcopy(shot), "id": f"shot-{index}"} for index in range(1, 7)]
    return {"plan": {"schema_version": "components-0.1", "id": "lesson", "title": "Media test",
                     "provenance": {"kind": "model_output", "author": "candidate", "interventions": []}, "shots": shots},
            "narration": [{"shot_id": s["id"], "text": "第一句。第二句！"} for s in shots]}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "ROOT", tmp_path / "repository")
    monkeypatch.setattr(comparison, "verify_selected_run", lambda *args: {"verified": True}, raising=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    pilot.write_json(run_dir / "answer.json", answer())
    calls = []

    def run(command, timeout=180):
        args = [str(arg) for arg in command]
        calls.append(args)
        if args[0] == "say":
            assert args[1:5] == ["-v", "Tingting", "-r", "240"]
            text = Path(args[args.index("-f") + 1]).read_text(encoding="utf-8")
            Path(args[args.index("-o") + 1]).write_bytes(text.encode("utf-8"))
        elif args[-1].endswith(".wav"):
            media._write_pcm(Path(args[-1]), b"\x01\x00" * 480)
        else:
            pytest.fail(f"Unexpected media subprocess: {args}")
        return ""

    monkeypatch.setattr(pilot, "run", run)
    monkeypatch.setattr(pipeline, "render", lambda *a, **kw: pytest.fail("Rendering is forbidden"))
    monkeypatch.setattr(pipeline, "publish", lambda *a: pytest.fail("Preparation cannot publish"))
    return run_dir, calls


def test_prepare_freezes_only_id_and_records_exact_audio(setup, monkeypatch):
    run_dir, calls = setup
    original = answer()
    original["narration"].reverse()
    pilot.write_json(run_dir / "answer.json", original)
    before = (run_dir / "answer.json").read_bytes()
    clock = iter(range(100))
    monkeypatch.setattr(media.time, "perf_counter", lambda: next(clock))
    report = media.prepare(run_dir, "media-test")
    plan = pilot.read_json(run_dir / "plan.json")
    assert plan == {**original["plan"], "id": "media-test"}
    assert (run_dir / "answer.json").read_bytes() == before
    assert pipeline.frozen_plan("media-test") == plan
    assert report["answer_sha256"] == pilot.sha256(run_dir / "answer.json")
    assert report["plan_sha256"] == pilot.sha256(run_dir / "plan.json")
    assert report["audio_sha256"] == pilot.sha256(run_dir / "audio/narration.wav")
    assert report["status"] == "prepared"
    assert report["duration"] == 108
    assert report["tts_seconds"] == 12
    assert len([c for c in calls if c[0] == "say"]) == 12
    assert all("-t" not in c and "-af" not in c and "-shortest" not in c for c in calls)
    assert not list(run_dir.rglob("*.mp4"))
    assert not (run_dir / "media-review.json").exists()
    audio = media._pcm(run_dir / "audio/narration.wav")[1]
    assert len(audio) == 108 * 48000 * 2
    for index, shot in enumerate(report["shots"]):
        assert shot["shot_id"] == f"shot-{index + 1}"
        assert shot["start"] == index * 18
        assert shot["audio_duration"] == .02
        assert shot["tail_silence"] == 17.68
        assert [s["duration"] for s in shot["sentences"]] == [.01, .01]
        frames, data = media._pcm(run_dir / shot["audio_path"])
        assert frames == 18 * 48000
        assert data[:14400 * 2] == b"\0" * 14400 * 2
        assert data[14400 * 2:(14400 + 960) * 2] == b"\x01\x00" * 960
        assert data[(14400 + 960) * 2:] == b"\0" * (848640 * 2)
        assert audio[index * len(data):(index + 1) * len(data)] == data
    srt = (run_dir / "audio/narration.srt").read_text(encoding="utf-8")
    assert "00:00:00,300 --> 00:00:00,320\n第一句。\n第二句！" in srt
    assert "00:01:30,300 --> 00:01:30,320" in srt
    assert srt.count(" --> ") == 6


def test_repeat_prepare_validates_without_tts_or_init(setup, monkeypatch):
    run_dir, calls = setup
    first = media.prepare(run_dir, "media-test")
    digest = pilot.sha256(run_dir / "media-preparation.json")
    monkeypatch.setattr(pipeline, "init", lambda *args: pytest.fail("No reinitialization"))
    monkeypatch.setattr(pilot, "run", lambda *args, **kw: pytest.fail("No repeated TTS"))
    assert media.prepare(run_dir, "media-test") == first
    assert pilot.sha256(run_dir / "media-preparation.json") == digest


def test_prepare_requires_source_verification_before_any_side_effect(setup, monkeypatch):
    run_dir, calls = setup
    verified = []

    def reject(path, project_id):
        verified.append((path, project_id))
        raise ValueError("Invalid selected run")

    monkeypatch.setattr(comparison, "verify_selected_run", reject)
    with pytest.raises(ValueError, match="Invalid selected run"):
        media.prepare(run_dir, "media-test")
    assert verified == [(run_dir.resolve(), "media-test")]
    assert calls == []
    assert not (run_dir / "plan.json").exists()
    assert not pipeline.paths("media-test")[2].exists()


def test_prepare_rechecks_source_chain_before_completion(setup, monkeypatch):
    run_dir, _ = setup
    checks = []

    def verify(*args):
        checks.append(args)
        if len(checks) == 2:
            raise ValueError("Selected run changed")
        return {"verified": True}

    monkeypatch.setattr(comparison, "verify_selected_run", verify)
    with pytest.raises(ValueError, match="Selected run changed"):
        media.prepare(run_dir, "media-test")
    assert len(checks) == 2
    assert pilot.read_json(run_dir / "media-preparation.json")["status"] == "failed"


def test_prepare_reuses_identical_pipeline_init(setup):
    run_dir, _ = setup
    source = run_dir.parent / "frozen.json"
    pilot.write_json(source, {**answer()["plan"], "id": "media-test"})
    pipeline.init(source)
    before = pilot.sha256(pipeline.paths("media-test")[1] / "component-plan.json")
    media.prepare(run_dir, "media-test")
    assert pilot.sha256(pipeline.paths("media-test")[1] / "component-plan.json") == before


def test_changed_frozen_plan_and_different_project_are_rejected(setup):
    run_dir, _ = setup
    media.prepare(run_dir, "media-test")
    with pytest.raises(ValueError, match="Stale media preparation"):
        media.prepare(run_dir, "different")
    frozen = pipeline.paths("media-test")[0] / "plan.json"
    value = pilot.read_json(frozen)
    value["title"] = "Changed"
    pilot.write_json(frozen, value)
    with pytest.raises(ValueError, match="Frozen plan was modified"):
        media.prepare(run_dir, "media-test")


@pytest.mark.parametrize("change", [
    lambda r: r["artifacts"].pop("audio/01-shot-1-01.aiff"),
    lambda r: r["artifacts"].update({"../outside.wav": "hash"}),
    lambda r: r["shots"][0]["sentences"][0].update(duration=1),
    lambda r: r["shots"][0]["sentences"][0].update(tts_seconds=float("nan")),
    lambda r: r["shots"][0]["sentences"][0].update(start=2),
    lambda r: r["shots"][0].update(tail_silence=.1),
    lambda r: r.update(tts_seconds=-1),
    lambda r: r.update(implementation_sha256="old"),
])
def test_preparation_ledger_changes_are_rejected(setup, change):
    run_dir, _ = setup
    report = media.prepare(run_dir, "media-test")
    change(report)
    pilot.write_json(run_dir / "media-preparation.json", report)
    with pytest.raises(ValueError):
        media.prepare(run_dir, "media-test")


@pytest.mark.parametrize("path", ["answer.json", "plan.json", "audio/narration.wav",
                                "audio/narration.srt", "audio/01-shot-1-01.aiff",
                                "audio/01-shot-1-01.wav", "audio/01-shot-1-01.txt", "audio/01-shot-1.wav"])
def test_prepared_artifact_changes_fail_closed(setup, path):
    run_dir, _ = setup
    media.prepare(run_dir, "media-test")
    target = run_dir / path
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        media.prepare(run_dir, "media-test")


@pytest.mark.parametrize("change", [
    lambda a: a.update(candidate="identity"),
    lambda a: a["plan"].update(id="model-name"),
    lambda a: a["plan"]["provenance"].update(author="model-name"),
    lambda a: a["plan"]["shots"].pop(),
    lambda a: a["plan"]["shots"][0].update(duration=17),
    lambda a: a["plan"]["shots"][0].update(duration=float("nan")),
    lambda a: a["narration"].pop(),
    lambda a: a["narration"][0].update(shot_id="missing"),
    lambda a: a["narration"][0].update(shot_id="shot-2"),
    lambda a: a["narration"][0].update(text=" "),
    lambda a: a["narration"][0].update(text="[[rate 500]]测试。"),
    lambda a: a["narration"][0].update(text="不改写\n换行。"),
])
def test_invalid_candidate_input_is_never_repaired(setup, change):
    run_dir, calls = setup
    value = answer()
    change(value)
    pilot.write_json(run_dir / "answer.json", value)
    before = (run_dir / "answer.json").read_bytes()
    with pytest.raises(ValueError):
        media.prepare(run_dir, "media-test")
    assert not calls
    assert (run_dir / "answer.json").read_bytes() == before
    assert not (run_dir / "plan.json").exists()


def test_duplicate_json_keys_are_rejected(setup):
    run_dir, calls = setup
    raw = json.dumps(answer(), ensure_ascii=False).replace('"id": "lesson"', '"id": "lesson", "id": "lesson"')
    (run_dir / "answer.json").write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON"):
        media.prepare(run_dir, "media-test")
    assert not calls


def test_different_existing_frozen_project_is_not_overwritten(setup):
    run_dir, _ = setup
    other = run_dir.parent / "other-plan.json"
    value = answer()["plan"]
    value.update(id="media-test", title="Other frozen plan")
    pilot.write_json(other, value)
    pipeline.init(other)
    with pytest.raises(ValueError, match="Frozen project differs"):
        media.prepare(run_dir, "media-test")
    assert pipeline.frozen_plan("media-test")["title"] == "Other frozen plan"
    assert not (run_dir / "audio").exists()


@pytest.mark.parametrize("seconds,allowed", [(17.2, True), (17.2 + 1 / 48000, False)])
def test_exact_speech_boundary_has_no_truncation(setup, monkeypatch, seconds, allowed):
    run_dir, calls = setup
    value = answer()
    for narration in value["narration"]:
        narration["text"] = "测试。"
    pilot.write_json(run_dir / "answer.json", value)
    base_run = pilot.run

    def run(command, **kwargs):
        if str(command[-1]).endswith(".wav"):
            media._write_pcm(Path(command[-1]), b"\x01\x00" * round(seconds * 48000))
        else:
            base_run(command, **kwargs)

    monkeypatch.setattr(pilot, "run", run)
    if allowed:
        report = media.prepare(run_dir, "media-test")
        assert all(s["tail_silence"] == .5 for s in report["shots"])
    else:
        with pytest.raises(ValueError, match="exceeds 17.2"):
            media.prepare(run_dir, "media-test")
        report = pilot.read_json(run_dir / "media-preparation.json")
        assert report["status"] == "failed"
        assert report["shots"][0]["sentences"][0]["duration"] == seconds
        assert len([c for c in calls if c[0] == "say"]) == 1
        with pytest.raises(ValueError, match="Incomplete preparation"):
            media.prepare(run_dir, "media-test")


def test_sentence_durations_are_accumulated_within_each_shot(setup, monkeypatch):
    run_dir, calls = setup
    base_run = pilot.run

    def run(command, **kwargs):
        if str(command[-1]).endswith(".wav"):
            media._write_pcm(Path(command[-1]), b"\x01\x00" * (9 * 48000))
        else:
            base_run(command, **kwargs)

    monkeypatch.setattr(pilot, "run", run)
    with pytest.raises(ValueError, match="exceeds 17.2"):
        media.prepare(run_dir, "media-test")
    assert len([c for c in calls if c[0] == "say"]) == 2
    assert not (run_dir / "audio/01-shot-1.wav").exists()


def test_timeout_keeps_tts_cost_and_never_retries(setup, monkeypatch):
    run_dir, _ = setup
    times = iter([10., 190.])
    monkeypatch.setattr(media.time, "perf_counter", lambda: next(times))

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("say", 180)

    monkeypatch.setattr(pilot, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        media.prepare(run_dir, "media-test")
    report = pilot.read_json(run_dir / "media-preparation.json")
    assert report["status"] == "failed"
    assert report["tts_seconds"] == 180
    assert report["shots"][0]["sentences"][0]["tts_seconds"] == 180
    assert not (run_dir / "audio/narration.wav").exists()


def test_mid_preparation_answer_change_is_rejected(setup, monkeypatch):
    run_dir, _ = setup
    base_run = pilot.run

    def run(*args, **kwargs):
        base_run(*args, **kwargs)
        path = run_dir / "answer.json"
        path.write_bytes(path.read_bytes() + b" ")

    monkeypatch.setattr(pilot, "run", run)
    with pytest.raises(ValueError, match="Answer changed"):
        media.prepare(run_dir, "media-test")
    assert pilot.read_json(run_dir / "media-preparation.json")["status"] == "failed"


def test_sentence_split_preserves_all_characters_and_decimal():
    text = '数值1.5。“确认吗？” 是的！末句没有标点 '
    parts = media._sentences(text)
    assert "".join(parts) == text
    assert parts == ["数值1.5。", "“确认吗？”", " 是的！", "末句没有标点 "]


def metadata(final=False):
    video = {"codec_type": "video", "codec_name": "h264", "duration": "108.000", "start_time": "0.000",
             "width": 1920, "height": 1080, "avg_frame_rate": "30/1"}
    streams = [video]
    if final:
        streams.extend([
            {"codec_type": "audio", "codec_name": "aac", "duration": "108.000", "start_time": "0.000",
             "sample_rate": "48000", "channels": 1},
            {"codec_type": "subtitle", "codec_name": "mov_text"},
        ])
    return {"streams": streams, "format": {"duration": "108.000", "start_time": "0.000"}}


@pytest.fixture
def assembly(setup, monkeypatch):
    run_dir, calls = setup
    media.prepare(run_dir, "media-test")
    out, context, _ = pipeline.paths("media-test")
    folder = pipeline.attempt_dir("media-test", 1)
    folder.mkdir(parents=True)
    video = folder / "render.mp4"
    video.write_bytes(b"synthetic test video; no renderer")
    pilot.write_json(folder / "render.json", {"video_path": str(video)})
    (folder / "review-input.json").write_bytes(b"component evidence test marker")
    (context / "review-001.json").write_bytes(b"component review test marker")
    (run_dir / "media-review.json").write_bytes(b"media review test marker")
    # 审批仅在内存里模拟；不写任何可用于真实发布的批准文件。
    review = {"project_id": "media-test", "attempt": 1, "reviewer_role": "reviewer",
              "reviewer_id": "independent-test-reviewer", "status": "approved", "blockers": [],
              "hashes": media._review_hashes(run_dir, video)}
    read_json = pilot.read_json

    def read(path):
        if Path(path) == run_dir / "media-review.json":
            return deepcopy(review)
        return read_json(path)

    monkeypatch.setattr(pilot, "read_json", read)
    actions = []

    def publish(project_id, attempt):
        assert (project_id, attempt) == ("media-test", 1)
        actions.append("publish")
        published = out / "component-demo-v001.mp4"
        published.write_bytes(video.read_bytes())
        (out / "delivery-001.json").write_bytes(b"mock component delivery")
        return str(published)

    def run(command, **kwargs):
        args = [str(arg) for arg in command]
        calls.append(args)
        assert actions[0] == "publish"
        if args[-1].endswith("lesson-pending.mp4"):
            actions.append("mux")
            Path(args[-1]).write_bytes(b"synthetic mux output")
        elif args[-3:] == ["-f", "null", "-"]:
            actions.append("decode")
        else:
            pytest.fail(f"Unexpected assembly subprocess: {args}")

    monkeypatch.setattr(pipeline, "publish", publish)
    monkeypatch.setattr(pipeline, "evidence_hashes", lambda *args: {"video": pilot.sha256(video), "components": "fixed"})
    monkeypatch.setattr(pilot, "run", run)
    monkeypatch.setattr(pilot, "probe", lambda path: metadata(Path(path).name == "lesson-pending.mp4"))
    calls.clear()
    return run_dir, review, video, actions, calls


def test_assemble_publishes_before_mux_and_binds_both_approvals(assembly):
    run_dir, review, video, actions, calls = assembly
    result = media.assemble(run_dir, "media-test", 1)
    assert result == run_dir / "lesson.mp4"
    assert actions == ["publish", "mux", "decode"]
    delivery = pilot.read_json(run_dir / "delivery.json")
    assert delivery["hashes"] == review["hashes"]
    assert delivery["sha256"] == pilot.sha256(result)
    assert delivery["media_review_sha256"] == pilot.sha256(run_dir / "media-review.json")
    assert delivery["component_review_sha256"] == pilot.sha256(pipeline.paths("media-test")[1] / "review-001.json")
    assert len(delivery["approval_sources"]) == 5
    assert (run_dir / "media-review.json").read_bytes() == b"media review test marker"
    mux = calls[0]
    assert mux[mux.index("-c:v") + 1] == "copy"
    assert mux[mux.index("-c:a") + 1] == "aac"
    assert mux[mux.index("-c:s") + 1] == "mov_text"
    assert [mux[i + 1] for i, arg in enumerate(mux) if arg == "-map"] == ["0:v:0", "1:a:0", "2:s:0"]
    assert not set(mux) & {"-t", "-shortest", "-vf", "-af", "-y", "-r"}
    with pytest.raises(ValueError, match="immutable"):
        media.assemble(run_dir, "media-test", 1)


@pytest.mark.parametrize("change", [
    lambda r: r.update(status="blocked"),
    lambda r: r.update(blockers=["audio issue"]),
    lambda r: r.pop("blockers"),
    lambda r: r.update(reviewer_role="coordinator"),
    lambda r: r.update(reviewer_id="candidate"),
    lambda r: r.update(reviewer_id=" Candidate "),
    lambda r: r.update(reviewer_id=media.WRITER),
    lambda r: r.update(reviewer_id=" "),
    lambda r: r.update(project_id="other"),
    lambda r: r.update(attempt=2),
    lambda r: r.update(attempt=True),
    lambda r: r.update(hashes={}),
])
def test_invalid_media_approval_never_publishes_or_muxes(assembly, change):
    run_dir, review, _, actions, calls = assembly
    change(review)
    with pytest.raises(ValueError):
        media.assemble(run_dir, "media-test", 1)
    assert actions == calls == []
    assert not (run_dir / "lesson.mp4").exists()


@pytest.mark.parametrize("key", ["answer", "plan", "preparation", "audio", "subtitles", "video"])
def test_each_media_review_hash_is_required(assembly, key):
    run_dir, review, _, actions, _ = assembly
    review["hashes"][key] = "stale"
    with pytest.raises(ValueError, match="Stale media review"):
        media.assemble(run_dir, "media-test", 1)
    assert actions == []


def test_component_gate_rejection_is_not_bypassed(assembly, monkeypatch):
    run_dir, _, _, actions, calls = assembly

    def reject(*args):
        actions.append("publish-rejected")
        raise ValueError("Independent component review missing")

    monkeypatch.setattr(pipeline, "publish", reject)
    with pytest.raises(ValueError, match="component review missing"):
        media.assemble(run_dir, "media-test", 1)
    assert actions == ["publish-rejected"]
    assert calls == []
    assert not (run_dir / "delivery.json").exists()


def test_assemble_requires_source_verification_before_publish(assembly, monkeypatch):
    run_dir, _, _, actions, calls = assembly
    verified = []

    def reject(path, project_id):
        verified.append((path, project_id))
        raise ValueError("Invalid selected run")

    monkeypatch.setattr(comparison, "verify_selected_run", reject)
    with pytest.raises(ValueError, match="Invalid selected run"):
        media.assemble(run_dir, "media-test", 1)
    assert verified == [(run_dir.resolve(), "media-test")]
    assert actions == calls == []


def test_assemble_rechecks_source_chain_before_delivery(assembly, monkeypatch):
    run_dir, _, _, actions, _ = assembly
    checks = []

    def verify(*args):
        checks.append(args)
        if len(checks) == 3:
            raise ValueError("Selected run changed")
        return {"verified": True}

    monkeypatch.setattr(comparison, "verify_selected_run", verify)
    with pytest.raises(ValueError, match="Selected run changed"):
        media.assemble(run_dir, "media-test", 1)
    assert actions == ["publish", "mux", "decode"]
    assert not (run_dir / "lesson.mp4").exists()
    assert not (run_dir / "delivery.json").exists()


def test_missing_media_approval_is_not_created(assembly):
    run_dir, _, _, actions, _ = assembly
    (run_dir / "media-review.json").unlink()
    with pytest.raises(FileNotFoundError):
        media.assemble(run_dir, "media-test", 1)
    assert actions == []
    assert not (run_dir / "media-review.json").exists()


def test_media_approval_replaced_during_read_is_rejected(assembly, monkeypatch):
    run_dir, _, _, actions, _ = assembly
    original_read = pilot.read_json

    def read(path):
        result = original_read(path)
        if Path(path) == run_dir / "media-review.json":
            Path(path).write_bytes(b"replaced approval marker")
        return result

    monkeypatch.setattr(pilot, "read_json", read)
    with pytest.raises(ValueError, match="approval changed"):
        media.assemble(run_dir, "media-test", 1)
    assert actions == []


def test_publisher_cannot_substitute_other_video(assembly, monkeypatch):
    run_dir, _, _, actions, calls = assembly
    original_publish = pipeline.publish

    def publish(*args):
        path = Path(original_publish(*args))
        path.write_bytes(b"wrong video")
        return str(path)

    monkeypatch.setattr(pipeline, "publish", publish)
    with pytest.raises(ValueError, match="inputs or approvals changed"):
        media.assemble(run_dir, "media-test", 1)
    assert actions == ["publish"]
    assert calls == []


@pytest.mark.parametrize("stage", ["mux", "decode"])
def test_subprocess_failure_cannot_leave_final_delivery(assembly, monkeypatch, stage):
    run_dir, _, _, _, _ = assembly
    base_run = pilot.run

    def run(command, **kwargs):
        base_run(command, **kwargs)
        if (str(command[-1]).endswith("lesson-pending.mp4")) == (stage == "mux"):
            raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(pilot, "run", run)
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        media.assemble(run_dir, "media-test", 1)
    assert not (run_dir / "lesson.mp4").exists()
    assert not (run_dir / "delivery.json").exists()
    assert not (run_dir / "lesson-pending.mp4").exists()


@pytest.mark.parametrize("change", [
    lambda m: m["streams"].pop(),
    lambda m: m["streams"][0].update(duration="107"),
    lambda m: m["streams"][1].update(duration="109"),
    lambda m: m["streams"][1].update(duration="NaN"),
    lambda m: m["streams"][1].update(start_time="1"),
    lambda m: m["streams"][1].update(codec_name="mp3"),
    lambda m: m["streams"][1].update(sample_rate="44100"),
    lambda m: m["streams"][1].update(channels=2),
    lambda m: m["streams"][2].update(codec_name="subrip"),
    lambda m: m["streams"][0].update(width=1280),
    lambda m: m["format"].update(duration="109"),
    lambda m: m["streams"].append({"codec_type": "audio"}),
])
def test_bad_final_streams_cannot_be_delivered(assembly, monkeypatch, change):
    run_dir, _, _, actions, _ = assembly

    def probe(path):
        final = Path(path).name == "lesson-pending.mp4"
        result = metadata(final)
        if final:
            change(result)
        return result

    monkeypatch.setattr(pilot, "probe", probe)
    with pytest.raises(ValueError):
        media.assemble(run_dir, "media-test", 1)
    assert actions == ["publish", "mux"]
    assert not (run_dir / "lesson.mp4").exists()
    assert not (run_dir / "lesson-pending.mp4").exists()
    assert not (run_dir / "delivery.json").exists()


@pytest.mark.parametrize("target", ["answer", "preparation", "audio", "subtitle", "video", "media-review",
                                  "component-review", "component-delivery", "review-input", "render"])
def test_mid_mux_mutation_invalidates_delivery(assembly, monkeypatch, target):
    run_dir, _, video, _, _ = assembly
    out, context, _ = pipeline.paths("media-test")
    paths = {"answer": run_dir / "answer.json", "preparation": run_dir / "media-preparation.json",
             "audio": run_dir / "audio/narration.wav", "subtitle": run_dir / "audio/narration.srt",
             "video": video, "media-review": run_dir / "media-review.json",
             "component-review": context / "review-001.json", "component-delivery": out / "delivery-001.json",
             "review-input": video.parent / "review-input.json", "render": video.parent / "render.json"}
    base_run = pilot.run

    def run(command, **kwargs):
        base_run(command, **kwargs)
        if str(command[-1]).endswith("lesson-pending.mp4"):
            path = paths[target]
            path.write_bytes(path.read_bytes() + b" ")

    monkeypatch.setattr(pilot, "run", run)
    with pytest.raises(ValueError):
        media.assemble(run_dir, "media-test", 1)
    assert not (run_dir / "lesson.mp4").exists()
    assert not (run_dir / "delivery.json").exists()


@pytest.mark.skipif(not Path(pilot.FFMPEG).is_file() or not Path(pilot.FFPROBE).is_file(),
                    reason="Local ffmpeg/ffprobe unavailable")
def test_real_ffmpeg_stream_copy_aac_and_mov_text(tmp_path):
    # 仅临时色块和静音，不初始化项目、不运行组件 renderer、不创建审核记录。
    video, audio = tmp_path / "test-video.mp4", tmp_path / "test-audio.wav"
    subtitles, result = tmp_path / "test.srt", tmp_path / "test-mux.mp4"
    media._write_pcm(audio, b"\0" * (108 * 48000 * 2))
    subtitles.write_text("1\n00:00:00,300 --> 00:00:17,500\n测试第一句。\n测试第二句。\n", encoding="utf-8")
    pilot.run([pilot.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=108",
               "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", video], timeout=60)
    original = media._streams(video)
    pilot.run([pilot.FFMPEG, "-v", "error", "-i", video, "-i", audio, "-i", subtitles,
               "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-disposition:s:0", "default",
               "-movflags", "+faststart", result], timeout=60)
    stream = media._streams(result, final=True, original=original)
    assert float(stream["duration"]) == 108
    pilot.run([pilot.FFMPEG, "-v", "error", "-i", result, "-map", "0:v:0", "-map", "0:a:0",
               "-f", "null", "-"], timeout=60)
    for path in (video, result):
        hashes = pilot.run([pilot.FFMPEG, "-v", "error", "-i", path, "-map", "0:v:0",
                            "-c:v", "copy", "-f", "hash", "-"])
        if path == video:
            source_hash = hashes
        else:
            assert hashes == source_hash
