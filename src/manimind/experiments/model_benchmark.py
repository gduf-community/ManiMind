"""Measure model-written ManimGL scenes against a fixed, narrated lesson.

No model can approve its own video. Generation, execution, inspection and
delivery are separate commands, with immutable attempt directories.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import time
import wave
from urllib.parse import urlsplit

from ..bootstrap import repo_root
from ..postproduce.pilot import read_json, write_json, sha256, probe, run, validate_review, FFMPEG
from ..render import render_manim_scene, extract_keyframes

ROOT = repo_root()
SETTINGS = ROOT / "configs/model-benchmark.json"
SUPPORT = ROOT / "src/manimind/experiments/scene_support.py"
GUARDED_SUPPORT = ROOT / "src/manimind/experiments/guarded_scene.py"
LAYOUT_GUARD = ROOT / "src/manimind/experiments/layout_guard.py"
SPEC = ROOT / "configs/velocity-pilot.json"
CONFIG = ROOT / "configs/velocity-pilot-manimgl.yml"
BASELINE = ROOT / "outputs/velocity-pilot"

SYSTEM = """你负责高中数学知识演示视频的 ManimGL 代码实现。只输出完整 Python 源码。
这是严格的同题评测：分镜、数学事实、配音和时间轴已冻结，不要读取或模仿既有样片源码。
你要独立设计所选分镜的布局、动态几何和公式过渡。禁止网络、文件操作、shell、音频操作。
只允许 import manimlib、numpy、math 和下述 scene_support；不写 __main__。
必须 class GeneratedLesson(BenchmarkScene)，只实现 construct 和视觉辅助方法，不覆盖 setup/tear_down/cue/beat。
可导入：from manimind.experiments.scene_support import BenchmarkScene, cn, formula, INK, CYAN, YELLOW, CORAL, GREEN, MUTED, BACKGROUND
cn(text,size=28,color=INK) 返回中文透明图片 ImageMobject；formula(tex,size=38,color=INK)返回正确设置模板和颜色的Tex。
含cn的组必须用 Group，不能用 VGroup；中文文字用cn，不用Tex或Text。公式用formula。
基类提供字幕、标题、固定时钟：依次用 with self.cue(index, '本镜头短标题'):，index 从0到本次 timeline.cues 的长度减1。
块内用 self.beat(0.3, FadeIn(obj))、self.beat(0.75, tracker.animate.set_value(...)) 等安排动画；fraction是当前句时长比例且单调递增。
beat不接受run_time。DecimalNumber可以set_value，但Tex不能。需要移动的辅助线用Line，避免对DashedLine修改端点。
退出with时自动等待到整句结束；不要直接self.play/self.wait，更不能整体变速。每句需要至少一个解释性视觉变化。
基类不提供图形或教学答案，只负责排字和时钟。不要self.clear()，只删除你自己持有的视觉对象。
16:9画布 x=[-7.11,7.11],y=[-4,4]，顶部y>2.8标题，底部y<-2.8字幕；教学内容严格限制x=[-6.3,6.3],y=[-2.5,2.5]。
图与解释分区，关键数据字号>=28；内容最多一到两个视觉焦点；不堆满公式，不用缩得很小来规避重叠。
ManimGL 1.7.2，不是CE：from manimlib import *；ShowCreation，不用Create；Axes.get_graph，不用plot。
Axes(x_range=(0,3.3,1),y_range=(0,44,8),width=...,height=...,axis_config={'include_tip':False,'include_numbers':False})；点坐标用axes.c2p。
需要刻度数字时手动formula生成，避免依赖未知axes接口。动态数用DecimalNumber配updater，不要每帧重建Tex/中文贴图。
Dot必须显式fill_color=color；不要把带动态数字的组放入FadeIn/Transform，让数字先add再启动updater。
所有updater在删除对象前clear_updaters；不要闭包捕获随后会重绑定的变量。
全片保持t/时间差用CYAN，s/位置用YELLOW，速度/斜率用CORAL，切线用GREEN。
只完成本次spec.cues和timeline中的镜头；facts是数学背景，不要求将所有事实塞入片段。
割线镜头必须让动点沿曲线、辅助线、割线和读数由同一ValueTracker同步驱动，不要先后移动。
若包含zoom镜头，必须真实改变数学窗口，不能假放大。只有包含result/recap时才需要最终换算/极限定义。
短片段保持一套连续图形，开场清楚标出模型和固定点；不要切成多页课件。不依赖外部图片素材。
"""


def validate_id(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", value):
        raise ValueError("run-id must contain only lowercase letters, digits and hyphens")
    return value


def paths(run_id: str):
    run_id = validate_id(run_id)
    return (ROOT / "outputs" / run_id, ROOT / "runtime/projects" / run_id,
            ROOT / "runtime/sessions" / f"{run_id}-generation")


def resolve_profile(name: str, settings: dict, environ: dict) -> tuple[dict, str]:
    profile = dict(settings["profiles"][name])
    base = profile.get("base_url") or environ.get(profile.get("base_url_env", ""), "")
    key = environ.get(profile["api_key_env"], "")
    parsed = urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query:
        raise ValueError("Set an explicit, credential-free model base URL")
    allowed = profile.get("allowed_hosts")
    if allowed and parsed.hostname not in allowed:
        raise ValueError("Profile/key destination mismatch; no request was sent")
    if allowed and parsed.scheme != "https":
        raise ValueError("Cloud API requires HTTPS")
    if not key:
        raise ValueError(f"Missing {profile['api_key_env']}; never borrow another provider's key")
    profile.update(base_url=base, model=environ.get(profile.get("model_env", "")) or profile["model"])
    return profile, key


def extract_code(reply: str) -> str:
    text = reply.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[-1].strip() != "```" or lines[0].strip() not in {"```", "```python", "```py"}:
            raise ValueError("Expected one complete Python code block")
        text = "\n".join(lines[1:-1])
    ast.parse(text)
    return text + "\n"


def preflight_code(code: str) -> list[str]:
    """Conservative lint, not a security sandbox. Manual review is still needed."""
    issues = []
    tree = ast.parse(code)
    cue_contexts = {id(item.context_expr) for node in ast.walk(tree) if isinstance(node, ast.With) for item in node.items}
    defined_methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    allowed = {"manimlib", "numpy", "math", "manimind.experiments.scene_support", "manimind.experiments.guarded_scene"}
    forbidden = {"open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "globals", "locals", "vars", "input", "breakpoint"}
    if not any(isinstance(n, ast.ClassDef) and n.name == "GeneratedLesson" for n in tree.body):
        issues.append("Expected class GeneratedLesson")
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            fractions = [call.args[0].value for statement in node.body for call in ast.walk(statement)
                         if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                         and isinstance(call.func.value, ast.Name) and call.func.value.id == "self"
                         and call.func.attr == "beat" and call.args and isinstance(call.args[0], ast.Constant)
                         and type(call.args[0].value) in {int, float}]
            if any(not 0 <= value <= 1 for value in fractions) or fractions != sorted(fractions):
                issues.append("Literal beat fractions must be monotonic in [0,1]")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"FadeIn", "FadeOut"} and len(node.args) > 1):
            issues.append("FadeIn/FadeOut accept one object; pass shift by keyword and separate animations")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"):
            if node.func.attr == "cue" and id(node) not in cue_contexts:
                issues.append("self.cue must be entered with a with block")
            if node.func.attr == "add_updater_to" and "add_updater_to" not in defined_methods:
                issues.append("Unknown Scene.add_updater_to; use mobject.add_updater")
            if node.func.attr == "beat" and any(kw.arg == "run_time" for kw in node.keywords):
                issues.append("self.beat does not accept run_time")
        if isinstance(node, ast.Import) and any(n.name not in allowed for n in node.names):
            issues.append("Import outside the render contract")
        if isinstance(node, ast.ImportFrom) and (node.module not in allowed or node.level):
            issues.append("Import outside the render contract")
        if isinstance(node, ast.Name) and node.id in forbidden:
            issues.append(f"Forbidden name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            issues.append("Dunder attribute access")
        if isinstance(node, ast.FunctionDef) and node.name in {"setup", "tear_down", "cue", "beat", "get_time_progression", "register_labels"}:
            issues.append(f"Must not override clock/support method: {node.name}")
    return sorted(set(issues))


def cost_summary(records: list[dict], pricing: dict | None) -> dict:
    complete = bool(records) and all(isinstance(r.get("prompt_tokens"), int) and isinstance(r.get("completion_tokens"), int) for r in records)
    known_input = sum(r.get("prompt_tokens") or 0 for r in records)
    known_output = sum(r.get("completion_tokens") or 0 for r in records)
    known_estimate = None
    if pricing and any(r.get("prompt_tokens") is not None or r.get("completion_tokens") is not None for r in records):
        known_estimate = (known_input * pricing["input_per_million"] + known_output * pricing["output_per_million"]) / 1_000_000
    estimate = known_estimate if complete else None
    return {"requests": len(records), "usage_complete": complete, "known_input_tokens": known_input,
            "known_output_tokens": known_output, "estimated_model_cost": estimate, "estimated_known_usage_cost": known_estimate,
            "pricing": pricing, "excludes": ["reviewer", "rendering", "TTS", "human work", "server depreciation and electricity"]}


def attempt_records(attempts: list[dict]) -> list[dict]:
    # A process may stop after sending a request but before recording its usage.
    return [call for attempt in attempts for call in (attempt.get("calls") or [{}])]


def validate_inputs(entry: dict, out: Path, context: Path) -> None:
    if entry.get("design_brief_sha256"):
        for name, path in [("design_brief", out / "design-brief.json"), ("guarded_support", GUARDED_SUPPORT), ("layout_guard", LAYOUT_GUARD)]:
            if sha256(path) != entry[f"{name}_sha256"]:
                raise ValueError(f"Changed benchmark input: {name}")
    for name, path in [("support", SUPPORT), ("timeline", out / "timeline.json"),
                       ("audio", out / "narration.wav"), ("config", out / "manimgl.yml"),
                       ("prompt", Path(entry["prompt_path"]))]:
        if sha256(path) != entry[f"{name}_sha256"]:
            raise ValueError(f"Changed benchmark input: {name}")
    if "experiment_sha256" in entry and sha256(context / "experiment.json") != entry["experiment_sha256"]:
        raise ValueError("Changed benchmark input: experiment")
    if entry.get("repair_authorization_path"):
        if sha256(Path(entry["repair_authorization_path"])) != entry["repair_authorization_sha256"]:
            raise ValueError("Changed benchmark input: repair authorization")
    if entry["status"] == "generated":
        source = Path(entry["code_path"])
        if not source.is_file() or sha256(source) != entry["code_sha256"]:
            raise ValueError("Missing or manually modified model source")
        reply = Path(entry["prompt_path"]).with_name(f"reply-{entry['index']:02d}.txt")
        if extract_code(reply.read_text(encoding="utf-8")) != source.read_text(encoding="utf-8"):
            raise ValueError("Source does not match original model response")


@contextmanager
def exclusive_run(run_id: str):
    """Serialize CLI commands; a crashed owner's lock requires manual inspection."""
    _, _, session = paths(run_id)
    session.mkdir(parents=True, exist_ok=True)
    lock = session / "command.lock"
    with lock.open("x", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "run_id": run_id}, handle)
    try:
        yield
    finally:
        lock.unlink()


