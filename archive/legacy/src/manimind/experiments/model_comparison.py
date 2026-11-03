"""Prepare identical, answer-free review packets and reuse bounded experiments.

No candidate answer is a delivery approval. Independent ground truth and
adjudication live beside the manifest but are never included in API requests.
"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

from . import model_benchmark as bench, model_dialogue as dialogue
from ..postproduce import pilot
from ..scene_spec import experiment

CONFIG = bench.ROOT / "configs/model-comparison.json"
PURPOSE = {
    "task": "Blind review of sampled frames from a continuous mathematics lesson excerpt",
    "threshold": "Identify factual/semantic blockers separately from pedagogical advisories; not full-course approval",
    "is_delivery_approval": False,
}
INSTRUCTION = """审核同一短镜头按时间排序的原始帧及对应场景数据。不要推测作者或模型身份。
独立检查数学、标题语义、图文一致性、读数、视觉焦点和可读性。区分过程预告和当前读数，结合时间轴判断。
按连续课程辅助短镜头的门槛评估，不要求这一片段独立讲完整节课。不要预设一定有错误，也不要预设一定正确。
仅凭提供的帧不能证明连续运动、音频或整段视频质量。不可将建议项夸大成数学错误。
只返回JSON，字段case_id, verdict(blocked/acceptable_with_advisories/insufficient_evidence),
findings数组(每项severity=blocker/advisory, claim, evidence, frame_numbers, correction), limitations数组。
evidence要指出实际文字/数值/位置与计算依据；没有证据时明确不确定。总共最多8条发现，避免重复，保持简洁。
"""


def check_components(baseline):
    report_path = bench.ROOT / "outputs" / baseline / "report.json"
    report = pilot.read_json(report_path)
    for name, path in experiment.COMPONENTS.items():
        if any(run["hashes"][name] != pilot.sha256(path) for run in report["runs"]):
            raise ValueError(f"Baseline component changed: {name}")
    return report_path


def build_packet(case, directory):
    spec = pilot.read_json(directory / "scene-spec.json")
    clock = pilot.read_json(directory / "timeline.json")
    cues = [{key: cue[key] for key in ("id", "start", "duration", "subtitle_lines")}
            for cue in clock["cues"]]
    return {"instruction": INSTRUCTION, "case_id": case["id"], "scene_spec": spec,
            "timeline": {"duration": clock["duration"], "fps": clock["fps"], "cues": cues},
            "frames": [{"number": i + 1, "seconds": t} for i, t in enumerate(case["times"])]}


def prepare(config=CONFIG):
    settings = pilot.read_json(config)
    out, context, _ = bench.paths(settings["id"])
    if (context / "comparison.json").exists() or out.exists():
        raise ValueError("Comparison already exists; never overwrite evidence")
    check_components(settings["baseline_suite"])
    baseline_path = bench.ROOT / "runtime/projects" / settings["baseline_suite"] / "suite.json"
    baseline = pilot.read_json(baseline_path)
    if baseline["system"] != experiment.SYSTEM or baseline["contract"] != experiment.CONTRACT:
        raise ValueError("Baseline generation prompt/contract changed")
    generation = deepcopy(baseline["settings"])
    generation["profile"] = settings["generation_profile"]
    sources, files, cases = {}, {}, []
    sources[str(baseline_path)] = pilot.sha256(baseline_path)
    out.mkdir(parents=True)
    generation_path = context / "generation-config.json"
    pilot.write_json(generation_path, generation)
    files[str(generation_path)] = pilot.sha256(generation_path)
    purpose_path = out / "purpose.json"
    pilot.write_json(purpose_path, PURPOSE)
    files[str(purpose_path)] = pilot.sha256(purpose_path)
    for case in settings["cases"]:
        directory = bench.ROOT / "outputs" / settings["baseline_suite"] / case["run"] / case["render"]
        packet = build_packet(case, directory)
        case_out = out / case["id"]
        case_out.mkdir()
        brief = case_out / "brief.json"
        pilot.write_json(brief, packet)
        files[str(brief)] = pilot.sha256(brief)
        for name in ("scene-spec.json", "timeline.json"):
            sources[str(directory / name)] = pilot.sha256(directory / name)
        images = []
        for i, timestamp in enumerate(case["times"]):
            candidates = [p for p in (directory / "frames").glob("frame_*.jpg")
                          if float(p.stem.removeprefix("frame_").replace("_", ".")) == timestamp]
            if len(candidates) != 1:
                raise ValueError(f"Missing or ambiguous original frame: {case['id']} at {timestamp}")
            source = candidates[0]
            target = case_out / f"frame-{i + 1:02d}.jpg"
            shutil.copy2(source, target)
            sources[str(source)] = pilot.sha256(source)
            files[str(target)] = pilot.sha256(target)
            images.append(str(target))
        cases.append({"id": case["id"], "brief": str(brief), "images": images})
    pilot.write_json(context / "comparison.json", {
        "scope": "long_term", "writer_role": "coordinator", "consumer_roles": ["evaluator", "reviewer", "lead"],
        "lifecycle": "This bounded model comparison", "invalidation_rule": "Changed packet/source/provider/protocol requires a new comparison",
        "settings": settings, "source_hashes": sources, "file_hashes": files, "cases": cases,
        "purpose_path": str(purpose_path), "generation_config": str(generation_path),
        "review_profiles": {alias: pilot.read_json(bench.SETTINGS)["profiles"][name]
                            for alias, name in settings["review_profiles"].items()},
        "dialogue_system_sha256": pilot.sha256(Path(dialogue.__file__)),
        "comparison_source_sha256": pilot.sha256(Path(__file__)),
        "limitations": ["Four related samples, not population reviewer accuracy", "No audio or continuous video input",
                        "Historical generation baseline, not concurrent randomization", "Rolling API aliases; gateway identity is not attested"],
    })
    print(json.dumps({"status": "prepared", "cases": len(cases), "api_requests": 0, "context": str(context)}))


def load(comparison):
    _, context, _ = bench.paths(comparison)
    record = pilot.read_json(context / "comparison.json")
    for path, digest in {**record["source_hashes"], **record["file_hashes"]}.items():
        if pilot.sha256(Path(path)) != digest:
            raise ValueError("Changed comparison evidence")
    if (pilot.sha256(Path(dialogue.__file__)) != record["dialogue_system_sha256"]
            or pilot.sha256(Path(__file__)) != record["comparison_source_sha256"]):
        raise ValueError("Changed comparison protocol")
    return record


def init_generation(comparison):
    record = load(comparison)
    check_components(record["settings"]["baseline_suite"])
    name = record["settings"]["generation_profile"]
    if pilot.read_json(bench.SETTINGS)["profiles"][name] != record["review_profiles"]["deepseek"]:
        raise ValueError("Generation provider changed after freeze")
    suite = record["settings"]["generation_suite"]
    with bench.exclusive_run(suite):
        experiment.init(suite, Path(record["generation_config"]))
    print(json.dumps({"status": "initialized", "suite": suite}))


def review(comparison, provider):
    from ..llm.client import LlmClient  # Load provider-specific credentials.

    record = load(comparison)
    settings = record["settings"]
    name = settings["review_profiles"][provider]
    current = pilot.read_json(bench.SETTINGS)
    if current["profiles"][name] != record["review_profiles"][provider]:
        raise ValueError("Review provider changed after freeze")
    bench.resolve_profile(name, current, os.environ)
    results = []
    for case in record["cases"]:
        case_id = bench.validate_id(f"{comparison}-{provider}-{case['id']}")
        _, context, session = bench.paths(case_id)
        with bench.exclusive_run(case_id):
            if (session / "dialogue.json").exists():
                results.append({"case": case["id"], "status": "already_attempted"})
                continue
            if not (context / "collaboration.json").exists():
                dialogue.init(case_id, name, Path(record["purpose_path"]), max_requests=1)
            frozen = pilot.read_json(context / "collaboration.json")
            if frozen["profile"] != record["review_profiles"][provider] or frozen["purpose"] != PURPOSE or frozen["max_requests"] != 1:
                raise ValueError("Changed candidate case")
            try:
                dialogue.ask(case_id, Path(case["brief"]), [Path(p) for p in case["images"]],
                             max_tokens=settings["max_review_output_tokens"])
                results.append({"case": case["id"], "status": "completed"})
            except Exception as exc:
                results.append({"case": case["id"], "status": "failed", "error_type": type(exc).__name__})
                calls = pilot.read_json(session / "dialogue.json")["turns"][-1].get("calls", [])
                if any(call.get("status_code") in {401, 402, 403, 429} for call in calls):
                    break
    print(json.dumps({"provider": provider, "results": results, "is_delivery_approval": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "init-generation", "review"])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--comparison", default="ds-mimo-review-20261018")
    parser.add_argument("--provider", choices=["deepseek", "mimo"])
    args = parser.parse_args()
    identifier = pilot.read_json(args.config)["id"] if args.action == "prepare" else args.comparison
    with bench.exclusive_run(identifier):
        if args.action == "prepare":
            prepare(args.config)
        elif args.action == "init-generation":
            init_generation(args.comparison)
        else:
            if not args.provider:
                parser.error("review requires --provider")
            review(args.comparison, args.provider)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "detail": str(exc) if isinstance(exc, ValueError) else "See retained evidence"}))
        raise SystemExit(1) from None
