"""Reading retiming author checks; no pixel or listening certification."""
import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reading_author_evidence", ROOT / "runtime/sessions/wave-alignment-20261031/author-reading/evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

@pytest.fixture(scope="module")
def result():
    return evidence.report("preflight")

def test_complete_audio_and_every_reference_fit(result):
    assert all(r["feasible"] for r in result["per_unit"])
    assert len(result["schedule"]) == 6
    assert sum(len(r["references"]) for r in result["schedule"]) == 19
    assert sum(r["duration_seconds"] for r in result["schedule"]) == pytest.approx(194.72)

def test_every_original_physical_target_and_rate_is_retained(result):
    assert result["physical_advance_targets"]["time_record"] == ["1", "2", "4", "5.5", "8"]
    assert result["physical_advance_targets"]["speed"] == ["2", "4"]
    assert result["physical_advance_targets"]["direction"] == ["0.5"]
    for screen, physics, rate in result["dry_physics_intervals"]:
        assert screen == pytest.approx(physics)
        assert rate == "linear"

@pytest.mark.parametrize("event", ["record_quarter", "record_half", "record_cycle", "record_two_cycles", "speed_one_cycle", "direction_shifted"])
def test_result_inside_corresponding_process_words(result, event):
    row = next(r for r in result["word_landmarks"] if r["event"] == event)
    assert row["absolute_word_span"][0] <= row["event_time"] <= row["absolute_word_span"][1]

def test_results_visible_before_spoken_assertions(result):
    for quote in ("相隔四米", "量出两米", "相隔一个波长", "波速等于走过的距离除以所用时间",
                  "所以波速等于波长除以周期", "得到每秒一米", "灰线留下原来", "位移从零增大到正值",
                  "读出波长四米", "读出周期四秒"):
        row = next(r for r in result["word_landmarks"] if r["quote"] == quote)
        assert row["event_time"] <= row["absolute_word_span"][0] + .02

def test_frozen_zero_length_estimates_remain_explicit(result):
    row = next(r for r in result["word_landmarks"] if r["unit"] == "R05" and r["quote"] == "向上运动")
    assert not row["all_word_durations_positive"]
    assert result["listening_review"] == "not_performed"

def test_original_geometry_formula_units_and_display_calls_are_preserved():
    names = {"put", "label", "span", "axes", "string_world", "phase_marker", "clock", "title",
             "point", "Dot", "Circle", "Line", "Arrow", "polyline", "ValueTracker"}
    def signatures(path):
        tree = ast.parse(path.read_text())
        return {method.name: [ast.dump(call, include_attributes=False) for call in ast.walk(method)
            if isinstance(call, ast.Call) and
            ((isinstance(call.func, ast.Attribute) and call.func.attr in names) or
             (isinstance(call.func, ast.Name) and call.func.id in names))]
            for cls in tree.body if isinstance(cls, ast.ClassDef) for method in cls.body
            if isinstance(method, ast.FunctionDef) and method.name in evidence.advance_targets(path)}
    assert signatures(ROOT / "examples/wave_reading_visual.py") == signatures(ROOT / "examples/wave_reading_audio_aligned.py")
