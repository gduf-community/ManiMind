"""Pure visual clocks and measured narration anchors; no speech synthesis."""

from __future__ import annotations

import ast
import math
import re

from .freeform_agent import check_agent_source


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def visual_timeline(plan, fps=30):
    if type(fps) is not int or fps <= 0:
        raise ValueError("Visual fps must be a positive integer")
    if not isinstance(plan, dict) or not isinstance(plan.get("title"), str) or not plan["title"].strip():
        raise ValueError("A visual plan needs a title")
    cues = plan.get("cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("A visual plan needs cues")
    ids, anchors, result, cursor = set(), set(), [], 0.0
    for cue in cues:
        name = cue.get("id")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) or name in ids:
            raise ValueError("Visual cue ids must be unique safe names")
        if not positive(cue.get("duration")):
            raise ValueError("Visual duration must be positive and finite")
        for field in ("heading", "visual", "learning_purpose"):
            if not isinstance(cue.get(field), str) or not cue[field].strip():
                raise ValueError(f"Visual cue needs {field}")
        entries = cue.get("anchors")
        if not isinstance(entries, list) or not entries:
            raise ValueError("Each cue needs at least one named visual event")
        for entry in entries:
            anchor = entry.get("id")
            if (not isinstance(anchor, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", anchor)
                    or anchor in anchors or not isinstance(entry.get("meaning"), str) or not entry["meaning"].strip()):
                raise ValueError("Visual anchors need unique names and meanings")
            anchors.add(anchor)
        duration = math.ceil(cue["duration"] * fps) / fps
        # Narration is deliberately absent. This compatibility field renders no subtitles.
        result.append({k: v for k, v in {**cue, "start": round(cursor, 9), "duration": duration,
                                       "spoken_spans": []}.items() if k not in {"spoken", "subtitle_lines", "audio_path"}})
        ids.add(name)
        cursor += duration
    return {"mode": "visual_first_silent", "fps": fps, "duration": round(cursor, 9), "cues": result}


def validate_events(timeline, events):
    expected = {a["id"]: cue for cue in timeline["cues"] for a in cue["anchors"]}
    rows = events.get("events")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Every declared visual event must be measured once by the renderer")
    seen, previous = set(), -1.0
    for row in rows:
        name, when = row.get("id"), row.get("time")
        cue = expected.get(name)
        if (cue is None or name in seen or type(when) not in (int, float) or not math.isfinite(when)
                or when < previous or not cue["start"] <= when < cue["start"] + cue["duration"]):
            raise ValueError("Visual event is duplicate, unknown, out of cue, or not monotonic")
        seen.add(name)
        previous = when
    if not positive(events.get("duration")) or abs(events["duration"] - timeline["duration"]) > .1:
        raise ValueError("Measured visual duration differs from the visual plan")
    return rows


def narration_plan(value, timeline, events):
    measured = {row["id"]: row["time"] for row in validate_events(timeline, events)}
    cue_ids = {cue["id"] for cue in timeline["cues"]}
    anchor_cues = {a["id"]: cue["id"] for cue in timeline["cues"] for a in cue["anchors"]}
    rows = value.get("segments") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("Post-visual narration needs segments")
    result = []
    for row in rows:
        if (row.get("cue") not in cue_ids or anchor_cues.get(row.get("anchor")) != row["cue"]
                or row.get("relation") not in {"before", "during", "after"}
                or not isinstance(row.get("text"), str) or not row["text"].strip()):
            raise ValueError("Narration must reference a measured event in its own cue")
        result.append({**row, "anchor_time": measured[row["anchor"]]})
    if {row["cue"] for row in result} != cue_ids:
        raise ValueError("Declare the intended narration for every visual cue")
    return {"segments": result, "audio_status": "not_generated",
            "alignment_status": "semantic_intent_only_not_final_audio_timing",
            "instruction": "Future speech may require text edits or local visual holds; do not globally retime physics"}


def check_visual_source(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "manimind.experiments.visual_first_support":
            if node.level or any(a.name != "VisualLessonScene" for a in node.names):
                raise ValueError("Only VisualLessonScene may be imported from the visual runtime")
            node.module = "manimind.experiments.freeform_support"
    # Normalize only the validation AST, never the candidate bytes or its provenance.
    check_agent_source(ast.unparse(tree))
