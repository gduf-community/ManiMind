"""Versioned course excerpts for one lesson, not a prescribed teaching template.

Editors own unit plans; this module selects catalogue exits and adjacent lesson
intentions. It never infers mastery, assigns media approval, or schedules agents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re


ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,100}\Z")
CATALOGUE_FIELDS = {"id", "module", "title", "role", "requires", "new_understanding", "reuse", "exit_check", "split_hint"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def catalogue(path):
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if len(reader.fieldnames or []) != len(CATALOGUE_FIELDS) or set(reader.fieldnames or []) != CATALOGUE_FIELDS:
            raise ValueError("Unknown course catalogue fields")
        rows = list(reader)
    result = {}
    for row in rows:
        identity = row.get("id")
        if (None in row or not isinstance(identity, str) or not ID.fullmatch(identity)
                or identity in result or any(not value for key, value in row.items() if key != "requires")):
            raise ValueError("Catalogue rows need unique IDs and complete descriptions")
        result[identity] = {**row, "requires": [name for name in row["requires"].split(";") if name]}
    active, done = set(), set()

    def visit(identity):
        if identity not in result:
            raise ValueError(f"Unknown prerequisite: {identity}")
        if identity in active:
            raise ValueError("Hard-prerequisite graph contains a cycle")
        if identity in done:
            return
        active.add(identity)
        for dependency in result[identity]["requires"]:
            visit(dependency)
        active.remove(identity)
        done.add(identity)

    for identity in result:
        visit(identity)
    return result


def validate_unit(value, rows):
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Require an explicit course-unit schema")
    for field in ("unit_id", "title", "audience", "scope"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(f"Course unit needs {field}")
    if not ID.fullmatch(value["unit_id"]):
        raise ValueError("Unsafe course unit ID")
    lessons = value.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        raise ValueError("Course unit needs a lesson sequence")
    seen = set()
    for lesson in lessons:
        identity = lesson.get("project_id") if isinstance(lesson, dict) else None
        if not isinstance(identity, str) or not ID.fullmatch(identity) or identity in seen:
            raise ValueError("Lesson project IDs must be unique")
        seen.add(identity)
        names = lesson.get("catalogue_ids")
        if (not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names)
                or len(names) != len(set(names)) or any(name not in rows for name in names)):
            raise ValueError("Lesson coverage must reference current catalogue entries")
        for field in ("new_understanding", "exit_task", "handoff"):
            if not isinstance(lesson.get(field), str) or not lesson[field].strip():
                raise ValueError(f"Lesson needs an explicit {field}; no fixed narrative form is required")
    return lessons


def build_context(unit_path, project_id, root):
    root, unit_path = Path(root).resolve(), Path(unit_path).resolve()
    unit = read(unit_path)
    if not isinstance(unit, dict) or not isinstance(unit.get("catalogue"), str) or not unit["catalogue"].strip():
        raise ValueError("Course unit must name a catalogue")
    source = (root / unit["catalogue"]).resolve()
    rows = catalogue(source)
    lessons = validate_unit(unit, rows)
    matches = [index for index, row in enumerate(lessons) if row["project_id"] == project_id]
    if len(matches) != 1:
        raise ValueError("Project is not in this course unit")
    index = matches[0]
    current = lessons[index]
    selected = [rows[name] for name in current["catalogue_ids"]]
    prerequisite_ids = list(dict.fromkeys(name for row in selected for name in row["requires"]))
    return {"schema_version": 1, "unit_id": unit["unit_id"], "title": unit["title"],
            "audience": unit["audience"], "scope": unit["scope"], "current_lesson": current,
            "previous_lesson": lessons[index - 1] if index else None,
            "next_lesson": lessons[index + 1] if index + 1 < len(lessons) else None,
            "catalogue_excerpts": selected,
            "prerequisite_exits": [rows[name] for name in prerequisite_ids],
            "entry_assumptions": unit.get("entry_assumptions", []),
            "entry_evidence_status": unit.get("entry_evidence_status", "assumed_not_tested"),
            "author_guidance": unit.get("author_guidance", []),
            "course_alignment_status": unit.get("course_alignment_status", "draft_not_teacher_certified"),
            "sources": {"unit": str(unit_path), "unit_sha256": sha(unit_path),
                        "catalogue": str(source), "catalogue_sha256": sha(source),
                        "context_builder_sha256": sha(__file__)},
            "writer": "Course excerpt builder from editor-owned unit and catalogue",
            "consumers": ["lesson author", "narrator", "independent course reviewer", "unit publisher"],
            "lifecycle": "This unit/catalogue revision and selected lesson",
            "invalidation": "Unit, catalogue, selection, or context-builder change",
            "boundary": "Guidance and assumed learner entry; not mastery, official coverage, or media approval"}


def verify_context(path, root):
    value = read(path)
    rebuilt = build_context(value["sources"]["unit"], value["current_lesson"]["project_id"], root)
    if value != rebuilt:
        raise ValueError("Course excerpt or its inputs changed")
    return value


def write_context(unit_path, project_id, output, root):
    root, output = Path(root).resolve(), Path(output).absolute()
    if os.path.lexists(output):
        raise FileExistsError(output)
    if not output.resolve().is_relative_to(root / "runtime/projects"):
        raise ValueError("Course context belongs to long-term runtime/projects")
    value = build_context(unit_path, project_id, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--unit", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        if args.unit is None or args.project is None:
            parser.error("build requires --unit and --project")
        value = write_context(args.unit, args.project, args.output, args.root)
    else:
        value = verify_context(args.output, args.root)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