def check_budget(attempts: list[dict], settings: dict) -> None:
    # A confirmed 429 rejection is not a generated answer; timeouts still count
    # because the provider may have generated and billed an unknown response.
    generations = sum(not (a.get("calls") and all(c.get("status_code") == 429 for c in a["calls"])) for a in attempts)
    if len(attempts) >= settings["max_requests"] or generations >= settings["max_generations"]:
        raise ValueError("Generation/request limit reached; retain all failures")


def repair_budget(authorization: Path, run_id: str, attempts: list[dict], limits: dict,
                  record_file: Path, context: Path, feedback: Path, output_budget: int) -> dict:
    """Audit one explicit user-authorized request; not an authentication service."""
    if authorization.resolve().parent != record_file.resolve().parent:
        raise ValueError("Repair authorization must be in this run's session")
    if not attempts:
        raise ValueError("Extra repair requires an existing exhausted run")
    try:
        check_budget(attempts, limits)
    except ValueError:
        pass
    else:
        raise ValueError("Extra repair requires an exhausted run")
    approval = read_json(authorization)
    expected = {"run_id": run_id, "next_attempt": len(attempts) + 1,
                "authorized_by": "user", "additional_requests": 1,
                "previous_attempts_sha256": sha256(record_file),
                "experiment_sha256": sha256(context / "experiment.json"),
                "feedback_sha256": sha256(feedback)}
    maximum = approval.get("max_output_tokens")
    if (any(approval.get(k) != v for k, v in expected.items())
            or type(approval.get("additional_requests")) is not int
            or type(maximum) is not int or not output_budget <= maximum <= 65536
            or not isinstance(approval.get("user_instruction"), str) or not approval["user_instruction"].strip()):
        raise ValueError("Missing, stale or mismatched one-request repair authorization")
    return {"max_generations": len(attempts) + 1, "max_requests": len(attempts) + 1}


