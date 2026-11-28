import json
from pathlib import Path

import pytest

from manimind.canvas import project

FIXTURE = Path(__file__).parent / "fixtures/canvas/tiny"


def test_assemble_builds_a_silent_hyperframes_composition(tmp_path):
    manifest = project.assemble(FIXTURE, tmp_path / "p")
    index = (tmp_path / "p/index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="root"' in index and 'data-duration="1.0"' in index
    assert "<audio" not in index                       # HyperFrames renders the picture only
    assert index.index("engine/adapter.js") < index.index("scene/tiny.js")
    register = json.loads(index.split("ManimindCanvas.register(")[1].split(");")[0])
    assert register == {"compositionId": "root", "duration": 1.0, "fonts": ["40px KaTeX_Main", "40px KaTeX_Math"],
                        "offset": 0.0}
    for name in ("engine/engine.js", "engine/motion.js", "engine/base.css", "vendor/gsap.min.js",
                 "vendor/katex/katex.min.js", "scene/tiny.js"):
        assert name in manifest["files"]
    with pytest.raises(FileExistsError):
        project.assemble(FIXTURE, tmp_path / "p")


def test_span_project_keeps_film_time(tmp_path):
    project.assemble(FIXTURE, tmp_path / "s", span=(0.25, 0.75))
    index = (tmp_path / "s/index.html").read_text(encoding="utf-8")
    assert 'data-duration="0.5"' in index and '"offset": 0.25' in index
    with pytest.raises(ValueError):
        project.assemble(FIXTURE, tmp_path / "bad", span=(0.5, 2.0))


def test_scene_scripts_must_stay_inside_the_scene(tmp_path):
    scene = tmp_path / "scene"
    scene.mkdir()
    (scene / "scene.json").write_text(json.dumps({"id": "x", "duration": 1, "layers": [{"type": "canvas", "id": "c"}],
                                                  "scripts": ["../escape.js"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        project.read_scene(scene)


def test_audio_resolves_against_the_repository_and_is_hashed(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF0000WAVE")
    tracks = project.resolve_audio({"audio": []}, [{"src": str(wav), "start": 1.5}])
    assert tracks[0]["start"] == 1.5 and tracks[0]["volume"] == 1.0 and len(tracks[0]["sha256"]) == 64
    with pytest.raises(FileNotFoundError):
        project.resolve_audio({"audio": [{"src": "outputs/does-not-exist.wav", "start": 0}]})
