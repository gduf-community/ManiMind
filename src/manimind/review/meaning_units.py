"""Continuous speech units with multiple measured visual references.

Narrators write schema-3 project inputs; the forced aligner writes session-scoped
model estimates, never listening/ASR certification. The scheduler consumes both
and actual WAV receipts. Text, reference, WAV or model changes invalidate timings;
visual/cue changes invalidate placement, but do not themselves invalidate speech.
No topic, lesson length, shot count or minimum reference count is prescribed.
"""

from __future__ import annotations

import math
from pathlib import Path
import re

from .semantic_focus import finite, focus_windows, safe_id

SOURCE_CONTRACT = "continuous-meaning-units-v1"
FOCUS_SCOPE = "meaning_unit_not_visual_focus"
TIMING_METHOD = "stable_whisper_forced_alignment"
TIMING_SCOPE = "model_estimated_forced_alignment_not_listening"


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))


def validate_units(value):
    """Validate text without normalizing punctuation, whitespace or references."""
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 3:
        raise ValueError("Require schema_version=3 meaning units, not legacy visual-focus segments")
    rows = value.get("units")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Require a nonempty units list")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "cue", "text", "references"}
                or not safe_id(row.get("id")) or row["id"].casefold() in seen
                or row["id"].upper() in {"CON", "PRN", "AUX", "NUL"}
                or re.fullmatch(r"(?:COM|LPT)[1-9]", row["id"], re.I)
                or not safe_id(row.get("cue")) or not _text(row.get("text"))):
            raise ValueError("Each unique Windows-safe meaning unit needs id, cue, text and references; no unit visual focus")
        seen.add(row["id"].casefold())
        refs, ids = row.get("references"), set()
        if not isinstance(refs, list) or not refs:
            raise ValueError("Meaning units require ordered semantic references")
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {"id", "focus", "text"}
                    or not safe_id(ref.get("id")) or ref["id"] in ids
                    or not safe_id(ref.get("focus")) or not _text(ref.get("text"))):
                raise ValueError("Each reference needs a unique local id, measured visual focus and exact text")
            ids.add(ref["id"])
        if "".join(ref["text"] for ref in refs) != row["text"]:
            raise ValueError("Ordered reference text must equal unit.text character for character")
    return rows


def cue_windows(timeline):
    if not isinstance(timeline, dict) or not finite(timeline.get("duration")) or timeline["duration"] <= 0:
        raise ValueError("Require a measured visual timeline")
    rows, result = timeline.get("cues"), {}
    if not isinstance(rows, list) or not rows:
        raise ValueError("Require measured cue boundaries")
    previous = 0
    for row in rows:
        if (not isinstance(row, dict) or not safe_id(row.get("id")) or row["id"] in result
                or not finite(row.get("start")) or not finite(row.get("duration"))
                or row["duration"] <= 0 or row["start"] + 1e-8 < previous
                or row["start"] + row["duration"] > timeline["duration"] + 1e-8):
            raise ValueError("Cue intervals must be finite, ordered, unique and inside the film")
        previous = row["start"] + row["duration"]
        result[row["id"]] = (row["start"], previous)
    return result


def validate_narration(value, timeline, focuses):
    rows = validate_units(value)
    cues = cue_windows(timeline)
    windows = focus_windows(focuses, timeline["duration"])
    for row in rows:
        if row["cue"] not in cues or any(ref["focus"] not in windows for ref in row["references"]):
            raise ValueError("Each meaning unit must reference a current cue and measured focus file")
    return rows


def transport_segments(value):
    return [{**row, "focus": row["id"], "focus_scope": FOCUS_SCOPE} for row in validate_units(value)]


