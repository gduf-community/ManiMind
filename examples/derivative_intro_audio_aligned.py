"""Preparatory semantic windows over frozen v003, without audio scheduling.

Intent declarations belong to this source version and exact reference wording.
Each construct owns fresh transition states and an append-only runtime journal;
the scene writes them to its explicit output directory, reviewers and a future
audio aligner consume them, and any source/text/timing/media change invalidates
them. No WAV, ASR estimate, timing offset or publication permission is created.
"""

import json
import sys
from typing import NamedTuple

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_delivery import DerivativeIntroDeliveryLesson
finally:
    sys.argv = _host_argv
del _host_argv

from manimind.review.meaning_units import validate_units


class FormulaReferent(NamedTuple):
    unit: str
    reference: str
    focus: str
    cue: str
    stage: str
    ready: str
    mode: str
    text: str


FORMULA_REFERENTS = (
    FormulaReferent("algebra_reason", "expand", "expanded_terms", "algebra", "expanded", "expanded_ready",
                    "state", "展开以后，得到四、四h和h平方，最后减四。"),
    FormulaReferent("algebra_reason", "combine", "combined_terms", "algebra", "combined", "combined_ready",
                    "process_result", "两个常数相消，留下四h加h平方。"),
    FormulaReferent("algebra_reason", "factor", "factored_h", "algebra", "factored", "factored_ready",
                    "process_result", "提取公因式h，分子就成了h乘以括号里的四加h。"),
    FormulaReferent("algebra_reason", "simple", "simplified_rate", "algebra", "simplified", "simplified_ready",
                    "state", "于是，每条这样的割线，斜率都等于四加h。"),
    FormulaReferent("name_derivative", "pattern", "definition_pattern", "definition", "general_position",
                    "definition_pattern_ready", "process_result",
                    "把位置写成a，在a附近有定义，差商从两侧趋近同一个有限值时，就用这个极限定义f撇a。"),
)
FROZEN_SCENE_SOURCES = (
    "examples/derivative_intro_delivery.py",
    "examples/derivative_intro_refined.py",
    "examples/derivative_intro_visual.py",
)
STATE_CONTRACTS = (
    {"state": "exact reference declarations and semantic modes", "writer": "lesson author in this source",
     "consumers": ["reference validator", "scene hooks", "independent reviewer"],
     "lifecycle": "This source and exact reference-text version",
     "invalidation": "Reference ID, wording, referent, source or semantic decision changes"},
    {"state": "transition maps, active intent, phase counters and fulfillment flags", "writer": "scene runtime",
     "consumers": ["scene guards", "construct finalizer"],
     "lifecycle": "Created once per construct; failed constructs stay unresolved and cannot finalize or restart in place",
     "invalidation": "Discard with this construct; never reuse across renders or audio attempts"},
    {"state": "append-only process/result journal and inherited measured focus windows", "writer": "scene runtime",
     "consumers": ["lead", "independent reviewer", "future original-audio aligner"],
     "lifecycle": "One exact visual source, cue schedule and render; no timestamps edited after recording",
     "invalidation": "Source, text, cue timing, runtime or media changes require a fresh measurement"},
)


def validate_reference_bindings(narration):
    """Require the existing IDs, wording and semantic referents, without edits."""
    units = {row["id"]: row for row in validate_units(narration)}
    for intent in FORMULA_REFERENTS:
        unit = units.get(intent.unit)
        ref = next((row for row in unit["references"] if row["id"] == intent.reference), None) if unit else None
        if (unit is None or unit["cue"] != intent.cue or ref is None
                or ref["focus"] != intent.focus or ref["text"] != intent.text):
            raise ValueError(f"Reference meaning changed or missing: {intent.unit}/{intent.reference}")
    return FORMULA_REFERENTS


