"""First-look and regression gates as separate entry points, plus merge.

``unit_film.require_review`` (frozen) calls ``require_regression`` for the
visual stage, so a perfectly valid blind first look is reported as blocked
while the regression review has not been written yet.  This conflates two
independent reviews: the first-look reviewer must not see the baseline, and
the regression reviewer must.  The gates here keep them apart:

* :func:`first_look_gate` -- current independent visual review only;
* :func:`regression_gate` -- ``not_required`` for fresh lessons, ``blocked``
  while the regression report is missing, otherwise the frozen
  ``unit_film.require_regression`` check;
* :func:`merge_gate` -- both must pass (or regression not required) and the
  two reviewers must share neither agent nor context.

The frozen functions are reused through :class:`UnitFilmBackend`; nothing in
``manimind.postproduce`` is modified.  Release still goes through the frozen
publishers, which keep their own combined check.

Gate results are plain dicts ``{"gate", "status", "reason", ...}`` with
status in ``pass`` / ``fail`` / ``blocked`` / ``not_required``.  They are
returned, not written; a coordinator that stores one must bind it to the
attempt and the report SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from . import identity

GATE_STATUSES = ("pass", "fail", "blocked", "not_required")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8").lstrip("﻿"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class UnitFilmBackend:
    """Adapter over the frozen ``unit_film`` checks (imported lazily)."""

    def __init__(self):
        from manimind.postproduce import unit_film
        from manimind.review import content_regression, understanding_quality
        self.unit_film, self.regression, self.quality = unit_film, content_regression, understanding_quality
        self.root = unit_film.pilot.ROOT

    def plan(self, attempt):
        return _read(Path(attempt) / "plan.json")

    def bindings(self, attempt):
        return self.unit_film.bindings(attempt)

    def authors(self, attempt):
        return [self.unit_film._identity(self.plan(attempt), "author")]

    def review(self, report, stage, current, authors):
        return self.unit_film._review(report, stage, current, authors=authors)

    def editorial(self, report, attempt, stage):
        duration = _read(Path(attempt) / "timeline.json")["duration"]
        return self.quality.validate_editorial_review(report, duration=duration, stage=stage)

    def regression_required(self, attempt):
        profile = _read(Path(attempt) / "workflow-profile.json")
        return self.regression.revision_required(self.plan(attempt), profile_version=profile["version"])

    def regression_report_path(self, attempt):
        return (Path(self.root) / self.plan(attempt)["revision_review"]).resolve()

    def require_regression(self, attempt):
        return self.unit_film.require_regression(attempt)


def _result(gate, status, reason="", **extra):
    assert status in GATE_STATUSES
    return {"gate": gate, "status": status, "reason": reason, **extra}


def _assignment(backend, attempt, version):
    return backend.plan(attempt).get("project_id"), version or Path(attempt).resolve().name


def first_look_gate(attempt, report_path, *, backend=None, registry=None, version=None):
    """Check the blind first look alone; never consults the regression review."""
    backend = backend or UnitFilmBackend()
    report_path = Path(report_path)
    if not report_path.is_file():
        return _result("first_look", "blocked", f"First-look report missing: {report_path}")
    report = _read(report_path)
    info = {"report": str(report_path.resolve()), "report_sha256": _sha(report_path),
            "reviewer_agent": report.get("reviewer_agent"), "reviewer_context": report.get("reviewer_context")}
    try:
        backend.review(report, "visual", backend.bindings(attempt), backend.authors(attempt))
        backend.editorial(report, attempt, "visual")
        if registry is not None:
            lesson, label = _assignment(backend, attempt, version)
            identity.check(identity.load(registry), report["reviewer_agent"], report["reviewer_context"],
                           lesson, label, "visual")
    except (ValueError, KeyError, TypeError) as error:
        return _result("first_look", "fail", str(error), **info)
    return _result("first_look", "pass", **info)


def regression_gate(attempt, *, backend=None, registry=None, version=None):
    """Check the content regression alone; independent of the first look."""
    backend = backend or UnitFilmBackend()
    try:
        if not backend.regression_required(attempt):
            return _result("regression", "not_required", "Fresh lesson: no baseline comparison")
        path = backend.regression_report_path(attempt)
    except (ValueError, KeyError, TypeError) as error:
        return _result("regression", "fail", str(error))
    if not Path(path).is_file():
        return _result("regression", "blocked", f"Regression report not written yet: {path}")
    report = _read(path)
    info = {"report": str(path), "report_sha256": _sha(path),
            "reviewer_agent": report.get("reviewer_agent"), "reviewer_context": report.get("reviewer_context")}
    try:
        backend.require_regression(attempt)
        if registry is not None:
            lesson, label = _assignment(backend, attempt, version)
            identity.check(identity.load(registry), report["reviewer_agent"], report["reviewer_context"],
                           lesson, label, "content_regression")
    except (ValueError, KeyError, TypeError) as error:
        return _result("regression", "fail", str(error), **info)
    return _result("regression", "pass", **info)


def merge_gate(attempt, first_look_report, *, backend=None, registry=None, version=None):
    """Merge-stage combination: both gates acceptable and reviewers disjoint."""
    backend = backend or UnitFilmBackend()
    first = first_look_gate(attempt, first_look_report, backend=backend, registry=registry, version=version)
    second = regression_gate(attempt, backend=backend, registry=registry, version=version)
    parts = {"first_look": first, "regression": second}
    failed = [g for g in (first, second) if g["status"] == "fail"]
    pending = [g for g in (first, second) if g["status"] == "blocked"]
    if failed:
        return _result("merge", "fail", "; ".join(f"{g['gate']}: {g['reason']}" for g in failed), parts=parts)
    if pending:
        return _result("merge", "blocked", "; ".join(f"{g['gate']}: {g['reason']}" for g in pending), parts=parts)
    if second["status"] == "pass":
        ids_first = {first["reviewer_agent"], first["reviewer_context"]}
        ids_second = {second["reviewer_agent"], second["reviewer_context"]}
        if ids_first & ids_second:
            return _result("merge", "fail", "Blind first look and regression require different reviewer "
                                            f"agents and contexts; shared {sorted(ids_first & ids_second)}", parts=parts)
    return _result("merge", "pass", parts=parts)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m manimind.review_guard.gates")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("first-look")
    one.add_argument("attempt")
    one.add_argument("report")
    two = sub.add_parser("regression")
    two.add_argument("attempt")
    three = sub.add_parser("merge")
    three.add_argument("attempt")
    three.add_argument("report", help="first-look report")
    for command in (one, two, three):
        command.add_argument("--registry")
        command.add_argument("--version", help="version label for the registry (default: attempt dir name)")
    args = parser.parse_args(argv)
    if args.command == "first-look":
        result = first_look_gate(args.attempt, args.report, registry=args.registry, version=args.version)
    elif args.command == "regression":
        result = regression_gate(args.attempt, registry=args.registry, version=args.version)
    else:
        result = merge_gate(args.attempt, args.report, registry=args.registry, version=args.version)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["status"] in ("pass", "not_required") else 1


if __name__ == "__main__":
    raise SystemExit(main())
