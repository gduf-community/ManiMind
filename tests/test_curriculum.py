import csv
import json

import pytest

from manimind import curriculum as subject


def inputs(tmp_path):
    table = tmp_path / "catalogue.csv"
    fields = sorted(subject.CATALOGUE_FIELDS)
    rows = [dict.fromkeys(fields, "description") for _ in range(3)]
    for row, identity, prerequisites in zip(rows, ["A", "B", "C"], ["", "A", "B"]):
        row.update(id=identity, requires=prerequisites)
    with table.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    value = {"schema_version": 1, "unit_id": "test-unit", "catalogue": "catalogue.csv",
             "title": "Course", "audience": "Audience", "scope": "A small unit",
             "lessons": [{"project_id": f"lesson-{name}", "catalogue_ids": [name],
                          "new_understanding": "A distinct increment", "exit_task": "Explain a new case",
                          "handoff": "Continue the same model"} for name in ("A", "B", "C")]}
    unit = tmp_path / "unit.json"
    unit.write_text(json.dumps(value))
    return table, unit, value


def test_context_selects_only_relevant_course_exits_and_neighbors(tmp_path):
    _, unit, _ = inputs(tmp_path)
    result = subject.build_context(unit, "lesson-B", tmp_path)
    assert result["current_lesson"]["project_id"] == "lesson-B"
    assert result["previous_lesson"]["project_id"] == "lesson-A"
    assert result["next_lesson"]["project_id"] == "lesson-C"
    assert [row["id"] for row in result["catalogue_excerpts"]] == ["B"]
    assert [row["id"] for row in result["prerequisite_exits"]] == ["A"]
    assert result["entry_evidence_status"] == "assumed_not_tested"
    assert "mastery" not in result


def test_first_and_last_lessons_do_not_invent_neighbors(tmp_path):
    _, unit, _ = inputs(tmp_path)
    assert subject.build_context(unit, "lesson-A", tmp_path)["previous_lesson"] is None
    assert subject.build_context(unit, "lesson-C", tmp_path)["next_lesson"] is None


def test_long_context_is_create_only_and_changes_invalidate_it(tmp_path):
    _, unit, value = inputs(tmp_path)
    output = tmp_path / "runtime/projects/test/context.json"
    subject.write_context(unit, "lesson-B", output, tmp_path)
    subject.verify_context(output, tmp_path)
    with pytest.raises(FileExistsError):
        subject.write_context(unit, "lesson-B", output, tmp_path)
    value["audience"] = "Changed audience"
    unit.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="changed"):
        subject.verify_context(output, tmp_path)


def test_context_cannot_be_written_into_short_term_session(tmp_path):
    _, unit, _ = inputs(tmp_path)
    with pytest.raises(ValueError, match="long-term"):
        subject.write_context(unit, "lesson-A", tmp_path / "runtime/sessions/wrong/context.json", tmp_path)


@pytest.mark.parametrize("target_exists", [False, True])
def test_existing_output_symlink_is_never_followed(tmp_path, target_exists):
    _, unit, _ = inputs(tmp_path)
    output = tmp_path / "runtime/projects/test/context.json"
    output.parent.mkdir(parents=True)
    target = output.with_name("target.json")
    if target_exists:
        target.write_text("original")
    output.symlink_to(target)
    with pytest.raises(FileExistsError):
        subject.write_context(unit, "lesson-A", output, tmp_path)
    assert output.is_symlink()
    assert target.exists() is target_exists
    if target_exists:
        assert target.read_text() == "original"


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "empty_exit", "missing_project"])
def test_structural_errors_are_not_teaching_preferences(tmp_path, mutation):
    _, unit, value = inputs(tmp_path)
    if mutation == "unknown":
        value["lessons"][0]["catalogue_ids"] = ["missing"]
    elif mutation == "duplicate":
        value["lessons"][1]["project_id"] = "lesson-A"
    elif mutation == "empty_exit":
        value["lessons"][0]["exit_task"] = ""
    unit.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        subject.build_context(unit, "missing" if mutation == "missing_project" else "lesson-A", tmp_path)


def test_no_lesson_count_timing_or_narrative_recipe_is_required(tmp_path):
    _, unit, value = inputs(tmp_path)
    value["lessons"] = value["lessons"][:1]
    value["lessons"][0]["custom_design"] = "No hook, no fixed length, a continuous derivation"
    unit.write_text(json.dumps(value))
    result = subject.build_context(unit, "lesson-A", tmp_path)
    assert result["current_lesson"]["custom_design"].startswith("No hook")


@pytest.mark.parametrize("field,value", [("catalogue", ""), ("schema_version", True),
                                        ("schema_version", "1"), ("catalogue", None)])
def test_invalid_course_source_or_schema_is_explicit(tmp_path, field, value):
    _, unit, data = inputs(tmp_path)
    data[field] = value
    unit.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        subject.build_context(unit, "lesson-A", tmp_path)


def test_unhashable_coverage_is_rejected_as_data_not_runtime_error(tmp_path):
    _, unit, data = inputs(tmp_path)
    data["lessons"][0]["catalogue_ids"] = [{"id": "A"}]
    unit.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="coverage"):
        subject.build_context(unit, "lesson-A", tmp_path)


@pytest.mark.parametrize("change", ["missing", "cycle", "duplicate"])
def test_catalogue_graph_errors_are_detected(tmp_path, change):
    table, _, _ = inputs(tmp_path)
    with table.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    if change == "missing":
        rows[0]["requires"] = "unknown"
    elif change == "cycle":
        rows[0]["requires"] = "C"
    else:
        rows[2]["id"] = "A"
    with table.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        subject.catalogue(table)
