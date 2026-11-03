"""The documented planning example runs from a clean source-only workspace."""

import json
from pathlib import Path
import shutil
import subprocess
import sys


def test_documented_plan_command_uses_only_the_clean_workspace(tmp_path):
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "src/manimind", tmp_path / "src/manimind", ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "configs").mkdir()
    shutil.copyfile(root / "configs/pipeline.example.json", tmp_path / "configs/pipeline.example.json")
    result = subprocess.run([sys.executable, "-B", "-m", "manimind.main", "plan", "configs/pipeline.example.json",
                             "--session-id", "getting-started"], cwd=tmp_path,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp_path / "src"),
                                 "MANIMIND_DISABLE_DOTENV": "1", "PYTHONDONTWRITEBYTECODE": "1"},
                            text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["persisted_paths"]
    for path in payload["persisted_paths"].values():
        assert Path(path).is_relative_to(tmp_path)
        assert Path(path).is_file()
    assert not (tmp_path / ".env").exists()


def test_projectile_source_successor_runs_without_outputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for rel in ["tests/test_projectile_source_snapshot.py", "tests/fixtures/legacy-projectile/frozen_candidate.py",
                "archive/legacy/examples/projectile_formula_motion_full.py"]:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
    assert not (tmp_path / "outputs").exists()
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             "tests/test_projectile_source_snapshot.py"], cwd=tmp_path,
                            env={"PATH": "/usr/bin:/bin", "MANIMIND_DISABLE_DOTENV": "1",
                                 "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                            text=True, capture_output=True, check=True)
    assert "5 passed" in result.stdout
