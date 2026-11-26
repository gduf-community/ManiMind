"""Reviewer identity registry: one reviewer context per lesson/version/stage.

``unit_film._review`` only prevents authors from reviewing their own work and
a narration reviewer reusing the visual reviewer's context.  It cannot see
that the same reviewer context already looked at lesson 03, or at the v011
candidate of the same lesson, so a "fresh" first look could carry prior
exposure.  This registry records every assignment and refuses reuse.

Rules (agent id and context id are checked independently, so relabeling one
of them cannot create a fresh identity):

* the first registration of an identity binds it to ``(lesson, version, stage)``;
* registering the same identity again for exactly that assignment is idempotent;
* any other lesson, any other version of the same lesson (older or newer) or
  any other stage is rejected.

State record: ``review-identities.json`` (path chosen by the coordinator,
normally ``runtime/sessions/<session_id>/review-identities.json``).
Writer: coordinator dispatching reviewers.  Consumers: dispatch, gates in
:mod:`.gates`.  Lifecycle: the whole review session; entries are append-only.
Invalidation: never rewritten; a wrong entry is superseded by a new session
file, not edited.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile

SCHEMA = "review-identities-v1"
# Stage names used by unit_film._review callers.
STAGES = ("visual", "narration", "content_regression", "audio_alignment", "captions")


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Require explicit {name}; never infer a reviewer identity")
    return value


def _empty():
    return {"schema": SCHEMA, "entries": [],
            "writer": "manimind.review_guard.identity", "consumers": ["reviewer dispatch", "review_guard gates"],
            "lifecycle": "This review session; append-only",
            "invalidation": "Never rewritten; start a new registry file instead of editing entries"}


@contextmanager
def _locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def load(path):
    path = Path(path)
    if not path.exists():
        return _empty()
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != SCHEMA or not isinstance(value.get("entries"), list):
        raise ValueError("Unknown reviewer identity registry")
    return value


def _assignment(lesson, version, stage):
    if stage not in STAGES:
        raise ValueError(f"Unknown review stage {stage!r}")
    return {"lesson": _text(lesson, "lesson"), "version": _text(version, "version"), "stage": stage}


def conflicts(registry, reviewer_agent, reviewer_context, lesson, version, stage):
    """Entries that make this assignment a reuse (empty list = allowed)."""
    _text(reviewer_agent, "reviewer_agent")
    _text(reviewer_context, "reviewer_context")
    wanted = _assignment(lesson, version, stage)
    found = []
    for entry in registry["entries"]:
        same_identity = (entry["reviewer_agent"] in (reviewer_agent, reviewer_context)
                         or entry["reviewer_context"] in (reviewer_agent, reviewer_context))
        if same_identity and {k: entry[k] for k in wanted} != wanted:
            found.append(entry)
    return found


def check(registry, reviewer_agent, reviewer_context, lesson, version, stage):
    found = conflicts(registry, reviewer_agent, reviewer_context, lesson, version, stage)
    if found:
        prior = ", ".join(f"{e['lesson']}@{e['version']}/{e['stage']}" for e in found[:4])
        raise ValueError(
            f"Reviewer {reviewer_agent}/{reviewer_context} already reviewed {prior}; "
            f"one review context per lesson/version/stage, dispatch a fresh reviewer for "
            f"{lesson}@{version}/{stage}")
    return True


def register(path, reviewer_agent, reviewer_context, lesson, version, stage, *, note=None):
    """Record the assignment or raise if the identity was used elsewhere."""
    path = Path(path)
    with _locked(path):
        registry = load(path)
        check(registry, reviewer_agent, reviewer_context, lesson, version, stage)
        wanted = _assignment(lesson, version, stage)
        for entry in registry["entries"]:
            if (entry["reviewer_agent"], entry["reviewer_context"]) == (reviewer_agent, reviewer_context) and \
                    {k: entry[k] for k in wanted} == wanted:
                return entry
        entry = {"reviewer_agent": reviewer_agent, "reviewer_context": reviewer_context, **wanted,
                 "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if note:
            entry["note"] = str(note)
        registry["entries"].append(entry)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(registry, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp, path)
        except BaseException:
            if os.path.exists(temp):
                os.unlink(temp)
            raise
        return entry


def assignment_for_report(report, plan, *, version):
    """Derive ``(agent, context, lesson, version, stage)`` from a report and plan."""
    return (report.get("reviewer_agent"), report.get("reviewer_context"),
            plan.get("project_id"), version, report.get("stage"))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m manimind.review_guard.identity")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "register"):
        cmd = sub.add_parser(name)
        cmd.add_argument("registry")
        cmd.add_argument("--agent", required=True)
        cmd.add_argument("--context", required=True)
        cmd.add_argument("--lesson", required=True, help="project_id of the lesson")
        cmd.add_argument("--version", required=True, help="attempt/version label, e.g. visual-v013")
        cmd.add_argument("--stage", required=True, choices=STAGES)
        cmd.add_argument("--note")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            check(load(args.registry), args.agent, args.context, args.lesson, args.version, args.stage)
            result = {"allowed": True}
        else:
            result = {"allowed": True, "entry": register(args.registry, args.agent, args.context, args.lesson,
                                                         args.version, args.stage, note=args.note)}
        code = 0
    except ValueError as error:
        result, code = {"allowed": False, "error": str(error)}, 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