def validate_timings(value, narration, *, plan_sha256, wav_sha256s, durations):
    """Pure structural checks; production must ALSO call the aligner's verifier."""
    rows = validate_units(narration)
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or value.get("method") != TIMING_METHOD or value.get("timing_scope") != TIMING_SCOPE
            or not _hash(plan_sha256) or value.get("plan_sha256") != plan_sha256
            or any(not _text(value.get(key)) for key in ("writer", "lifecycle", "invalidation"))
            or not isinstance(value.get("consumers"), list) or not value["consumers"]
            or any(not _text(item) for item in value["consumers"])
            or value.get("smoke_only") is not False or value.get("listening_reviewed") is not False
            or value.get("test_only") is not False
            or value.get("acceptance") != "estimated_not_listening_or_publication_approved"
            or not _text(value.get("attempt")) or not Path(value["attempt"]).is_absolute()
            or not _text(value.get("plan")) or not Path(value["plan"]).is_absolute()
            or not isinstance(value.get("software"), dict) or not value["software"]
            or not isinstance(value.get("sources"), list) or not value["sources"]):
        raise ValueError("Require provenance-bound forced alignment estimates, not listening certification")
    seen_sources = set()
    for source in value["sources"]:
        if (not isinstance(source, dict) or not _text(source.get("path"))
                or not Path(source["path"]).is_absolute() or source["path"] in seen_sources
                or not _hash(source.get("sha256"))):
            raise ValueError("Forced alignment needs unique absolute source paths and fingerprints")
        seen_sources.add(source["path"])
    measured = value.get("units")
    if (not isinstance(measured, list) or len(measured) != len(rows)
            or len(wav_sha256s) != len(rows) or len(durations) != len(rows)):
        raise ValueError("Every intact unit WAV needs measured phrase timings")
    for unit, item, wav_sha, duration in zip(rows, measured, wav_sha256s, durations, strict=True):
        if (not isinstance(item, dict) or item.get("id") != unit["id"] or not _hash(wav_sha)
                or item.get("wav_sha256") != wav_sha or not finite(duration) or duration <= 0
                or not finite(item.get("duration_seconds"))
                or abs(item["duration_seconds"] - duration) > 1 / 48000):
            raise ValueError("Forced alignment must bind exact unit IDs, WAV hashes and measured durations")
        phrases = item.get("phrases")
        if not isinstance(phrases, list) or len(phrases) != len(unit["references"]):
            raise ValueError("Every ordered reference requires its own measured phrase")
        previous = 0
        for ref, phrase in zip(unit["references"], phrases, strict=True):
            if (not isinstance(phrase, dict) or phrase.get("id") != ref["id"] or phrase.get("text") != ref["text"]
                    or not finite(phrase.get("start")) or not finite(phrase.get("end"))
                    or not previous <= phrase["start"] < phrase["end"] <= duration):
                raise ValueError("Measured phrases must preserve exact reference text/order and fit intact WAV")
            previous = phrase["end"]
    return measured


def schedule(timeline, narration, focuses, timings, *, gap=0.0, durations=None):
    """Intersect ALL per-phrase legal starts, cue bounds and intact WAV bounds."""
    if not isinstance(timings, dict) or not isinstance(timings.get("units"), list):
        raise ValueError("Require measured unit timings")
    units = validate_narration(narration, timeline, focuses)
    actual = durations if durations is not None else [row.get("duration_seconds") for row in timings.get("units", [])]
    measured = validate_timings(timings, narration, plan_sha256=timings.get("plan_sha256"),
        wav_sha256s=[row.get("wav_sha256") for row in timings.get("units", [])],
        durations=actual)
    if not finite(gap) or gap < 0:
        raise ValueError("Require a finite nonnegative speech gap")
    windows, cues = focus_windows(focuses, timeline["duration"]), cue_windows(timeline)
    result, previous = [], -gap
    for unit, timing, duration in zip(units, measured, actual, strict=True):
        cue_start, cue_end = cues[unit["cue"]]
        low, high = max(0, cue_start, previous + gap), min(cue_end, timeline["duration"]) - duration
        for ref, phrase in zip(unit["references"], timing["phrases"], strict=True):
            window = windows[ref["focus"]]
            low = max(low, window["start"] - phrase["start"])
            high = min(high, window["end"] - phrase["end"])
        # Only the placement is quantized to a PCM sample; never trim the WAV.
        start = math.ceil(low * 48000 - 1e-8) / 48000
        if start > high + 1e-10:
            raise ValueError(f"{unit['id']}: no intersection of phrase focus/cue/full-WAV bounds; revise/review visuals or text, never trim or speed up")
        result.append({**unit, "start": start, "end": start + duration,
                       "duration_seconds": duration, "legal_start": [low, high],
                       "phrases": [{**phrase, "focus": ref["focus"],
                                    "visual_start": start + phrase["start"], "visual_end": start + phrase["end"],
                                    "focus_start": windows[ref["focus"]]["start"],
                                    "focus_end": windows[ref["focus"]]["end"]}
                                   for ref, phrase in zip(unit["references"], timing["phrases"], strict=True)]})
        previous = start + duration
    return result
