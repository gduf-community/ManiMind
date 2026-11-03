import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from manimind.experiments import sol_visual_recovery as recovery
from manimind.postproduce import pilot
from manimind.review.learning_quality import DIMENSIONS, QUALITY_FORMAT


def received(directory, role, value, payload=None):
    directory.mkdir(parents=True, exist_ok=True)
    pilot.write_json(directory / "input.json", payload or {})
    pilot.write_json(directory / "answer.txt", value)
    pilot.write_json(directory / "record.json", {"role": role, "status": "received",
        "input_sha256": pilot.sha256(directory / "input.json"),
        "answer_sha256": pilot.sha256(directory / "answer.txt")})


@pytest.fixture
def item(tmp_path):
    session, review, out = [tmp_path / x for x in ("session", "review", "out")]
    for path in (session, review, out):
        path.mkdir()
    director = tmp_path / "director" / "request-0001"
    command = {"action": "request_review", "args": {}, "notes": "Original", "observations": []}
    received(director, "director", command)
    step = session / "team-step-0012"
    step.mkdir()
    pilot.write_json(step / "command.json", {"role": "director", "request": str(director), "command": command,
        "answer_sha256": pilot.sha256(director / "answer.txt")})
    team_path = session / "team-state.json"
    pilot.write_json(team_path, {"status": "execution_stopped", "turn": 11, "cycle": 1,
        "started_at": "2026-10-24T11:00:00+00:00", "stopped_at": "2026-10-24T12:00:00+00:00",
        "inflight": {"phase": "tool", "turn": 12, "role": "director", "step": str(step)},
        "actors": {"director": {"history": []}}, "tool_durations": []})
    video = out / "video.mp4"
    video.write_bytes(b"fixture only")
    image = out / "frame.jpg"
    image.write_bytes(b"fixture pixels")
    frame = {"path": str(image), "sha256": pilot.sha256(image), "cue": "cue", "time": .5}
    evidence = {"hashes": {"source": "frozen"}, "video_sha256": pilot.sha256(video), "duration": 2,
                "cue_ids": ["cue"], "frames": [frame], "temporal_evidence": []}
    cycle = review / "cycle-01-visual"
    cycle.mkdir()
    pilot.write_json(cycle / "evidence.json", evidence)
    pilot.write_json(out / "review-input.json", evidence)
    pilot.write_json(out / "timeline.json", {"cues": [{"id": "cue", "start": 0, "duration": 2}]})
    payload = {"role": "reviewer", "system": recovery.native_system("reviewer"),
               "model": "gpt-6.1-sol", "reasoning_effort": "max", "text": "ORIGINAL\n" + QUALITY_FORMAT,
               "images": [{"path": str(image), "sha256": frame["sha256"]}], "transport": "fixture"}
    first = review / "request-0001"
    requested = {"action": "inspect_frames", "times": [1.0]}
    received(first, "reviewer", requested, payload)
    record = pilot.read_json(first / "record.json")
    pilot.write_json(first / "record.json", {**record, "stage": "cycle-01-visual-whole"})
    pilot.write_json(first / "extra-frames.json", [{**frame, "time": 1.0}])
    failed = review / "request-0002"
    failed.mkdir()
    payload = copy.deepcopy(payload)
    payload["text"] = 'ORIGINAL\nYour unedited frame request:\n{"action": "inspect_frames", "times": [1.0]}'
    payload["text"] += '\nAdditional frame timestamps, image order:\n[1.0]'
    payload["text"] += "\nNow return the final review JSON; no more frame requests for this batch.\n" + QUALITY_FORMAT
    payload["images"] *= 2
    pilot.write_json(failed / "input.json", payload)
    pilot.write_json(failed / "record.json", {"role": "reviewer", "stage": "cycle-01-visual-whole-detail",
        "status": "failed", "returncode": 1, "error_type": "ProviderStopped", "usage": [],
        "input_sha256": pilot.sha256(failed / "input.json")})
    (failed / "events.jsonl").write_text('{"type":"turn.failed","error":{"message":"Selected model is at capacity. Please try a different model."}}\n')
    def requests(role):
        return sorted((review if role == "reviewer" else director.parent if role == "director" else session).glob("request-*/record.json"))
    value = SimpleNamespace(session=session, review_session=review, director_session=director.parent, out=out,
        team_path=team_path, state_path=session / "agent-state.json", role_requests=requests,
        config={"model": "gpt-6.1-sol"}, verify=lambda: None, hashes=lambda: {"source": "frozen"},
        latest_video=lambda _: (video, 2), report=lambda: None)
    pilot.write_json(value.state_path, {})
    value.save_team = lambda: pilot.write_json(value.team_path, value.team)
    return value


def verdict():
    return {"action": "review", "status": "pass", "checks": {k: "pass" for k in ("mathematics", "visual_layout", "narrative", "cue_timing")},
        "inspected_cues": [{"id": "cue", "observations": [{"time": 1.0, "detail": "Fixture observation"}]}],
        "issues": [], "limitations": ["Fixture only"],
        "quality": {k: {"rating": 4, "evidence": "1.0 fixture"} for k in DIMENSIONS},
        "viewer_test": {"can_explain": "fixture", "missing_links": [], "transfer_question": "fixture?", "supported_answer": "fixture"}}


