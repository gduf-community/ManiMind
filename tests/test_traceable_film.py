"""Evidence completeness and gate delegation, not teaching-quality scoring."""

import copy
import hashlib

import pytest

from manimind.postproduce import traceable_film as gate


@pytest.fixture
def example(tmp_path):
    rows = [{"id": "substitute", "operation": "substitute output change",
             "source": "Delta y", "target": "numerator", "purpose": "track the same output change"}]
    frames = []
    evidence = []
    for time, phase in enumerate(("before", "during", "after"), start=1):
        frame = tmp_path / f"{phase}.png"
        frame.write_bytes(phase.encode())
        digest = hashlib.sha256(frame.read_bytes()).hexdigest()
        frames.append({"time": time, "path": str(frame), "sha256": digest})
        evidence.append({"phase": phase, "time": time, "frame": str(frame),
                         "sha256": digest, "finding": "actual observation"})
    report = {"formula_continuity": {"checks": [{"id": "substitute", "traceable": True,
              "identity_finding": "same Delta y", "operation_finding": "output/input",
              "evidence": evidence}]}}
    return rows, report, frames


def test_valid_current_process_evidence_passes(example):
    rows, report, frames = example
    assert gate.validate_observations(rows, report, 5, frame_index=frames) is report


@pytest.mark.parametrize("rows", [None, [], [{"id": "only"}], [
    {"id": "same", "operation": "a", "source": "a", "target": "b", "purpose": "c"}]*2])
def test_missing_or_duplicate_selection_fails(rows):
    with pytest.raises(ValueError):
        gate.validate_selection(rows)


@pytest.mark.parametrize("change", [
    lambda x: x.pop("formula_continuity"),
    lambda x: x["formula_continuity"].update(checks=[]),
    lambda x: x["formula_continuity"]["checks"][0].update(id="unselected"),
    lambda x: x["formula_continuity"]["checks"][0].update(traceable=False),
    lambda x: x["formula_continuity"]["checks"][0].update(identity_finding=""),
    lambda x: x["formula_continuity"]["checks"][0].update(operation_finding=""),
    lambda x: x["formula_continuity"]["checks"][0]["evidence"].pop(1),
    lambda x: x["formula_continuity"]["checks"][0]["evidence"][1].update(time=4),
    lambda x: x["formula_continuity"]["checks"][0]["evidence"][1].update(time=True),
    lambda x: x["formula_continuity"]["checks"][0]["evidence"][1].update(time=float("nan")),
    lambda x: x["formula_continuity"]["checks"][0]["evidence"][1].update(sha256="stale"),
])
def test_motion_counts_or_final_stills_cannot_replace_process_observations(example, change):
    rows, report, frames = example
    change(report)
    with pytest.raises(ValueError):
        gate.validate_observations(rows, report, 5, frame_index=frames)


def test_valid_file_from_other_video_or_time_is_rejected(example):
    rows, report, frames = example
    stale_index = copy.deepcopy(frames)
    stale_index[1]["time"] += .1
    with pytest.raises(ValueError, match="current bound media"):
        gate.validate_observations(rows, report, 5, frame_index=stale_index)


def test_changed_frame_is_rejected(example):
    rows, report, frames = example
    from pathlib import Path
    Path(frames[1]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        gate.validate_observations(rows, report, 5, frame_index=frames)


@pytest.mark.parametrize("operation", ["install", "silent"])
def test_failed_continuity_never_reaches_native_publication(monkeypatch, operation):
    calls = []
    def reject(*args):
        raise ValueError("untraceable")
    monkeypatch.setattr(gate, "require_review", reject)
    monkeypatch.setattr(gate.unit_film, "install_narration", lambda *a: calls.append(a))
    monkeypatch.setattr(gate.unit_film, "release_silent", lambda *a: calls.append(a))
    with pytest.raises(ValueError, match="untraceable"):
        if operation == "install":
            gate.install_narration("a", "b", "c", "d")
        else:
            gate.release_silent("a", "b", "c", "d", "e")
    assert not calls


def test_success_delegates_to_unchanged_native_installer(monkeypatch):
    calls = []
    monkeypatch.setattr(gate, "require_review", lambda *args: calls.append("continuity"))
    monkeypatch.setattr(gate.unit_film, "install_narration", lambda *args: calls.append(args) or "native")
    assert gate.install_narration("a", "b", "c", "d") == "native"
    assert calls == ["continuity", ("a", "b", "c", "d")]
