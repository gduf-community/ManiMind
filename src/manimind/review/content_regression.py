"""Task-selected content continuity, separate from blind editorial quality.

Contracts are project-long baseline inventories. Independent comparison reports
are session-scoped observations, bound to current media and the inventory.
No fixed topic, shot count, duration or layout is protected. Source/media or
contract changes invalidate approval. Evidence structure is not pixel truth or
authenticated reviewer identity; an independent reviewer must inspect it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .semantic_focus import finite, safe_id


GUIDANCE = """
先保留有效解释，再减少同屏负担。记录基线中推理、变量连续性、单位、条件及
图形-公式联系的功能；按当前任务选择保留项，不把旧片的布局、对象数或时长
当通用模板。新增内容不得悄悄替换旧片已经有效的部分。独立首看后，另行比较
新旧真实画面；逐项报告retained/equivalent/lost。功能等价须说明理由，过程要
检查before/during/after而非只给终态。总分、可播放、片长或留白不抵消内容丢失。
"""


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def revision_required(plan, *, profile_version=None):
    mode = plan.get("revision_mode")
    if (profile_version == "understanding-first-v3" or plan.get("workflow_profile", "").endswith("visual-first-workflow-v3.json")) and mode not in {"fresh", "revision"}:
        raise ValueError("Declare fresh or revision for the revision-aware workflow")
    if mode is not None and mode not in {"fresh", "revision"}:
        raise ValueError("Unknown revision mode")
    requested = mode == "revision" or "revision_contract" in plan or "revision_review" in plan
    if mode == "fresh" and requested:
        raise ValueError("A fresh project cannot silently attach a revision baseline")
    if requested and (not isinstance(plan.get("revision_contract"), str) or not plan["revision_contract"].strip()
                      or not isinstance(plan.get("revision_review"), str) or not plan["revision_review"].strip()):
        raise ValueError("Revision needs both a baseline contract and comparison review path")
    return requested


def validate_contract(value):
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unknown content regression contract schema")
    assets, units = value.get("assets"), value.get("units")
    if not isinstance(assets, dict) or not assets or not isinstance(units, list) or not units:
        raise ValueError("Task-selected baseline assets and content units are required")
    for name, asset in assets.items():
        if (not safe_id(name) or not isinstance(asset.get("path"), str) or not asset["path"].strip()
                or not isinstance(asset.get("sha256"), str) or len(asset["sha256"]) != 64
                or not finite(asset.get("duration")) or asset["duration"] <= 0):
            raise ValueError("Every baseline needs a path, fingerprint and measured duration")
    seen = set()
    for row in units:
        if (not safe_id(row.get("id")) or row["id"] in seen or row.get("asset") not in assets
                or not isinstance(row.get("function"), str) or not row["function"].strip()):
            raise ValueError("Unique content units must identify a baseline and teaching function")
        seen.add(row["id"])
        interval = row.get("baseline_interval")
        if (not isinstance(interval, list) or len(interval) != 2 or not all(finite(t) for t in interval)
                or not 0 <= interval[0] < interval[1] <= assets[row["asset"]]["duration"]):
            raise ValueError("Baseline evidence must be an in-range nonempty interval")
        features, ids = row.get("features"), set()
        if not isinstance(features, list) or not features:
            raise ValueError("Identify the meaningful details to compare")
        for feature in features:
            if (not safe_id(feature.get("id")) or feature["id"] in ids or feature.get("kind") not in {"state", "process"}
                    or not isinstance(feature.get("claim"), str) or not feature["claim"].strip()):
                raise ValueError("Every unique detail needs a function claim and state/process kind")
            ids.add(feature["id"])
    return value


def contract_bindings(path, root):
    path, root = Path(path), Path(root)
    value = validate_contract(json.loads(path.read_text(encoding="utf-8")))
    hashes = {}
    for identity, asset in value["assets"].items():
        actual = sha(root / asset["path"])
        if actual != asset["sha256"]:
            raise ValueError("The selected baseline media changed")
        hashes[identity] = actual
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return value, {"revision_contract_sha256": sha(path), "baseline_media_sha256": digest,
                   "regression_validator_sha256": sha(__file__)}


def validate_comparison(value, contract, current_bindings, duration):
    validate_contract(contract)
    if (value.get("stage") != "content_regression" or value.get("reviewer_role") != "independent"
            or not isinstance(value.get("reviewer_agent"), str) or not value["reviewer_agent"].strip()
            or value.get("bindings") != current_bindings or value.get("status") not in {"pass", "revise"}
            or type(value.get("release_authorized")) is not bool or not isinstance(value.get("blocking_findings"), list)):
        raise ValueError("Require a current independent content comparison with explicit release decision")
    rows = value.get("units")
    expected = {row["id"]: row for row in contract["units"]}
    if (not isinstance(rows, list) or len(rows) != len(expected)
            or {row.get("id") for row in rows} != set(expected)):
        raise ValueError("Compare every task-selected unit, not only the successful ones")
    losses = []
    for row in rows:
        features = {feature["id"]: feature for feature in expected[row["id"]]["features"]}
        details = row.get("features")
        if (not isinstance(details, list) or len(details) != len(features)
                or {detail.get("id") for detail in details} != set(features)):
            raise ValueError("Every meaningful baseline detail needs an explicit comparison")
        for detail in details:
            outcome = detail.get("outcome")
            if outcome not in {"retained", "equivalent", "lost"}:
                raise ValueError("Use retained, functionally equivalent or lost, never silent omission")
            if outcome == "lost":
                losses.append(f"{row['id']}.{detail['id']}")
                continue
            if outcome == "equivalent" and (not isinstance(detail.get("rationale"), str) or not detail["rationale"].strip()):
                raise ValueError("An equivalent replacement needs an explicit functional rationale")
            evidence = detail.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("Retention needs current pixels, not an author's intention or source alone")
            for item in evidence:
                if (not finite(item.get("time")) or not 0 <= item["time"] < duration
                        or not isinstance(item.get("finding"), str) or not item["finding"].strip()):
                    raise ValueError("Cite actual current in-range pixel observations")
            if features[detail["id"]]["kind"] == "process":
                phases = {item.get("phase"): item["time"] for item in evidence}
                if (not {"before", "during", "after"} <= set(phases)
                        or not phases["before"] < phases["during"] < phases["after"]):
                    raise ValueError("A process cannot be certified by a terminal still; inspect before/during/after")
    if value["status"] == "pass" and (losses or value["blocking_findings"] or not value["release_authorized"]):
        raise ValueError("An editorial score cannot compensate for losing selected effective content")
    if value["status"] == "revise" and value["release_authorized"]:
        raise ValueError("A failed comparison cannot authorize release")
    return value