def select_excerpt(spec: dict, timeline: dict, cue_ids: list[str]) -> tuple[dict, dict, dict]:
    """Select contiguous source cues and rebase their clock without changing speech."""
    ids = [cue["id"] for cue in timeline["cues"]]
    if not cue_ids or len(set(cue_ids)) != len(cue_ids) or any(c not in ids for c in cue_ids):
        raise ValueError("Select unique, known cue IDs")
    indices = [ids.index(c) for c in cue_ids]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError("Excerpt cues must be contiguous and in original order")
    fps = timeline["fps"]
    cues = deepcopy(timeline["cues"][indices[0]:indices[-1] + 1])
    start_frame = round(cues[0]["start"] * fps)
    end_frame = round((cues[-1]["start"] + cues[-1]["duration"]) * fps)
    for cue in cues:
        cue["start"] = (round(cue["start"] * fps) - start_frame) / fps
        cue["speech_start"] = cue["speech_start"] - start_frame / fps
        cue.pop("audio_path", None)
    selected = deepcopy(spec)
    by_id = {cue["id"]: cue for cue in selected["cues"]}
    selected["cues"] = [by_id[c] for c in cue_ids]
    selected["scope"] = "Continuous excerpt only; other lesson facts are context, not extra scenes"
    excerpt = {"cue_ids": list(cue_ids), "start_frame": start_frame, "end_frame": end_frame,
               "fps": fps, "baseline_duration": timeline["duration"]}
    clock = {**deepcopy(timeline), "duration": (end_frame - start_frame) / fps, "cues": cues, "excerpt": excerpt}
    return selected, clock, excerpt


