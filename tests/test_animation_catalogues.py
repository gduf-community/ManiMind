"""Editorial catalogues stay separate from native curriculum and media state."""

import csv
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("animation_catalogues", ROOT / "scripts/check_animation_catalogues.py")
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


def copy_data(tmp_path):
    shutil.copytree(ROOT / "docs/curricula", tmp_path / "docs/curricula")
    return tmp_path / subject.LIBRARY


def mutate(folder, name, callback):
    path = folder / name
    rows = subject.read_csv(path, subject.FIELDS)
    callback(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=subject.FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_six_courses_are_separate_and_have_no_quantity_cap():
    index, catalogues = subject.load(ROOT)
    assert {c["id"] for c, _ in catalogues} == {
        "high-school-mathematics", "high-school-physics", "calculus", "linear-algebra",
        "probability", "mathematical-statistics",
    }
    assert "quantity_cap" not in index
    assert all(rows for _, rows in catalogues)
    assert index["purpose"] == "editorial_selection_not_runtime_or_mastery_state"


def test_generated_reading_tables_match_data():
    for relative, expected in subject.views(ROOT).items():
        assert (ROOT / relative).read_text(encoding="utf-8") == expected


@pytest.mark.parametrize("field,value,error", [
    ("source_ids", "UNKNOWN", "Unknown source"),
    ("curriculum_refs", "M99-99", "Invalid curriculum reference"),
    ("transfer_check", "", "Missing teaching field"),
    ("priority", "done", "Invalid priority"),
    ("id", "LA-001", "Invalid scene ID"),
])
def test_invalid_editorial_data_is_rejected(tmp_path, field, value, error):
    folder = copy_data(tmp_path)
    mutate(folder, "high-school-mathematics.csv", lambda rows: rows[0].update({field: value}))
    with pytest.raises(ValueError, match=error):
        subject.load(tmp_path)


def test_growth_is_not_capped(tmp_path):
    folder = copy_data(tmp_path)
    def grow(rows):
        for number in range(100, 145):
            rows.append(dict(rows[0], id=f"HM-{number:03}", title=f"Additional scene {number}"))
    mutate(folder, "high-school-mathematics.csv", grow)
    _, catalogues = subject.load(tmp_path)
    assert len(catalogues[0][1]) > 70


def test_sources_disclose_book_access_scope():
    sources = {r["id"]: r for r in subject.read_csv(ROOT / subject.LIBRARY / "sources.csv")}
    assert "旧版2014" in sources["B01"]["use_boundary"]
    assert "不是完整目录" in sources["B06"]["use_boundary"]
    assert "不能充作" in sources["B07"]["use_boundary"]


def test_unknown_pilot_does_not_become_an_assignment(tmp_path):
    folder = copy_data(tmp_path)
    path = folder / "index.json"
    value = json.loads(path.read_text())
    value["pilot_scenes"].append("UNKNOWN")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Unknown pilot scene"):
        subject.load(tmp_path)
