"""Render a ManiMind Canvas scene with the pinned HyperFrames CLI and keep a receipt.

    python -m manimind.canvas.render SCENE_DIR --out NEW_DIR [--audio AUDIO.json] [--check 12:13]

Steps: assemble a silent HyperFrames project (project.py) -> ``hyperframes lint`` -> ``hyperframes
render`` the picture -> mix the voice under the constant-gain rule and copy the video stream into
NEW_DIR/film.mp4 (voice.py) -> optional determinism check -> NEW_DIR/receipt.json.

Pinned and recorded: HyperFrames/GSAP/KaTeX versions (tools/hyperframes/package-lock.json), the
browser executable and its version, FFmpeg, every input file hash. HyperFrames telemetry, update
checks and auto-installs are switched off through its own environment variables for every call.

Determinism check: builds a silent project showing only the given span (same scene code, same film
times), renders it twice as PNG frames, once with one worker and once with three (frames then render
in a different order), and requires byte-identical frames.

State: NEW_DIR is create-only derived output (writer: this command; readers: reviewers, publishers);
the receipt is valid only for the exact inputs it lists. A failed run keeps its evidence; rerun into
a new directory instead of overwriting.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from . import project, voice

REPO = project.REPO
TOOLS = project.TOOLS
CLI = TOOLS / "node_modules/hyperframes/bin/hyperframes.mjs"
DEFAULT_BROWSER = "~/Library/Caches/ms-playwright/chromium_headless_shell-1234/*/chrome-headless-shell"
QUIET_ENV = {"DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1",
             "HYPERFRAMES_NO_AUTO_INSTALL": "1", "HYPERFRAMES_NO_OPTIONAL_INSTALL": "1",
             "HYPERFRAMES_NO_CAPTURE_DOTENV": "1"}


def browser_path() -> Path:
    """The pinned headless browser: MANIMIND_CANVAS_BROWSER, else the cached chrome-headless-shell."""
    explicit = os.environ.get("MANIMIND_CANVAS_BROWSER")
    hits = [Path(explicit)] if explicit else [Path(p) for p in glob.glob(os.path.expanduser(DEFAULT_BROWSER))]
    hits = [p for p in hits if p.is_file()]
    if not hits:
        raise FileNotFoundError("Pinned browser not found; set MANIMIND_CANVAS_BROWSER to a chrome-headless-shell")
    return hits[0]


def environment(browser: Path) -> dict:
    env = dict(os.environ, **QUIET_ENV, HYPERFRAMES_BROWSER_PATH=str(browser))
    ffmpeg_dir = REPO / "manimgl_env/bin"
    if (ffmpeg_dir / "ffmpeg").exists():
        env["PATH"] = f"{ffmpeg_dir}{os.pathsep}{env.get('PATH', '')}"
        # HyperFrames resolves the encoder from these first; PATH alone was not honoured.
        env["FFMPEG_PATH"] = env["HYPERFRAMES_FFMPEG_PATH"] = str((ffmpeg_dir / "ffmpeg").resolve())
        env["FFPROBE_PATH"] = str((ffmpeg_dir / "ffprobe").resolve())
    return env


def node() -> str:
    for candidate in (os.environ.get("MANIMIND_NODE"), "node"):
        if not candidate:
            continue
        try:
            out = subprocess.run([candidate, "--version"], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        if int(out.strip().lstrip("v").split(".")[0]) >= 22:
            return candidate
    raise RuntimeError("Node.js >= 22 is required (set MANIMIND_NODE to its path)")


def hyperframes(args, env, log: Path):
    """Run the pinned CLI from the attempt directory, so it never reads the repository's .env."""
    cmd = [node(), str(CLI), *(str(Path(a).resolve()) if isinstance(a, Path) else a for a in args)]
    with open(log, "ab") as out:
        out.write(("$ " + " ".join(cmd[1:]) + "\n").encode())
        out.flush()
        result = subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, cwd=log.parent)
    if result.returncode:
        raise RuntimeError(f"hyperframes {args[0]} failed ({result.returncode}); see {log}")


