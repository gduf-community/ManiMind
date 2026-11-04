"""Check editorial scene data and render its human-readable course tables."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = Path("docs/curricula/scene-library")
FIELDS = (
    "id", "module", "title", "visual_mechanism", "prerequisites", "transfer_check",
    "scope_note", "priority", "source_ids", "reference_locator", "curriculum_refs",
)
PRIORITIES = ("优先", "进阶", "待验证")


def read_csv(path, fields=None):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if fields is not None and tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"Unexpected fields: {path.name}")
        rows = list(reader)
    if not rows or any(None in row or None in row.values() for row in rows):
        raise ValueError(f"Empty or malformed CSV: {path.name}")
    return rows


def load(root=ROOT):
    root = Path(root)
    folder = root / LIBRARY
    index = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    required = {"writer", "consumers", "lifecycle", "invalidation", "purpose"}
    if not required <= index.keys():
        raise ValueError("Missing editorial ownership metadata")
    sources = read_csv(folder / index["sources"])
    source_ids = {row["id"] for row in sources}
    if len(source_ids) != len(sources):
        raise ValueError("Duplicate source ID")
    old_ids = {}
    for course in ("mathematics", "physics"):
        old_ids[course] = {row["id"] for row in read_csv(
            root / f"docs/curricula/high-school-{course}-v0.1.csv")}
    seen, course_ids, files, titles, catalogues = set(), set(), set(), set(), []
    for course in index["courses"]:
        filename = Path(course["file"])
        if filename.name != str(filename) or filename.suffix != ".csv":
            raise ValueError("Catalogue must be a local CSV filename")
        if course["id"] in course_ids or course["file"] in files:
            raise ValueError("Duplicate course or file")
        course_ids.add(course["id"])
        files.add(course["file"])
        rows = read_csv(folder / filename, FIELDS)
        for row in rows:
            identifier = row["id"]
            if not re.fullmatch(re.escape(course["prefix"]) + r"-\d{3}", identifier):
                raise ValueError(f"Invalid scene ID: {identifier}")
            if identifier in seen or row["title"] in titles:
                raise ValueError(f"Duplicate scene: {identifier}")
            seen.add(identifier)
            titles.add(row["title"])
            if any(not row[key].strip() for key in FIELDS if key != "curriculum_refs"):
                raise ValueError(f"Missing teaching field: {identifier}")
            if row["priority"] not in PRIORITIES:
                raise ValueError(f"Invalid priority: {identifier}")
            if not set(row["source_ids"].split(";")) <= source_ids:
                raise ValueError(f"Unknown source: {identifier}")
            refs = set(filter(None, row["curriculum_refs"].split(";")))
            subject = course["id"].removeprefix("high-school-")
            if refs and not refs <= old_ids.get(subject, set()):
                raise ValueError(f"Invalid curriculum reference: {identifier}")
        catalogues.append((course, rows))
    if len(index["pilot_scenes"]) != len(set(index["pilot_scenes"])):
        raise ValueError("Duplicate pilot scene")
    if not set(index["pilot_scenes"]) <= seen:
        raise ValueError("Unknown pilot scene")
    return index, catalogues


def cell(value):
    return value.replace("|", "\\|").replace("\n", " ")


def views(root=ROOT):
    index, catalogues = load(root)
    summary = ["# 精选动画场景总目录", "", "按课程分别浏览。以下为持续扩充的首轮候选，不设总数配额。", "",
               "| 课程 | 候选数 | 优先 | 进阶 | 待验证 |", "| --- | ---: | ---: | ---: | ---: |"]
    output = {}
    for course, rows in catalogues:
        name = course["id"] + ".md"
        counts = [sum(row["priority"] == p for row in rows) for p in PRIORITIES]
        summary.append(f"| [{course['title']}]({name}) | {len(rows)} | " + " | ".join(map(str, counts)) + " |")
        lines = [f"# {course['title']}动画场景", "", course["scope"], "",
                 "每项围绕一个理解障碍。可按学生基础调用先修知识，无需先看本项目其他视频。", "",
                 f"[完整教研字段]({course['file']}) · [来源与范围](../../research/animation-selection-20261104.md)", ""]
        modules = dict.fromkeys(row["module"] for row in rows)
        for module in modules:
            lines += [f"## {module}", "", "| 编号 | 场景问题 | 动画怎样帮助理解 | 优先级 |",
                      "| --- | --- | --- | --- |"]
            for row in rows:
                if row["module"] == module:
                    lines.append("| " + " | ".join(cell(row[k]) for k in (
                        "id", "title", "visual_mechanism", "priority")) + " |")
            lines.append("")
        output[LIBRARY / name] = "\n".join(lines).rstrip() + "\n"
    summary += ["", f"合计 {sum(len(rows) for _, rows in catalogues)} 个候选场景。数量是当前编辑库存，不代表已制作或已验证。", "",
                "## 小批试片建议", "", "| 编号 | 课程 | 场景 |", "| --- | --- | --- |"]
    by_id = {row["id"]: (course["title"], row["title"]) for course, rows in catalogues for row in rows}
    for identifier in index["pilot_scenes"]:
        summary.append("| " + " | ".join((identifier, *by_id[identifier])) + " |")
    summary += ["", "先用这批试片检验不同解释机制，再按教师与学生反馈调整选题和排序。", "",
                "本页和分科表从 CSV 生成；逐项修改后运行 `python3 scripts/check_animation_catalogues.py --write`。", ""]
    output[LIBRARY / "总目录.md"] = "\n".join(summary)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate the Markdown tables")
    args = parser.parse_args()
    expected = views()
    for relative, content in expected.items():
        target = ROOT / relative
        if args.write:
            target.write_text(content, encoding="utf-8")
        elif not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Out-of-date table: {relative}")
    _, catalogues = load()
    print(json.dumps({"courses": {c["title"]: len(rows) for c, rows in catalogues},
                      "total": sum(len(rows) for _, rows in catalogues),
                      "generated_tables": len(expected), "quantity_cap": None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
