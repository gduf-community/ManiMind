# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ManiMind is a multi-agent orchestration layer for math explainer animation production. Input: papers + notes. Output: scripts, storyboards, Manim math animations, HTML explainer snippets, and structured assets for voiceover/subtitle/editing stages.

The repo is the **orchestration layer** only — it does NOT re-implement rendering engines (Manim, HyperFrames, HTML animation). External rendering capabilities live under `resources/skills/` and `resources/references/`.

## Build & test commands

```bash
# Install core + API + dev deps
pip install -e ".[api,dev]"

# Run all tests (testpaths = tests, pythonpath = src)
pytest

# Run a single test file
pytest tests/test_workflow.py

# Run the FastAPI server
uvicorn backend.main:app --reload

# CLI entry point
python -m manimind <command>
```

PowerShell scripts (Windows-only initialization):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-workspace.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-prerequisites.ps1
```

## Architecture: 9-stage pipeline

`prestart → ingest → summarize → plan → dispatch → review → post_produce → package → done`

**Stages driven by task status**, not explicit stage transitions. `runtime.py:derive_current_stage()` infers the current stage from which `ExecutionTask` has `IN_PROGRESS` / `COMPLETED`.

## Agent roles & modes

Defined in `workflow.py:build_agent_profiles()`. Each role has an `AgentMode`:

| Role | Mode | Responsibility |
|------|------|----------------|
| `lead` | structured_write | Global state, stage transitions, asset manifest |
| `explorer` | read_only | Search papers/code/assets for patterns |
| `planner` | read_only | Constraint analysis, storyboard suggestions |
| `coordinator` | structured_write | Narration script, storyboard, task dispatch |
| `html_worker` | structured_write | HTML explainer snippets |
| `manim_worker` | structured_write | Manim math animation snippets |
| `svg_worker` | structured_write | SVG motion snippets |
| `reviewer` | verify_only | Evidence-based review, gate before post-produce |

**Reviewer is a hard gate**: no task past `review` can start until `review.outputs` is `COMPLETED`.

## Context system: long-term vs short-term

- **Long-term** (`runtime/projects/<project_id>/`): Project-lifecycle records — research summary, glossary, formula catalog, style guide, narration script, storyboard, review report. `sticky=True` records are auto-included for all roles.
- **Short-term** (`runtime/sessions/<session_id>/`): Per-session handoff and coordination. Session-scoped, invalidated on session end.

Every `ContextRecord` declares: writer, consumers, lifecycle, invalidation rule. `context_assembly.py:build_context_packet()` assembles a role+stage-specific context packet by intersecting the role's mode defaults, required inputs, and the role's consumer permissions.

## Core modules (`src/manimind/`)

- **`models.py`**: All dataclasses and enums. Pure data — no behavior beyond `to_dict()`.
- **`workflow.py`**: Builds the full `ProjectPlan` from a manifest. Contains the context blueprint, worker task generation (driven by `SegmentModality`), agent profiles, execution task DAG, and review checkpoints.
- **`task_board.py`**: Execution task state machine. Enforces owner-only writes, blocker resolution before advancing. Returns `verification_nudge_needed=True` when all pre-review tasks are done but review hasn't started.
- **`runtime.py`**: Loads persisted snapshots, applies them to an in-memory `ProjectPlan`, derives current stage.
- **`runtime_store.py`**: Persistence layer. Atomic writes (write-to-tmp then `os.replace`), JSONL audit logs for every mutation. Writes to both project-level and session-level directories.
- **`context_assembly.py`**: Context packet builder + prompt section cache (avoids rebuilding identical prompt segments).
- **`bootstrap.py`**: Workspace directory creation, toolchain detection (`python`, `node`, `bun`, `ffmpeg`, `manim`), runtime layout path generation.

## Backend API (`backend/`)

Thin FastAPI wrapper over `src/manimind/`. Routes:
- `POST /api/projects/plan` — create project plan from manifest
- `GET /api/projects/{project_id}/runtime` — read runtime snapshot
- `POST /api/projects/tasks` — list execution tasks
- `POST /api/projects/tasks/update` — advance task status
- `POST /api/projects/context-pack` — generate role+stage context packet

## Manifest format

See `configs/pipeline.example.json`. A manifest defines `project_id`, `title`, `source_bundle` (paper_path, note_paths, audience, style_refs), and `segments` (each with id, title, goal, narration, modality, formulas, etc.).

## Key invariants

- Never merge long-term and short-term context into the same file or path.
- Never skip the reviewer gate — no post-processing before review passes.
- No implicit global state for multi-agent coordination.
- All persisted state must go through atomic writes in `runtime_store.py`.
- This repo is orchestration only — don't re-implement rendering logic from `resources/`.
- Structural changes to module boundaries, roles, state paths, or context assembly must update `docs/architecture.canvas` and `docs/通用项目架构模板.md`.
