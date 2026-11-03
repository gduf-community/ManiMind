"""Formation retiming contracts; these checks never approve pixels or audio."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/wave_formation_audio_aligned.py"
SESSION = ROOT / "runtime/sessions/wave-alignment-20261031/author-formation"
PLAN = ROOT / "runtime/projects/wave-formation-20261028/plan-audio-aligned-v001.json"


def test_case_inherits_plain_lesson_and_only_overrides_chapter_timing():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert ast.unparse(cls.bases[0]) == "WaveFormationPlainLesson"
    assert {n.name for n in cls.body if isinstance(n, ast.FunctionDef)} == {
        "contrast", "formation", "delay", "period", "exit_task"}
    assert not any(isinstance(n, ast.ImportFrom) and "audio_aligned" in (n.module or "") for n in tree.body)


def test_all_original_physical_advance_targets_are_retained():
    def targets(path):
        tree = ast.parse(path.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        return {m.name: [ast.literal_eval(n.args[1]) for n in ast.walk(m)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "advance"]
                for m in cls.body if isinstance(m, ast.FunctionDef) and m.name != "chapters"}
    assert targets(SOURCE) == targets(ROOT / "examples/wave_formation_visual.py")


@pytest.fixture(scope="module")
def preflight():
    if not PLAN.exists() or not (SESSION / "check.py").exists():
        pytest.skip("Live frozen speech/session inputs are deliberately not Git fixtures")
    spec = importlib.util.spec_from_file_location("formation_author_check", SESSION / "check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = json.loads(PLAN.read_text())
    module.provenance()
    module.preservation()
    scene = module.dry_scene(plan)
    focus = {"duration": scene.now, "windows": scene.windows}
    rows = module.schedule(scene.timeline, module.read(module.ROW["draft"]), focus, module.read(module.ROW["timings"]))
    return module, plan, scene, {r["id"]: r for r in rows}


def word_interval(unit, quote):
    characters = [(c, w) for p in unit["phrases"] for w in p["words"] for c in w["word"].strip()]
    text = "".join(c for c, _ in characters)
    start = text.index(quote)
    words = [w for _, w in characters[start:start + len(quote)]]
    return unit["start"] + words[0]["start"], unit["start"] + words[-1]["end"]


def test_every_reference_and_intact_wav_is_schedulable(preflight):
    module, plan, scene, units = preflight
    assert scene.now == plan["duration"] == sum(scene.durations) == 159
    assert len(units) == 5
    assert sum(len(u["phrases"]) for u in units.values()) == 13
    assert sum(u["duration_seconds"] for u in units.values()) == pytest.approx(127.84)
    assert all(u["legal_start"][0] - 1e-9 <= u["start"] <= u["legal_start"][1] + 1e-9 for u in units.values())
    assert all(r["feasible"] for r in module.diagnostic(scene.timeline, {"windows": scene.windows}))
    assert all(screen == pytest.approx(physical) and rate == "linear" for screen, physical, rate in scene.physics_intervals)


def test_delay_records_full_two_seconds_then_removes_before_spoken_removal(preflight):
    _, _, scene, units = preflight
    events = {r["id"]: r["time"] for r in scene.events}
    unit = units["F03"]
    advance = [r for r in scene.advances if r["physical_to"] in (7.9, 8.5)]
    assert advance[0]["start"] >= unit["phrases"][0]["visual_end"]
    assert advance[-1]["end"] - advance[0]["start"] == pytest.approx(2)
    assert events["delay_height_arrived"] <= word_interval(unit, "四米处也到了这个高度")[0]
    assert events["later_state_matches"] <= word_interval(unit, "到了这个高度")[0]
    assert events["delay_records_removed"] <= word_interval(unit, "去掉留下的圈")[0]
    continued = next(r for r in scene.advances if r["physical_to"] == 10.5)
    begin, end = word_interval(unit, "继续让时间走")
    assert continued["start"] < end and continued["end"] > begin
    assert "y(4\\,\\mathrm m,8.5\\,\\mathrm s)=y(2\\,\\mathrm m,6.5\\,\\mathrm s)" not in scene.focus_start_labels["delayed_not_transported"]


def test_full_cycle_and_original_crest_trace_precede_result_claims(preflight):
    _, _, scene, units = preflight
    events = {r["id"]: r["time"] for r in scene.events}
    begin, end = word_interval(units["F04"], "再回到起点")
    assert begin <= events["period_finished"] <= end
    assert events["period_half"] < events["period_finished"]
    assert events["period_result_ready"] < word_interval(units["F04"], "走了四米")[0]
    assert events["contrast_after"] < word_interval(units["F01"], "回到起点时")[0]
    cycle = [r for r in scene.advances if 100 < r["start"] < 108]
    assert sum(r["physical_to"] - r["physical_from"] for r in cycle) == pytest.approx(4)


def test_prediction_and_both_graph_exits_are_distinct_and_early_enough(preflight):
    _, _, scene, units = preflight
    unit = units["F05"]
    events = {r["id"]: r["time"] for r in scene.events}
    assert events["formation_answer_ready"] < word_interval(unit, "回到平衡位置")[0]
    assert events["formation_space_question_ready"] < word_interval(unit, "同一时刻各处的位移")[0]
    assert events["formation_space_question_ready"] < events["formation_closed"]
    assert events["formation_closed"] < word_interval(unit, "同一个点的位移怎样随时间变")[0]


def test_sources_bind_real_eager_imports_but_not_sibling_new_cases(preflight):
    _, plan, _, _ = preflight
    watched = set(plan["sources"]) | {plan["scene"]}
    assert plan["workflow_profile"].endswith("v4.2-unit.json")
    assert plan["author_agent"] == plan["author_context"]
    for name in tuple(watched):
        if not name.startswith("examples/") or not name.endswith(".py"):
            continue
        for node in ast.walk(ast.parse((ROOT / name).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            if isinstance(node, ast.Import):
                modules += [alias.name for alias in node.names]
            for module in modules:
                if module.startswith("wave_"):
                    assert f"examples/{module}.py" in watched
    assert "examples/wave_reading_audio_aligned.py" not in watched
    assert "examples/wave_superposition_audio_aligned.py" not in watched