class DerivativeIntroAudioAlignedLesson(DerivativeIntroDeliveryLesson):
    """Measure process/result windows; inherit every visual and local stage time."""

    def _initialize_formula_windows(self):
        if hasattr(self, "_formula_window_states"):
            raise ValueError("Formula window state belongs to one construct only")
        for key in ("focus", "stage", "ready"):
            if len({getattr(row, key) for row in FORMULA_REFERENTS}) != len(FORMULA_REFERENTS):
                raise ValueError("Formula referents must have unique focus, stage and ready IDs")
        if any(row.mode not in {"state", "process_result"} for row in FORMULA_REFERENTS):
            raise ValueError("Each formula referent needs an explicit semantic window mode")
        self._formula_window_events = []
        self._formula_window_states = {
            intent.focus: {"intent": intent, "status": "armed", "samples": {"tokens": 0, "syntax": 0},
                           "ready_seen": False, "base_focus_claimed": False}
            for intent in FORMULA_REFERENTS
        }
        self._formula_stage_to_focus = {row.stage: row.focus for row in FORMULA_REFERENTS}
        self._formula_ready_to_focus = {row.ready: row.focus for row in FORMULA_REFERENTS}
        self._active_formula_focus = None

    def _record_formula_window(self, state, phase, **details):
        intent = state["intent"]
        self._formula_window_events.append({
            "phase": phase, "time": float(self.get_time()), "focus": intent.focus,
            "stage": intent.stage, "cue": intent.cue, "unit": intent.unit,
            "reference": intent.reference, "mode": intent.mode, "details": details,
        })

    def _start_formula_action(self, state):
        if state["status"] not in {"armed", "awaiting_condition_relocation"}:
            raise ValueError("Formula action must start exactly once")
        state["status"] = "running"
        state["started_at"] = float(self.get_time())
        self._record_formula_window(state, "action_started")
        if state["intent"].mode == "process_result":
            super().focus_begin(state["intent"].focus)
            self._record_formula_window(state, "process_focus_opened")

    def readable_matching(self, source, target, end, stage):
        focus = self._formula_stage_to_focus.get(stage)
        if focus is None or self._active_formula_focus is not None:
            raise ValueError("Unexpected or nested formula transition")
        state = self._formula_window_states[focus]
        if state["status"] != "armed" or self._cue["id"] != state["intent"].cue:
            raise ValueError("Formula intent is duplicate or outside its declared cue")
        if not any(source is member for obj in self.mobjects for member in obj.get_family()):
            raise ValueError("A formula action needs its actual visible source on stage")
        count = len(self.symbol_transitions)
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        if stage == "simplified":
            # Frozen v003 first moves the condition; that is not formula assembly.
            state["status"] = "awaiting_condition_relocation"
        else:
            self._start_formula_action(state)
        result = super().readable_matching(source, target, end, stage)
        if (state["status"] != "running" or result is not target
                or len(self.symbol_transitions) != count + 1
                or not all(state["samples"].values())
                or float(self.get_time()) <= state["started_at"]):
            raise ValueError("Formula intent was not fulfilled by an actual staged transition")
        transition = self.symbol_transitions[-1]
        if (transition["stage"] != stage or transition["target"] != target.get_tex()
                or transition["end"] != float(self.get_time())
                or not any(target is member for obj in self.mobjects for member in obj.get_family())):
            raise ValueError("Completed formula state does not match the current scene")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return result

    def sample(self, kind, **values):
        super().sample(kind, **values)
        focus = self._active_formula_focus
        if focus is None:
            return
        state = self._formula_window_states[focus]
        if (kind == "condition_relocation" and values.get("phase") == "after"
                and state["intent"].stage == "simplified"):
            self._record_formula_window(state, "condition_relocated")
            self._start_formula_action(state)
        elif kind == "refined_formula":
            if state["status"] != "running" or values.get("stage") != state["intent"].stage:
                raise ValueError("Formula samples must belong to the currently running intent")
            phase = values.get("phase")
            if phase not in state["samples"]:
                raise ValueError("Unexpected formula assembly phase")
            state["samples"][phase] += 1

    def mark(self, event_id):
        focus = self._formula_ready_to_focus.get(event_id)
        if focus is not None:
            state = self._formula_window_states[focus]
            if state["status"] != "completed" or state["ready_seen"]:
                raise ValueError("A ready mark requires the actual completed formula exactly once")
            super().mark(event_id)
            state["ready_seen"] = True
            self._record_formula_window(state, "ready_marked", anchor=event_id)
        else:
            super().mark(event_id)

    def focus_begin(self, identity):
        state = self._formula_window_states.get(identity)
        if state is None:
            return super().focus_begin(identity)
        if state["status"] != "completed" or not state["ready_seen"] or state["base_focus_claimed"]:
            raise ValueError("Result focus needs one completed, ready formula handoff")
        if state["intent"].mode == "process_result":
            if identity not in self._open_focus:
                raise ValueError("The measured process window was lost before its result")
            self._record_formula_window(state, "result_available")
        else:
            super().focus_begin(identity)
            self._record_formula_window(state, "state_focus_opened")
        state["base_focus_claimed"] = True

    def focus_end(self, identity):
        state = self._formula_window_states.get(identity)
        if state is None:
            return super().focus_end(identity)
        if state["status"] != "completed" or not state["ready_seen"] or not state["base_focus_claimed"]:
            raise ValueError("Cannot close an unfulfilled formula process/result intent")
        super().focus_end(identity)
        state["status"] = "closed"
        self._record_formula_window(state, "focus_closed")

    def _finish_formula_windows(self):
        if self._active_formula_focus is not None or any(
                row["status"] != "closed" for row in self._formula_window_states.values()):
            raise ValueError("Every declared formula intent must be fulfilled and closed")
        if self._open_focus:
            raise ValueError("Close every measured focus before the preparatory handoff")
        return {
            "schema_version": 1, "status": "preparatory_not_audio_aligned",
            "duration": float(self.get_time()),
            "references": [row._asdict() for row in FORMULA_REFERENTS],
            "events": self._formula_window_events,
            "state_contracts": list(STATE_CONTRACTS),
            "writer": "DerivativeIntroAudioAlignedLesson actual scene runtime",
            "consumers": ["lead", "independent reviewer", "future audio aligner"],
            "lifecycle": "One exact construct, cue schedule and source/reference version",
            "invalidation": "Source, references, cue timing, runtime or media change",
            "limitation": "Process windows record actions and results, not visibility at every subclause; actual pixels and original audio still require review",
            "audio_measurements": "not_provided", "audio_schedule": "not_created",
        }

    def construct(self):
        self._initialize_formula_windows()
        super().construct()
        report = self._finish_formula_windows()
        with (self.out / "formula-focus-events.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
