"""Assemble a HyperFrames project for a ManiMind seek(t) scene.

A scene directory holds ``scene.json`` and its scripts. ``assemble`` copies, into a new project
directory, the pinned browser libraries (KaTeX, GSAP from tools/hyperframes), this package's engine
(motion.js, engine.js, adapter.js, base.css) and the scene scripts, and writes index.html in the
HyperFrames composition format. The project is silent; ``resolve_audio`` returns the voice tracks
for voice.py. Rendering itself is HyperFrames' job (see render.py).

scene.json:
  id        film id (ASCII)               duration  seconds
  layers    [{"type": "canvas"|"fx", "id": str}, ...] bottom to top
  scripts   scene scripts, loaded in order after the engine; one defines window.createFilm()
  fonts     CSS font shorthands the film measures with, e.g. "40px KaTeX_Main"
  background  optional CSS colour         audio  optional [{"src", "start", "volume"}]

State: the assembled project is derived output, written by assemble() and read by HyperFrames;
it is valid only for the exact scene files and assets it was built from (hashes in the
returned manifest). Delete and rebuild instead of editing it.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import shutil

PACKAGE = Path(__file__).resolve().parent
ASSETS = PACKAGE / "assets"
REPO = PACKAGE.parents[2]
TOOLS = REPO / "tools/hyperframes"
ENGINE_FILES = ("motion.js", "engine.js", "adapter.js", "base.css")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_scene(scene_dir: Path) -> dict:
    scene = json.loads((scene_dir / "scene.json").read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", str(scene.get("id", ""))):
        raise ValueError("scene.json id must be lowercase ASCII letters, digits and hyphens")
    if not (isinstance(scene.get("duration"), (int, float)) and scene["duration"] > 0):
        raise ValueError("scene.json duration must be a positive number of seconds")
    layers = scene.get("layers") or []
    if not layers or any(l.get("type") not in ("canvas", "fx") or not re.fullmatch(r"[A-Za-z][\w-]*", l.get("id", ""))
                         for l in layers):
        raise ValueError("scene.json layers must be canvas/fx entries with simple ids")
    for name in scene.get("scripts", []):
        if Path(name).is_absolute() or ".." in Path(name).parts or not (scene_dir / name).is_file():
            raise ValueError(f"scene script missing or outside the scene directory: {name}")
    return scene


def _library_paths():
    katex = TOOLS / "node_modules/katex/dist"
    gsap = TOOLS / "node_modules/gsap/dist/gsap.min.js"
    if not katex.is_dir() or not gsap.is_file():
        raise FileNotFoundError("Pinned browser libraries missing: run `npm ci` in tools/hyperframes")
    return katex, gsap


def resolve_audio(scene: dict, override=None) -> list:
    """Voice tracks [{"source": Path, "start", "volume", "sha256"}] from scene.json or an override.

    Relative sources resolve against the repository root. The picture never carries these: HyperFrames
    renders silently and voice.py mixes them under the project's constant-gain rule.
    """
    tracks = []
    for item in override if override is not None else scene.get("audio", []):
        src = Path(item["src"])
        src = src if src.is_absolute() else REPO / src
        if not src.is_file():
            raise FileNotFoundError(f"audio not found: {src}")
        tracks.append({"source": src, "start": float(item["start"]), "volume": float(item.get("volume", 1.0)),
                       "sha256": sha256(src)})
    return sorted(tracks, key=lambda t: t["start"])


def assemble(scene_dir, project_dir, span=None) -> dict:
    """Build a fresh, silent HyperFrames project; returns a manifest of every file and its SHA256.

    ``span`` = (start, end) builds a project showing only that part of the film (same scene code,
    same absolute film times), used by determinism checks.
    """
    scene_dir, project_dir = Path(scene_dir).resolve(), Path(project_dir)
    scene = read_scene(scene_dir)
    if project_dir.exists():
        raise FileExistsError(f"{project_dir} exists; assemble into a new directory")
    katex, gsap = _library_paths()
    (project_dir / "vendor").mkdir(parents=True)
    shutil.copytree(katex, project_dir / "vendor/katex", ignore=shutil.ignore_patterns("contrib", "*.mjs", "README.md"))
    shutil.copy2(gsap, project_dir / "vendor/gsap.min.js")
    (project_dir / "engine").mkdir()
    for name in ENGINE_FILES:
        shutil.copy2(ASSETS / name, project_dir / "engine" / name)
    (project_dir / "scene").mkdir()
    for name in scene.get("scripts", []):
        shutil.copy2(scene_dir / name, project_dir / "scene" / Path(name).name)
    (project_dir / "index.html").write_text(_index(scene, span), encoding="utf-8")
    files = sorted(p for p in project_dir.rglob("*") if p.is_file())
    return {"scene": scene["id"], "duration": scene["duration"], "span": list(span) if span else None,
            "scene_dir": str(scene_dir), "files": {str(p.relative_to(project_dir)): sha256(p) for p in files}}


def _index(scene, span=None) -> str:
    offset, end = span or (0.0, scene["duration"])
    if not 0 <= offset < end <= scene["duration"]:
        raise ValueError("span must lie inside the film")
    duration = round(end - offset, 3)
    bg = html.escape(scene.get("background", "#101416"))
    layers = "\n".join(
        f'  <canvas id="{l["id"]}" width="1920" height="1080"></canvas>' if l["type"] == "canvas"
        else f'  <div id="{l["id"]}" class="mm-fx"></div>' for l in scene["layers"])
    scripts = "\n".join(f'<script src="scene/{html.escape(Path(n).name)}"></script>' for n in scene.get("scripts", []))
    register = json.dumps({"compositionId": "root", "duration": duration, "fonts": scene.get("fonts", []),
                           "offset": offset},
                          ensure_ascii=False)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(scene.get("title", scene["id"]))}</title>
<link rel="stylesheet" href="vendor/katex/katex.min.css">
<link rel="stylesheet" href="engine/base.css">
<style>:root {{ --bg: {bg}; }}</style>
</head>
<body>
<div id="root" data-composition-id="root" data-start="0" data-duration="{duration}" data-width="1920" data-height="1080">
{layers}
</div>
<script src="vendor/katex/katex.min.js"></script>
<script src="vendor/gsap.min.js"></script>
<script src="engine/motion.js"></script>
<script src="engine/engine.js"></script>
<script src="engine/adapter.js"></script>
{scripts}
<script>ManimindCanvas.register({register});</script>
</body>
</html>
"""