def slice_narration(source: Path, target: Path, excerpt: dict) -> None:
    """Lossless PCM slice at the same frame boundaries as the selected cues."""
    with wave.open(str(source), "rb") as reader:
        params = reader.getparams()
        first = round(excerpt["start_frame"] / excerpt["fps"] * params.framerate)
        last = round(excerpt["end_frame"] / excerpt["fps"] * params.framerate)
        if not 0 <= first < last <= params.nframes:
            raise ValueError("Excerpt is outside baseline narration")
        reader.setpos(first)
        data = reader.readframes(last - first)
    with wave.open(str(target), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(data)


def generate(profile_name: str, run_id: str, feedback: Path | None = None, *, max_output_tokens: int | None = None,
             cue_ids: list[str] | None = None, repair_authorization: Path | None = None,
             design_brief: Path | None = None) -> None:
    from ..llm.client import LlmClient

    settings = read_json(SETTINGS)
    output_budget = settings["max_output_tokens"] if max_output_tokens is None else max_output_tokens
    if isinstance(output_budget, bool) or not isinstance(output_budget, int) or not 1 <= output_budget <= 65536:
        raise ValueError("max_output_tokens must be an integer in [1, 65536]")
    profile, key = resolve_profile(profile_name, settings, os.environ)
    out, context, session = paths(run_id)
    record_file = session / "attempts.json"
    attempts = read_json(record_file)["attempts"] if record_file.exists() else []
    limits = settings
    if attempts:
        frozen = read_json(context / "experiment.json")
        if design_brief is not None and read_json(design_brief) != frozen.get("design_brief"):
            raise ValueError("Design brief changed: create a separate run-id")
        limits = {"max_generations": frozen["max_generations"], "max_requests": frozen.get("max_requests", 3)}
    if repair_authorization is not None:
        if feedback is None:
            raise ValueError("Authorized extra repair requires feedback")
        limits = repair_budget(repair_authorization, run_id, attempts, limits, record_file, context, feedback, output_budget)
    check_budget(attempts, limits)
    if bool(attempts) != bool(feedback):
        raise ValueError("First attempt has no feedback; retry requires explicit feedback")
    if attempts and read_json(context / "experiment.json")["profile"] != profile:
        raise ValueError("Model/profile changed: create a separate run-id")
    if attempts and cue_ids is not None:
        if (read_json(context / "experiment.json").get("excerpt") or {}).get("cue_ids") != cue_ids:
            raise ValueError("Cue selection changed: create a separate run-id")
    if attempts:
        for previous_entry in attempts:
            validate_inputs(previous_entry, out, context)
    elif out.exists() or context.exists():
        raise ValueError("Run directory already exists without an attempt ledger; use a new run-id")
    if not attempts:
        design = read_json(design_brief) if design_brief is not None else None
        if design is not None:
            contract = design.get("layout_contract", {})
            if (not contract.get("required_labels") or contract.get("bounds") != [-6.3, 6.3, -2.5, 2.5]
                    or not isinstance(contract["required_labels"], list)
                    or not all(isinstance(n, str) and n for n in contract["required_labels"])):
                raise ValueError("Design brief requires a nonempty label contract and teaching bounds")
        timeline = read_json(BASELINE / "timeline.json")
        if timeline["spec_sha256"] != sha256(SPEC):
            raise ValueError("Baseline narration is stale")
        spec, excerpt = read_json(SPEC), None
        if cue_ids is not None:
            spec, timeline, excerpt = select_excerpt(spec, timeline, cue_ids)
            excerpt.update(baseline_timeline_sha256=sha256(BASELINE / "timeline.json"),
                           baseline_audio_sha256=sha256(BASELINE / "audio/narration.wav"))
        out.mkdir(parents=True, exist_ok=True)
        if excerpt:
            timeline["project_id"] = run_id
            write_json(out / "timeline.json", timeline)
            slice_narration(BASELINE / "audio/narration.wav", out / "narration.wav", excerpt)
        else:
            shutil.copy2(BASELINE / "timeline.json", out / "timeline.json")
            shutil.copy2(BASELINE / "audio/narration.wav", out / "narration.wav")
        shutil.copy2(CONFIG, out / "manimgl.yml")
        if design is not None:
            write_json(out / "design-brief.json", design)
        write_json(context / "experiment.json", {
            "scope": "long_term", "writer_role": "coordinator", "consumer_roles": ["manim_worker", "reviewer", "lead"],
            "lifecycle": "experiment", "invalidation_rule": "Any input/hash or model change requires a new review or new run",
            "profile": profile, "spec": spec, "baseline": str(BASELINE), "excerpt": excerpt,
            "design_brief": design,
            "boundary": "Fixed expert script and narration; model generates all subject visuals, not end-to-end curriculum planning",
            "human_source_edits": 0, "source": "External API response only; fences may be removed",
            "max_generations": settings["max_generations"], "max_requests": settings["max_requests"]})
    snapshot = read_json(context / "experiment.json")
    system = SYSTEM
    user = json.dumps({"spec": snapshot["spec"], "timeline": read_json(out / "timeline.json")}, ensure_ascii=False, indent=2)
    if snapshot.get("design_brief") is not None:
        user += "\n共同讨论后冻结的设计规范：\n" + json.dumps(snapshot["design_brief"], ensure_ascii=False, indent=2)
        system += "\n本轮启用布局仪器：改为 from manimind.experiments.guarded_scene import GuardedBenchmarkScene，class GeneratedLesson(GuardedBenchmarkScene)。其余字形和颜色仍从scene_support导入。必须在第一个cue前调用self.register_labels({名称:实际Mobject,...})，包含layout_contract.required_labels全部名称及其他文字标签。每个beat末尾自动检查包围盒，禁止覆盖、篡改或绕过仪器。注册真实画面对象而不是替身；行内组用arrange(RIGHT,buff=...)保证间距，动态DecimalNumber每次set_value后重新排该行。注册的未来图例也预留位置。只给完整源码。\n"
    if feedback:
        previous = Path(attempts[-1]["code_path"])
        if previous.exists():
            user += "\n此前代码：\n" + previous.read_text()
        user += "\n审核/运行反馈（仅作诊断，不改变原约束）：\n" + feedback.read_text()
    index = len(attempts) + 1
    attempt_dir = out / f"attempt-{index:02d}"
    attempt_dir.mkdir(exist_ok=False)
    prompt_path = session / f"prompt-{index:02d}.json"
    write_json(prompt_path, {"system": system, "user": user})
    entry = {"index": index, "status": "requested", "max_output_tokens": output_budget,
             "prompt_path": str(prompt_path), "prompt_sha256": sha256(prompt_path),
             "experiment_sha256": sha256(context / "experiment.json"),
             "support_sha256": sha256(SUPPORT), "timeline_sha256": sha256(out / "timeline.json"),
             "audio_sha256": sha256(out / "narration.wav"), "config_sha256": sha256(out / "manimgl.yml"),
             "code_path": str(attempt_dir / "scene.py"), "feedback_path": str(feedback) if feedback else None}
    if snapshot.get("design_brief") is not None:
        entry.update(design_brief_sha256=sha256(out / "design-brief.json"),
                     guarded_support_sha256=sha256(GUARDED_SUPPORT), layout_guard_sha256=sha256(LAYOUT_GUARD))
    if repair_authorization is not None:
        entry.update(repair_authorization_path=str(repair_authorization.resolve()),
                     repair_authorization_sha256=sha256(repair_authorization), effective_request_limits=limits)
    attempts.append(entry)
    write_json(record_file, {"scope": "short_term", "writer_role": "manim_worker", "consumer_roles": ["reviewer", "lead"],
               "lifecycle": "this experimental run", "invalidation_rule": "Retain immutable attempts; never reuse across different inputs", "attempts": attempts})
    client = LlmClient(api_key=key, base_url=profile["base_url"], model=profile["model"], max_retries=1, timeout=profile.get("timeout", 600),
                       extra_body=profile["extra_body"], json_mode=False,
                       token_limit_param=profile.get("token_limit_param", "max_tokens"))
    try:
        reply = client.chat(system, user, temperature=profile["temperature"], max_tokens=output_budget)
        (session / f"reply-{index:02d}.txt").write_text(reply, encoding="utf-8")
        code = extract_code(reply)
        Path(entry["code_path"]).write_text(code, encoding="utf-8")
        entry.update(status="generated", code_sha256=sha256(Path(entry["code_path"])), preflight_issues=preflight_code(code))
    except Exception as exc:
        entry.update(status="generation_failed", error_type=type(exc).__name__)
        raise
    finally:
        entry["calls"] = client.drain_call_records()
        data = read_json(record_file)
        data["attempts"] = attempts
        write_json(record_file, data)
        summary = cost_summary(attempt_records(attempts), profile.get("pricing"))
        write_json(out / "cost.json", summary)
        print(json.dumps({"run_id": run_id, "attempt": index, "status": entry["status"], "cost": summary}, ensure_ascii=False), flush=True)


def latest(run_id: str):
    out, context, session = paths(run_id)
    entry = read_json(session / "attempts.json")["attempts"][-1]
    source = Path(entry["code_path"])
    if entry["status"] != "generated" or sha256(source) != entry["code_sha256"]:
        raise ValueError("Missing or manually modified model source")
    validate_inputs(entry, out, context)
    return out, context, session, entry, source


@contextmanager
def render_scope(out: Path, layout_report: Path | None = None):
    values = {"MANIMIND_BENCHMARK_DIR": str(out)}
    if layout_report is not None:
        values["MANIMIND_LAYOUT_REPORT"] = str(layout_report)
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, old in previous.items():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


def render(run_id: str, quality: str, execute: bool):
    if not execute:
        raise ValueError("Inspect source first, then explicitly pass --execute-reviewed-source; lint is not a sandbox")
    out, _, session, entry, source = latest(run_id)
    issues = preflight_code(source.read_text())
    if issues:
        raise ValueError(f"Blocked source: {issues}")
    started = time.monotonic()
    report_path = source.parent / "layout-checks.json" if entry.get("design_brief_sha256") else None
    if report_path and report_path.exists():
        raise ValueError("Existing instrumented render: keep evidence and use a fresh attempt")
    with render_scope(out, report_path):
        result = render_manim_scene(segment_id=f"lesson-{quality}", scene_code=source.read_text(), scene_class_name="GeneratedLesson",
                                    output_dir=source.parent, config_file=out / "manimgl.yml", quality=quality, timeout_seconds=1200)
    latest(run_id)
    if sha256(Path(result.code_path)) != entry["code_sha256"]:
        result.success = False
        result.error = "render_copy_source_mismatch"
    write_json(session / f"render-{entry['index']:02d}-{quality}.json", result.to_dict())
    data = {**result.to_dict(), "code_sha256": sha256(source), "render_seconds": time.monotonic() - started, "attempt": entry["index"]}
    write_json(source.parent / "render.json", data)
    print(json.dumps(data, ensure_ascii=False), flush=True)
    if not result.success:
        raise RuntimeError("Render failed; evidence saved, no delivery permitted")


def hashes(run_id: str, video: Path) -> dict:
    out, context, _, entry, source = latest(run_id)
    extra = ({"design_brief": sha256(out / "design-brief.json"), "guarded_support": sha256(GUARDED_SUPPORT),
              "layout_guard": sha256(LAYOUT_GUARD), "layout_report": sha256(source.parent / "layout-checks.json")}
             if entry.get("design_brief_sha256") else {})
    return {**extra, "source": sha256(source), "support": sha256(SUPPORT), "experiment": sha256(context / "experiment.json"),
            "timeline": sha256(out / "timeline.json"), "audio": sha256(out / "narration.wav"),
            "config": sha256(out / "manimgl.yml"), "prompt": entry["prompt_sha256"], "video": sha256(video)}


def requires_zoom(context: Path) -> bool:
    return any(c["id"] == "zoom" for c in read_json(context / "experiment.json")["spec"]["cues"])


def inspect(run_id: str):
    from PIL import Image, ImageDraw

    out, context, _, entry, source = latest(run_id)
    result = read_json(source.parent / "render.json")
    if not result["success"] or result["code_sha256"] != sha256(source):
        raise ValueError("Render failed or source changed")
    video = Path(result["video_path"])
    timeline = read_json(out / "timeline.json")
    metadata = probe(video)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    if abs(float(stream["duration"]) - timeline["duration"]) > 0.15:
        raise ValueError("Video/cue duration mismatch")
    samples = [(c["id"], round(c["start"] + c["duration"] * f, 3)) for c in timeline["cues"] for f in (0.18, 0.55, 0.88)]
    frames = extract_keyframes(video_path=video, output_dir=source.parent / "frames", timestamps=[t for _, t in samples], ffmpeg_executable=FFMPEG)
    if not frames.success or frames.missing_timestamps or len(frames.frame_paths) != len(samples):
        raise ValueError("Incomplete frame evidence")
    index, sheets = [], []
    for start in range(0, len(samples), 12):
        sheet = Image.new("RGB", (1600, 1008), "#202226")
        draw = ImageDraw.Draw(sheet)
        for offset, ((cue, timestamp), path) in enumerate(zip(samples[start:start+12], frames.frame_paths[start:start+12])):
            with Image.open(path) as frame:
                thumb = frame.copy()
                thumb.thumbnail((533, 225))
                x, y = offset % 3 * 533, offset // 3 * 252
                sheet.paste(thumb, (x, y+24))
                draw.text((x+6, y+5), f"{cue} / {timestamp:.2f}s", fill="white")
            index.append({"cue": cue, "time": timestamp, "path": path, "sha256": sha256(Path(path))})
        path = source.parent / "frames" / f"contact-{start//12+1:02d}.jpg"
        sheet.save(path, quality=92)
        sheets.append(str(path))
    write_json(out / "review-input.json", {"run_id": run_id, "attempt": entry["index"], "source_path": str(source),
               "hashes": hashes(run_id, video), "video_path": str(video), "timeline_path": str(out / "timeline.json"),
               "resolution": [stream["width"], stream["height"]], "duration": float(stream["duration"]),
               "frames": index, "contact_sheets": sheets, "requires_zoom": requires_zoom(context),
               "review_instruction": "Inspect source and pixels; rendering success is not educational quality. Check mathematics, visual_layout, narrative, cue_timing, and actual_zoom when required by the frozen selected cues. Identify limitations; never self-approve."})
    print(json.dumps({"run_id": run_id, "contact_sheets": sheets}, ensure_ascii=False), flush=True)


def assemble(run_id: str):
    out, context, _, entry, _ = latest(run_id)
    evidence = read_json(out / "review-input.json")
    if evidence.get("run_id") != run_id or evidence.get("attempt") != entry["index"]:
        raise ValueError("Review evidence belongs to another run or attempt")
    video = Path(evidence["video_path"])
    review = read_json(context / "review.json")
    if entry.get("design_brief_sha256"):
        from .layout_guard import validate_report

        validate_report(read_json(Path(entry["code_path"]).parent / "layout-checks.json"),
                        read_json(out / "design-brief.json")["layout_contract"], len(read_json(out / "timeline.json")["cues"]))
    validate_review(review, hashes(run_id, video), evidence["frames"], require_zoom=requires_zoom(context))
    target = out / f"{run_id}.mp4"
    run([FFMPEG, "-v", "error", "-y", "-i", video, "-i", out / "narration.wav", "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-18:TP=-1.5:LRA=7", "-movflags", "+faststart", target])
    streams = probe(target)["streams"]
    expected = read_json(out / "timeline.json")["duration"]
    if any(abs(float(s["duration"]) - expected) > 0.15 for s in streams if s["codec_type"] in {"audio", "video"}):
        raise ValueError("Final stream timing mismatch")
    run([FFMPEG, "-v", "error", "-i", target, "-f", "null", "-"], timeout=300)
    write_json(out / "delivery.json", {"video": str(target), "sha256": sha256(target), "review_sha256": sha256(context / "review.json"),
               "cost": read_json(out / "cost.json"), "limitations": ["Fixed expert script; not autonomous curriculum-to-video", "Single topic, no statistical pass rate", "Reviewer effort is not included in model cost"]})
    print(str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["generate", "render", "inspect", "assemble"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--profile", default="kimi-code")
    parser.add_argument("--feedback", type=Path)
    parser.add_argument("--design-brief", type=Path, help="Freeze a jointly designed JSON specification and enable label instrumentation")
    parser.add_argument("--repair-authorization", type=Path, help="Session-local record of explicit user authorization for exactly one extra request")
    parser.add_argument("--max-output-tokens", type=int, help="Explicit per-request budget override, at most 65536; recorded in the attempt ledger")
    parser.add_argument("--cues", nargs="+", help="Contiguous cue IDs for a short excerpt; retry reuses the frozen selection")
    parser.add_argument("--quality", choices=["l", "m", "h"], default="h")
    parser.add_argument("--execute-reviewed-source", action="store_true")
    args = parser.parse_args()
    with exclusive_run(args.run_id):
        if args.action == "generate":
            generate(args.profile, args.run_id, args.feedback, max_output_tokens=args.max_output_tokens,
                     cue_ids=args.cues, repair_authorization=args.repair_authorization, design_brief=args.design_brief)
        elif args.action == "render":
            render(args.run_id, args.quality, args.execute_reviewed_source)
        elif args.action == "inspect":
            inspect(args.run_id)
        else:
            assemble(args.run_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # SDK exception chains may contain provider account identifiers.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}, ensure_ascii=False))
        raise SystemExit(1) from None