def versions(browser: Path, env) -> dict:
    lock = json.loads((TOOLS / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    browser_version = subprocess.run([str(browser), "--version"], capture_output=True, text=True).stdout.strip()
    ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, env=env).stdout.split("\n")[0]
    return {"hyperframes": lock["node_modules/hyperframes"]["version"], "gsap": lock["node_modules/gsap"]["version"],
            "katex": lock["node_modules/katex"]["version"], "package_lock_sha256": project.sha256(TOOLS / "package-lock.json"),
            "browser": str(browser), "browser_version": browser_version, "ffmpeg": ffmpeg}


def frames_digest(directory: Path) -> dict:
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*.png"))}


def check_determinism(scene_dir, span: str, out: Path, env, log: Path) -> dict:
    """Render one span of the film twice as PNG frames (1 worker, then 3) and compare bytes."""
    start, end = (float(x) for x in span.split(":"))
    project.assemble(scene_dir, out / "determinism-project", span=(start, end))
    runs = {}
    for name, workers in (("one-worker", "1"), ("parallel", "3")):
        target = out / f"determinism-{name}"
        hyperframes(["render", out / "determinism-project", "--format", "png-sequence", "--workers", workers,
                     "-o", target, "--quiet"], env, log)
        runs[name] = frames_digest(target)
    a, b = runs["one-worker"], runs["parallel"]
    differing = sorted(k for k in a if a.get(k) != b.get(k))
    return {"span": [start, end], "frames": len(a), "identical": bool(a) and a.keys() == b.keys() and not differing,
            "differing_frames": differing[:20]}


def render(scene_dir, out, audio=None, check=None, fps=30) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    log = out / "hyperframes.log"
    browser = browser_path()
    env = environment(browser)
    scene = project.read_scene(Path(scene_dir))
    tracks = project.resolve_audio(scene, audio)
    manifest = project.assemble(scene_dir, out / "project")
    receipt = {"schema_version": 1, "writer": "manimind.canvas.render", "consumers": ["reviewer", "publisher"],
               "lifecycle": "This render attempt only", "invalidation": "Any listed input, version or browser change",
               "started_at": datetime.now(timezone.utc).isoformat(), "versions": versions(browser, env),
               "inputs": manifest, "fps": fps,
               "audio": [{**t, "source": str(t["source"])} for t in tracks]}
    hyperframes(["lint", out / "project"], env, log)
    picture = out / ("picture.mp4" if tracks else "film.mp4")
    hyperframes(["render", out / "project", "--fps", str(fps), "--quality", "looks", "-o", picture, "--quiet"], env, log)
    receipt["picture"] = {"path": str(picture), "sha256": project.sha256(picture)}
    if tracks:
        receipt["voice"] = voice.mix(tracks, float(scene["duration"]), out / "voice.wav", env)
        voice.mux(picture, out / "voice.wav", out / "film.mp4", env)
    receipt["film"] = {"path": str(out / "film.mp4"), "sha256": project.sha256(out / "film.mp4")}
    if check:
        receipt["determinism"] = check_determinism(scene_dir, check, out, env, log)
    receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
    (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    if check and not receipt["determinism"]["identical"]:
        raise RuntimeError(f"Determinism check failed: {receipt['determinism']['differing_frames']}")
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scene", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--audio", type=Path, help='JSON list [{"src", "start", "volume"}] overriding scene.json audio')
    ap.add_argument("--check", help="START:END seconds rendered twice (1 vs 3 workers) and compared byte for byte")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args(argv)
    audio = json.loads(a.audio.read_text(encoding="utf-8")) if a.audio else None
    receipt = render(a.scene, a.out, audio=audio, check=a.check, fps=a.fps)
    print(json.dumps({"film": receipt["film"], "determinism": receipt.get("determinism")}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
