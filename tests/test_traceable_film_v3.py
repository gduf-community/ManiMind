"""Supervised evidence integration; no actual educational review is fabricated."""

from pathlib import Path

from PIL import Image
import pytest

from test_traceable_film_v2 import native_attempt, write
from manimind.postproduce import traceable_film_v3 as gate


@pytest.fixture
def supervised(native_attempt):
    x = native_attempt
    output = x["root"] / "supervised"
    gate.prepare_evidence(x["folder"], output)
    index = output / "supervised-evidence.json"
    value = gate.common.read_json(index)
    report = gate.common.read_json(x["review"])
    section = report["formula_continuity"]
    section.update(evidence_index=str(index), evidence_index_sha256=gate.common.sha(index))
    for old, frame in zip(section["checks"][0]["evidence"], value["frames"], strict=True):
        old.update(frame=frame["path"], sha256=frame["sha256"], time=frame["time"])
    write(x["review"], report)
    return {**x, "index": index}


def test_frozen_render_accepts_the_new_review_only_supervisor(supervised):
    x = supervised
    assert gate.require_review(x["folder"], x["review"])["status"] == "pass"


@pytest.mark.parametrize("kind", ["frames", "sheets"])
def test_all_review_assets_are_checked_not_only_selected_pngs(supervised, kind):
    x = supervised
    value = gate.common.read_json(x["index"])
    asset = Path(value[kind][0]["path"])
    Image.new("RGB", (64, 64), "blue").save(asset)
    with pytest.raises(ValueError, match="changed"):
        gate.require_review(x["folder"], x["review"])


def test_dangling_output_symlink_is_rejected_before_any_target_write(native_attempt):
    x = native_attempt
    target, link = x["root"] / "absent-target", x["root"] / "existing-link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(FileExistsError):
        gate.prepare_evidence(x["folder"], link)
    assert not target.exists() and link.is_symlink()


def test_supervisor_and_original_index_are_immutable(supervised):
    x = supervised
    value = gate.common.read_json(x["index"])
    value["supervisor_sha256"] = "0" * 64
    write(x["index"], value)
    report = gate.common.read_json(x["review"])
    report["formula_continuity"]["evidence_index_sha256"] = gate.common.sha(x["index"])
    write(x["review"], report)
    with pytest.raises(ValueError, match="supervisor"):
        gate.require_review(x["folder"], x["review"])