def test_read_only_checkpoint_preserves_all_original_inputs(item):
    before = {str(p): pilot.sha256(p) for p in item.session.parent.rglob("*") if p.is_file()}
    pending = recovery.checkpoint(item)
    after = {str(p): pilot.sha256(p) for p in item.session.parent.rglob("*") if p.is_file()}
    assert before == after
    assert pending["available"] == {"cue": [.5, 1.0]}
    assert pending["saved"]["model"] == "gpt-6.1-sol" and pending["saved"]["reasoning_effort"] == "max"


@pytest.mark.parametrize("change", ["lock", "input", "pixels", "received", "unknown", "wrong_phase", "already_finished"])
def test_unsafe_or_ambiguous_replay_is_rejected(item, change):
    failed = item.review_session / "request-0002"
    if change == "lock":
        (item.session / "team.lock").touch()
    elif change == "input":
        pilot.write_json(failed / "input.json", {})
    elif change == "pixels":
        (item.out / "frame.jpg").write_bytes(b"changed")
    elif change in {"received", "unknown"}:
        record = pilot.read_json(failed / "record.json")
        record["status"] = "received" if change == "received" else "started"
        pilot.write_json(failed / "record.json", record)
    else:
        state = pilot.read_json(item.team_path)
        if change == "wrong_phase":
            state["inflight"]["phase"] = "request"
            pilot.write_json(item.team_path, state)
        else:
            pilot.write_json(Path(state["inflight"]["step"]) / "result.json", {})
    with pytest.raises(ValueError):
        recovery.checkpoint(item)


def test_received_review_finishes_only_the_pending_turn_once(item):
    pending = recovery.checkpoint(item)
    request = item.review_session / "request-0003"
    received(request, "reviewer", verdict(), pending["saved"])
    raw = (request / "answer.txt").read_text()
    recovery.finish_review(item, pending, raw, request, 3.5)
    state = pilot.read_json(item.team_path)
    assert state["turn"] == 12 and state["inflight"] is None and state["cycle"] == 1
    assert state["visual_phase"] == "visual_approved"
    assert state["actors"]["director"]["history"][0]["turn"] == 12
    assert (item.review_session / "request-0002/record.json").exists()
    with pytest.raises(ValueError):
        recovery.checkpoint(item)


@pytest.mark.parametrize("change", ["unseen", "blocker", "score", "forged"])
def test_invalid_or_forged_judgment_cannot_approve(item, change):
    pending = recovery.checkpoint(item)
    value = verdict()
    if change == "unseen":
        value["inspected_cues"][0]["observations"][0]["time"] = 1.5
    elif change == "blocker":
        value["checks"]["mathematics"] = "fail"
    elif change == "score":
        value["quality"]["science"]["rating"] = 2
    request = item.review_session / "request-0003"
    received(request, "reviewer", value, pending["saved"])
    if change == "forged":
        value["limitations"] = ["Rewritten"]
    with pytest.raises(ValueError):
        recovery.finish_review(item, pending, json.dumps(value), request, 1)
    assert not (pending["cycle"] / "report.json").exists()


def test_time_and_quota_exclude_the_stopped_gap(item):
    result = recovery.accounting(pilot.read_json(item.team_path), "2026-10-24T14:00:00+00:00", "2026-10-24T14:10:00+00:00",
        [{"used_percent": 40, "resets_at": 1}, {"used_percent": 41, "resets_at": 1}])
    assert result["total_active_seconds"] == 4200
    assert result["excluded_pause_seconds"] == 7200
    assert result["resume_quota_interval"]["account_interval_percentage_points"] == 1
    assert not result["resume_quota_interval"]["single_job_attribution"]


def test_recovery_replays_only_exact_detail_input_and_continues_next_turn(item, monkeypatch):
    pending = recovery.checkpoint(item)
    calls = []
    item.initialize = lambda: None
    monkeypatch.setattr(recovery, "bind_adapter", lambda _: None)
    class Reader:
        def __init__(self, _):
            pass
        def read(self):
            return {"used_percent": 40, "resets_at": 1}
        def close(self):
            pass
    monkeypatch.setattr(recovery, "RateReader", Reader)
    def request(role, stage, text, images):
        assert role == "reviewer" and text == pending["saved"]["text"]
        assert images == [Path(f["path"]) for f in pending["saved"]["images"]]
        calls.append(stage)
        directory = item.review_session / "request-0003"
        received(directory, role, verdict(), pending["saved"])
        return (directory / "answer.txt").read_text(), directory
    item.role_request = request
    def run_team():
        state = pilot.read_json(item.team_path)
        assert state["turn"] + 1 == 13 and state["cycle"] == 1
        state["status"] = "complete"
        pilot.write_json(item.team_path, state)
    item.run_team = run_team
    recovery.recover(item)
    assert calls == ["capacity-recovery-detail"]
    assert pilot.read_json(item.session / "review-recovery/receipt.json")["status"] == "complete"
    assert not (item.session / "team.lock").exists()
    assert not (item.session / "review-recovery/recovery.lock").exists()
    assert pilot.read_json(item.review_session / "request-0002/record.json")["status"] == "failed"
