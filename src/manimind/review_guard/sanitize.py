"""Strip prior judgments from reviewer-visible inputs and verify packets.

Problem: ``first-look-packet-v013.json`` declared that prior judgments are
excluded, yet bound the attempt directory whose ``plan.json`` carried
``repair_request`` (old review path, finding text and decision),
``correction_scope`` and ``revision_review``.  A first-look reviewer opening
the attempt therefore saw the previous verdict.

* :func:`sanitize_plan` returns a reviewer-visible copy without those fields.
* :func:`scan_packet` walks every JSON file reachable from a packet (string
  values that name existing files; attempt directories contribute their
  top-level JSON files) and reports leaks: forbidden keys, or reachable files
  that are themselves review reports / author observations.
* :func:`sanitize_packet` writes a sanitized plan and a rebound packet that
  references it instead of the raw attempt directory, then validates it.

Writer: author/coordinator preparing a review packet.  Consumers: the fresh
first-look reviewer and the coordinator's dispatch check.  Lifecycle: one
bound attempt.  Invalidation: any change to the source plan or packet inputs
(the receipt pins their SHA-256).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]

# Keys whose *name* marks prior judgments, repair history or regression
# context.  Matching is on the key alone, at any nesting depth.  Workflow rule
# keys such as ``review_checks`` or ``independent_review_required`` describe
# how to review, not what a previous reviewer decided, so judgment words are
# matched as the key's last word (optionally followed by ``_sha256``) only.
FORBIDDEN_KEY_PATTERNS = (
    # Repair / correction history written for the author: repair_request,
    # correction_scope.  Bare ``repair`` (pedagogical misconception repair in
    # scientific briefs) is not history and stays.
    re.compile(r"^(repair|repairs|correction|corrections)_"),
    # Regression context (baseline contract and comparison review).
    re.compile(r"^revision_(review|reviews|contract)(_sha256)?$"),
    # prior_decision, old_decisions, original_visual_review, blocking_findings,
    # visual_review_sha256, prior_rejection_overridden ...
    re.compile(r"_(review|reviews|decision|decisions|verdict|verdicts|rejection|rejections"
               r"|judgment|judgments|opinions|conclusions)(_sha256)?$"),
    re.compile(r"(^|_)(finding|findings)(_sha256)?$"),
    re.compile(r"^(prior|previous|old|original)_(review|decision|verdict|rejection|judgment|report|opinion|conclusion)"),
    # Author self-observations and withdrawals.
    re.compile(r"(^|_)(observations|withdrawal|withdrawn|selfcheck|self_check)$"),
)
# Neutral scheduling/instruction keys that match a pattern above.
ALLOWED_KEYS = frozenset({
    "review_times", "transition_review_times", "substage_review_times",
    "review_requirements", "report_target",
})
# Subtrees made of hashes only (no readable judgment text); their keys are not
# judged by name, e.g. ``bindings.baseline_media_sha256``.
HASH_ONLY_KEYS = frozenset({"bindings"})
# Keys whose values point to where a report will be written, not to inputs.
NON_INPUT_KEYS = frozenset({"report_target"})
# A reachable JSON file carrying these keys is a review report.
REPORT_MARKERS = ("reviewer_agent", "reviewer_context", "blocking_findings")
ATTEMPT_JSON_LIMIT = 4 * 1024 * 1024


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8").lstrip("﻿"))


def forbidden_key(key):
    if not isinstance(key, str) or key in ALLOWED_KEYS:
        return False
    lowered = key.lower()
    return any(pattern.search(lowered) for pattern in FORBIDDEN_KEY_PATTERNS)


def find_forbidden_keys(value, prefix=""):
    """Return dotted paths of forbidden keys anywhere inside ``value``."""
    hits = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if forbidden_key(key):
                hits.append(path)
                continue
            if key in HASH_ONLY_KEYS and isinstance(item, dict):
                continue
            hits.extend(find_forbidden_keys(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(find_forbidden_keys(item, f"{prefix}[{index}]"))
    return hits


def _strip(value, prefix, removed):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if forbidden_key(key):
                removed.append(path)
            elif key in HASH_ONLY_KEYS and isinstance(item, dict):
                result[key] = item
            else:
                result[key] = _strip(item, path, removed)
        return result
    if isinstance(value, list):
        return [_strip(item, f"{prefix}[{index}]", removed) for index, item in enumerate(value)]
    return value


def sanitize_plan(plan):
    """Return ``(reviewer_visible_copy, removed_dotted_paths)``; input is untouched."""
    if not isinstance(plan, dict):
        raise ValueError("A plan must be a JSON object")
    removed = []
    clean = _strip(plan, "", removed)
    if find_forbidden_keys(clean):
        raise AssertionError("sanitize_plan left forbidden keys")
    return clean, removed


def _strings(value, skip_keys=NON_INPUT_KEYS):
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in skip_keys:
                yield from _strings(item, skip_keys)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, skip_keys)
    elif isinstance(value, str):
        yield value


def _resolve(text, bases):
    if not text or len(text) > 4096 or "\n" in text or not ("/" in text or text.endswith(".json")):
        return None
    candidate = Path(text)
    options = [candidate] if candidate.is_absolute() else [base / candidate for base in bases]
    for option in options:
        try:
            if option.exists():
                return option.resolve()
        except OSError:
            continue
    return None


def _report_like(value):
    return isinstance(value, dict) and any(key in value for key in REPORT_MARKERS)


def scan_packet(packet, *, root=ROOT, max_depth=2, forbid_paths=()):
    """Walk JSON reachable from ``packet`` (a path or dict) and list leaks.

    Each leak is ``{"file", "kind", "detail", "hops"}``.  ``hops`` is 0 for the
    packet itself, 1 for files the packet names directly (including the JSON
    files inside a directory it names, e.g. ``attempt/plan.json``) and 2 for
    files named by those.  Hop-2 leaks are usually produced by frozen tools
    (an evidence index pointing back to the attempt) and are reported for the
    coordinator; :func:`blocking_leaks` decides what rejects the packet.
    """
    root = Path(root).resolve()
    leaks, seen = [], set()
    forbid = {Path(p).resolve() for p in forbid_paths}
    if isinstance(packet, (str, os.PathLike)):
        packet_path = Path(packet).resolve()
        packet_value = read_json(packet_path)
        bases = [packet_path.parent, root]
        seen.add(packet_path)
        label = str(packet_path)
    else:
        packet_value, bases, label = packet, [root], "<packet>"
    for hit in find_forbidden_keys(packet_value):
        leaks.append({"file": label, "kind": "forbidden_key", "detail": hit, "hops": 0})

    queue = [(packet_value, bases, 0, label)]
    while queue:
        value, here, depth, origin = queue.pop(0)
        if depth >= max_depth:
            continue
        hops = depth + 1
        for text in _strings(value):
            path = _resolve(text, here)
            if path is None or path in seen:
                continue
            seen.add(path)
            if path in forbid:
                leaks.append({"file": str(path), "kind": "forbidden_path", "detail": f"referenced from {origin}", "hops": hops})
            if path.is_dir():
                children = [p.resolve() for p in sorted(path.glob("*.json")) if p.is_file()]
                children = [p for p in children if p not in seen]
                for child in children:
                    seen.add(child)
                    if child in forbid:
                        leaks.append({"file": str(child), "kind": "forbidden_path", "detail": f"inside {path}", "hops": hops})
            elif path.suffix.lower() == ".json":
                children = [path]
            else:
                continue
            for child in children:
                if child.stat().st_size > ATTEMPT_JSON_LIMIT:
                    continue
                try:
                    data = read_json(child)
                except (ValueError, UnicodeDecodeError):
                    continue
                if _report_like(data):
                    leaks.append({"file": str(child), "kind": "review_report", "hops": hops,
                                  "detail": f"reachable from {origin}; status={data.get('status')!r}"})
                for hit in find_forbidden_keys(data):
                    leaks.append({"file": str(child), "kind": "forbidden_key", "detail": hit, "hops": hops})
                queue.append((data, [child.parent, root], hops, str(child)))
    return leaks


def blocking_leaks(leaks, *, strict=False):
    """Leaks that reject a first-look packet: everything when ``strict``,
    otherwise the packet itself, its direct references and explicit forbids."""
    return [row for row in leaks if strict or row["hops"] <= 1 or row["kind"] == "forbidden_path"]


def require_clean_packet(packet, *, strict=False, **kwargs):
    leaks = blocking_leaks(scan_packet(packet, **kwargs), strict=strict)
    if leaks:
        lines = "; ".join(f"{row['kind']}:{row['detail']} @ {row['file']}" for row in leaks[:12])
        raise ValueError(f"First-look packet exposes prior judgments ({len(leaks)}): {lines}")
    return packet


def _fresh(path):
    path = Path(path).absolute()
    if os.path.lexists(path):
        raise FileExistsError(path)
    return path


def _dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def leaky_file(path):
    """Return why a JSON file exposes prior judgments, else ``None``."""
    path = Path(path)
    if path.is_dir():
        reasons = [f"{child.name}: {why}" for child in sorted(path.glob("*.json"))
                   if child.is_file() and (why := leaky_file(child))]
        return "; ".join(reasons) or None
    if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > ATTEMPT_JSON_LIMIT:
        return None
    try:
        data = read_json(path)
    except (ValueError, UnicodeDecodeError):
        return None
    if _report_like(data):
        return "review report"
    hits = find_forbidden_keys(data)
    return f"forbidden keys {hits[:4]}" if hits else None


def redact_references(value, bases, withheld, prefix=""):
    """Replace string references to leaky JSON files/dirs with a placeholder."""
    if isinstance(value, dict):
        return {k: (v if k in HASH_ONLY_KEYS | NON_INPUT_KEYS else redact_references(v, bases, withheld, f"{prefix}.{k}" if prefix else k))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact_references(v, bases, withheld, f"{prefix}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, str):
        path = _resolve(value, bases)
        if path is not None and (why := leaky_file(path)):
            withheld.append({"key": prefix, "reference": value, "reason": why})
            return f"[withheld: prior-judgment reference] {path.name}"
    return value


def write_sanitized_plan(plan_path, target, *, root=ROOT):
    """Write a reviewer-visible plan copy plus a receipt next to it.

    Forbidden keys are removed; remaining string references to JSON files
    that themselves carry prior judgments (old plans with ``repair_request``,
    review reports) are replaced by a placeholder and listed in the receipt.
    """
    plan_path, target = Path(plan_path).resolve(), _fresh(target)
    receipt_path = _fresh(target.with_name(target.stem + ".receipt.json"))
    source_sha = sha(plan_path)
    clean, removed = sanitize_plan(read_json(plan_path))
    withheld = []
    clean = redact_references(clean, [plan_path.parent, Path(root).resolve()], withheld)
    _dump(target, clean)
    receipt = {
        "source_plan": str(plan_path), "source_plan_sha256": source_sha,
        "sanitized_plan": str(target.resolve()), "sanitized_plan_sha256": sha(target),
        "removed_keys": removed, "withheld_references": withheld,
        "writer": "manimind.review_guard.sanitize", "consumers": ["fresh first-look reviewer", "coordinator dispatch check"],
        "lifecycle": "Only this source plan revision",
        "invalidation": "Any byte change of the source plan; the sanitized copy is never a publisher input",
    }
    _dump(receipt_path, receipt)
    if sha(plan_path) != source_sha:
        raise ValueError("Source plan changed while sanitizing")
    return receipt


def sanitize_packet(packet_path, out_dir, *, root=ROOT, forbid_paths=(), strict=False):
    """Write ``reviewer-plan.json`` and a rebound packet into ``out_dir``.

    The rebound packet drops the raw ``attempt`` directory reference (its
    ``plan.json`` holds repair history) and points to the sanitized plan; it
    keeps hash-only ``bindings`` so the reviewer can still bind the report.
    Provenance (source packet/plan paths) lives only in receipts that the
    rebound packet does not reference.
    """
    packet_path, out_dir = Path(packet_path).resolve(), Path(out_dir).absolute()
    packet = read_json(packet_path)
    attempt = packet.get("attempt")
    if not isinstance(attempt, str) or not (Path(attempt) / "plan.json").is_file():
        raise ValueError("Packet must name an attempt directory with plan.json")
    attempt = Path(attempt).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_receipt = write_sanitized_plan(attempt / "plan.json", out_dir / "reviewer-plan.json", root=root)
    if packet.get("bindings", {}).get("plan_sha256") not in (None, plan_receipt["source_plan_sha256"]):
        raise ValueError("Packet bindings belong to another plan revision")
    rebound, removed = sanitize_plan({k: v for k, v in packet.items() if k != "attempt"})
    withheld = []
    rebound = redact_references(rebound, [packet_path.parent, Path(root).resolve()], withheld)
    rebound.update(
        reviewer_plan=plan_receipt["sanitized_plan"], reviewer_plan_sha256=plan_receipt["sanitized_plan_sha256"],
        attempt_withheld="Raw attempt directory withheld: its plan.json holds repair history; "
                         "use reviewer_plan, current_video and the listed frames",
    )
    target = _fresh(out_dir / packet_path.name)
    packet_receipt_path = _fresh(target.with_name(target.stem + ".receipt.json"))
    _dump(target, rebound)
    leaks = scan_packet(target, root=root, forbid_paths=forbid_paths)
    blocking = blocking_leaks(leaks, strict=strict)
    receipt = {
        "source_packet": str(packet_path), "source_packet_sha256": sha(packet_path),
        "sanitized_packet": str(target), "sanitized_packet_sha256": sha(target),
        "removed_packet_keys": removed, "withheld_packet_references": withheld,
        "plan_receipt": plan_receipt, "clean": not blocking, "strict": strict,
        "blocking_leaks": blocking, "indirect_leaks": [row for row in leaks if row not in blocking],
        "writer": "manimind.review_guard.sanitize", "consumers": ["coordinator dispatch check"],
        "lifecycle": "Only this source packet and plan revision",
        "invalidation": "Any byte change of the source packet, plan or reachable inputs",
    }
    _dump(packet_receipt_path, receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m manimind.review_guard.sanitize")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("plan", help="write a reviewer-visible plan copy")
    one.add_argument("plan")
    one.add_argument("target")
    one.add_argument("--root", default=str(ROOT))
    two = sub.add_parser("packet", help="write sanitized plan + rebound packet and validate")
    two.add_argument("packet")
    two.add_argument("out_dir")
    three = sub.add_parser("check", help="reject a packet whose reachable files expose prior judgments")
    three.add_argument("packet")
    three.add_argument("--max-depth", type=int, default=2)
    for command in (two, three):
        command.add_argument("--root", default=str(ROOT))
        command.add_argument("--forbid", action="append", default=[], help="explicit prior-review path")
        command.add_argument("--strict", action="store_true", help="indirect (hop-2) leaks also reject")
    args = parser.parse_args(argv)
    if args.command == "plan":
        result, code = write_sanitized_plan(args.plan, args.target, root=args.root), 0
    elif args.command == "packet":
        result = sanitize_packet(args.packet, args.out_dir, root=args.root, forbid_paths=args.forbid, strict=args.strict)
        code = 0 if result["clean"] else 1
    else:
        leaks = scan_packet(args.packet, root=args.root, max_depth=args.max_depth, forbid_paths=args.forbid)
        blocking = blocking_leaks(leaks, strict=args.strict)
        result = {"packet": str(Path(args.packet).resolve()), "clean": not blocking, "strict": args.strict,
                  "blocking_leaks": blocking, "indirect_leaks": [row for row in leaks if row not in blocking]}
        code = 0 if not blocking else 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
