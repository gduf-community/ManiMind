"""Film clock from voiced meaning units: character times -> cue times and caption rows.

Input is one JSON per attempt, ``{"units": {unit_id: {"text": str, "chars": [[char, seconds], ...]}}}``,
where seconds are relative to the unit's own WAV (forced alignment of the whole, unedited take), plus
where each unit starts on the film clock. Everything here is a pure function of those inputs, so a
scene's CUES can be regenerated whenever the voice changes; the scene code itself does not change.

State: the generated timing file is written by the scene's build step and read by the scene page;
it is valid only for the exact speech attempt and placement it was computed from.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

PUNCT = "，。、；：！？,.;:!? "


@dataclass(frozen=True)
class Unit:
    id: str
    text: str
    start: float                      # where the unit's WAV starts on the film clock
    chars: tuple                      # ((char, seconds within the WAV), ...), punctuation excluded

    @property
    def spoken(self) -> str:
        return "".join(c for c, _ in self.chars)


def load_units(alignment: dict, starts: dict) -> dict:
    """Build Units from an alignment dict and {unit_id: film start}; refuses text/char mismatches."""
    units = {}
    for uid, start in starts.items():
        row = alignment["units"][uid]
        chars = tuple((c, float(t)) for c, t in row["chars"])
        expected = "".join(c for c in row["text"] if c not in PUNCT)
        if "".join(c for c, _ in chars) != expected:
            raise ValueError(f"{uid}: aligned characters do not match the unit text")
        if any(b[1] < a[1] for a, b in zip(chars, chars[1:])):
            raise ValueError(f"{uid}: character times go backwards")
        units[uid] = Unit(uid, row["text"], float(start), chars)
    return units


def at(unit: Unit, word: str, nth: int = 0) -> float:
    """Film time of the first character of the nth occurrence of ``word`` (spaces/punctuation ignored)."""
    target = "".join(c for c in word if c not in PUNCT)
    i = -1
    for _ in range(nth + 1):
        i = unit.spoken.find(target, i + 1)
        if i < 0:
            raise KeyError(f"{word!r} (occurrence {nth}) not spoken in {unit.id}")
    return round(unit.start + unit.chars[i][1], 3)


def caption_rows(units, *, max_chars: int = 15, tail: float = 0.3, replace: dict | None = None,
                 unit_end: dict | None = None) -> list:
    """Clause captions [start, end, text]: each starts at its first spoken character.

    Clauses split at ，。 and merge while they fit ``max_chars``. A row ends just before the next one;
    the last row of a unit ends ``tail`` after the unit's end (``unit_end[id]``, film time) or after its
    last character. ``replace`` maps spoken words to their on-screen form, e.g. {"拉姆达": " λ "}.
    """
    replace = replace or {}
    rows = []
    for unit in units:
        clauses = [s for s in re.split(r"[，。]", unit.text) if s.strip()]
        merged, i = [], 0
        for clause in clauses:
            start = round(unit.start + unit.chars[i][1], 3)
            i += sum(1 for ch in clause if ch not in PUNCT)
            shown = clause
            for spoken, written in replace.items():
                shown = shown.replace(spoken, written)
            shown = re.sub(r" +", " ", shown).strip()
            if merged and len(merged[-1][2]) + len(shown) <= max_chars:
                merged[-1][2] += "  " + shown
            else:
                merged.append([start, None, shown])
        end = (unit_end or {}).get(unit.id, unit.start + unit.chars[-1][1]) + tail
        for k, row in enumerate(merged):
            row[1] = round(merged[k + 1][0] - 0.05 if k + 1 < len(merged) else end, 3)
        rows.extend(merged)
    return rows


def check_schedule(units, durations: dict, boundaries: dict, gap: float = 0.25) -> list:
    """Problems with a placement: overlapping units or a unit running past its shot boundary.

    ``durations`` = {unit_id: WAV seconds}; ``boundaries`` = {unit_id: film time its shot changes}.
    Returns a list of human-readable problems (empty = fine). Whole takes are never trimmed or sped up.
    """
    problems = []
    ordered = sorted(units, key=lambda u: u.start)
    for a, b in zip(ordered, ordered[1:]):
        if a.start + durations[a.id] + gap > b.start:
            problems.append(f"{a.id} ends {a.start + durations[a.id]:.2f}s, too close to {b.id} at {b.start:.2f}s")
    for u in ordered:
        limit = boundaries.get(u.id)
        if limit is not None and u.start + durations[u.id] > limit:
            problems.append(f"{u.id} ends {u.start + durations[u.id]:.2f}s after its shot changes at {limit:.2f}s")
    return problems
