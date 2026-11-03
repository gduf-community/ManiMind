"""Topic-independent measured focus windows and full-utterance coverage.

Renderers write measured intervals; narrators reference them; schedulers consume
actual WAV lengths. Intervals alone never prove visibility or understanding:
independent pixel review must verify their semantic meaning. New visuals, speech
or text invalidate the derived schedule; no automatic audio/physics retiming.
"""

from __future__ import annotations

import math
import re


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def safe_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", value))


def focus_windows(report, duration):
    if not finite(duration) or duration <= 0:
        raise ValueError("A measured positive visual duration is required")
    if not isinstance(report, dict) or not finite(report.get("duration")) or abs(report["duration"] - duration) > .04:
        raise ValueError("Focus report and rendered duration disagree")
    rows = report.get("windows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Measured focus windows are required for this alignment")
    result = {}
    for row in rows:
        identity, start, end = row.get("id"), row.get("start"), row.get("end")
        if (not safe_id(identity) or identity in result or not finite(start) or not finite(end)
                or not 0 <= start < end <= duration + 1e-5):
            raise ValueError("Focus windows need unique IDs and nonempty in-range measured intervals")
        result[identity] = dict(row)
    return result


def validate_narration(value, timeline, focuses):
    windows = focus_windows(focuses, timeline["duration"])
    rows = value.get("segments") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("An explicit narration plan is required")
    cues = {row["id"] for row in timeline["cues"]}
    seen = set()
    for row in rows:
        if (not safe_id(row.get("id")) or row["id"] in seen or row.get("cue") not in cues
                or row.get("focus") not in windows or not isinstance(row.get("text"), str)
                or not row["text"].strip()):
            raise ValueError("Each unique narration segment must reference a current cue and measured focus")
        seen.add(row["id"])
    return rows


def schedule(timeline, narration, focuses, durations, *, gap=.25, edge_margin=.12):
    """Place intact speech inside meaning windows, not merely after an anchor."""
    rows = validate_narration(narration, timeline, focuses)
    windows = focus_windows(focuses, timeline["duration"])
    if len(rows) != len(durations) or not finite(gap) or gap < 0 or not finite(edge_margin) or edge_margin < 0:
        raise ValueError("Every sentence needs a measured WAV duration and finite nonnegative margins")
    previous, result = -gap, []
    for row, duration in zip(rows, durations, strict=True):
        if not finite(duration) or duration <= 0:
            raise ValueError("Invalid actual speech duration")
        window = windows[row["focus"]]
        start = math.ceil(max(window["start"] + edge_margin, previous + gap) * 48000) / 48000
        end = start + duration
        if end > window["end"] - edge_margin + 1 / 48000:
            raise ValueError(f"{row['id']} exceeds readable focus {row['focus']}; rewrite speech or revise/review visuals, never silently speed up or truncate")
        result.append({**row, "start": start, "end": end, "duration_seconds": duration,
                       "focus_start": window["start"], "focus_end": window["end"]})
        previous = end
    return result


def audit_coverage(segments, focuses, duration):
    windows = focus_windows(focuses, duration)
    previous, findings = 0.0, []
    for row in segments:
        start, end = row.get("start"), row.get("end")
        window = windows.get(row.get("focus"))
        if (window is None or not finite(start) or not finite(end) or not 0 <= start < end <= duration
                or start < previous - 1e-5 or start < window["start"] - 1e-5 or end > window["end"] + 1e-5):
            findings.append({"id": row.get("id"), "problem": "Whole utterance leaves its readable visual focus or overlaps earlier speech"})
        if finite(end):
            previous = end
    return {"passed": not findings, "findings": findings,
            "scope": "Measured interval coverage, not a listening or comprehension verdict"}
