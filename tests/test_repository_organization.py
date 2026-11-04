"""Repository navigation checks, independent of native render and speech state."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repository_check", ROOT / "scripts/check_repository_organization.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_active_navigation_and_public_boundaries():
    result = check.validate(ROOT)
    assert result["errors"] == []
    assert result["public_safety_findings"] == []


def test_migration_records_are_real_and_unique():
    data = json.loads((ROOT / check.MANIFEST).read_text())
    rows = data["migrations"]
    assert len(rows) == len({r["old"] for r in rows})
    assert len(rows) == len({r["new"] for r in rows})
    assert all(r["status"] == "physically_moved" for r in rows)
    assert all(len(r["source_sha256"]) == 64 for r in rows)
    assert {"writer", "consumers", "lifecycle", "invalidation"} <= data.keys()


def test_catalog_does_not_publish_drafts_or_invent_urls():
    data = json.loads((ROOT / "作品/目录.json").read_text())
    if data.get("publication_scope") == "local_only_20261103":
        assert all(e["public_url"] is None for e in data["entries"])
    new = next(e for e in data["entries"] if e["id"] == "derivative-01-motion-revision-20261103")
    assert new["stage"] == "captioned_revision_preview_delivered"
    assert len(new["videos"]) == 1
    assert new["videos"][0]["sha256"] == "30c321299ca2fba9897791f8c98285b55824f88b5c138acf6f89443129d7293a"
    old = next(e for e in data["entries"] if e["id"] == "derivative-original-20261103")
    assert len(old["videos"]) == 9
    assert data["current_revision"]["stage"] == "in_progress"


def test_safety_findings_never_return_matching_secret_text():
    fake = "sk-" + "A" * 24
    findings = check.public_findings("header\n" + fake)
    assert findings == [{"type": "token_literal", "line": 2}]
    assert fake not in json.dumps(findings)


def test_links_parse_images_spaces_and_fragments():
    assert list(check.local_links("[x](<文档 有空格.md#标题>) ![p](图.png) [web](https://example.com)")) == ["文档 有空格.md", "图.png"]


def test_public_tree_passes_without_ignored_local_archives(tmp_path):
    manifest = json.loads((ROOT / check.MANIFEST).read_text())
    files = set(manifest["public_files"]) | {check.MANIFEST, ".gitignore", "作品/目录.json"}
    catalogue = json.loads((ROOT / "作品/目录.json").read_text())
    files.update(e["publication_receipt"]["path"] for e in catalogue["entries"] if "publication_receipt" in e)
    for rel in manifest["active_navigation"]:
        source = ROOT / rel
        files.add(rel)
        for target in check.local_links(source.read_text()):
            path = (source.parent / target).resolve()
            if path.is_file() and path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / "archive/local"):
                files.add(path.relative_to(ROOT).as_posix())
    canvas = json.loads((ROOT / "docs/architecture.canvas").read_text())
    files.update(n["file"] for n in canvas["nodes"] if n.get("type") == "file")
    for rel in files:
        assert not rel.startswith("archive/local/")
        source = ROOT / rel
        if source.is_file():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    assert not (tmp_path / "archive/local").exists()
    report = check.validate(tmp_path)
    assert report["success"], report
    assert report["skipped_local_archives"]
    strict = check.validate(tmp_path, require_local=True)
    assert not strict["success"]
    assert all(e["type"] in {"missing_migration_target", "missing_local_opaque_receipt"} for e in strict["errors"])


def test_archive_targets_must_be_inside_root_without_symlinks(tmp_path):
    assert check.checked_target(tmp_path, "../escape")[1] == "migration_target_outside_root"
    real = tmp_path / "real"
    real.write_text("original")
    (tmp_path / "link").symlink_to(real)
    assert check.checked_target(tmp_path, "link")[1] == "symlink_migration_target"


def test_future_public_urls_require_verified_release_binding(tmp_path):
    entry = {"public_url": "https://example.invalid/" + "future", "videos": []}
    assert check.publication_error(tmp_path, entry, "local_only_20261103") == "public_url_outside_current_snapshot_scope"
    assert check.publication_error(tmp_path, entry, "future_release") == "verified_publication_receipt_required"


def test_local_index_builder_preserves_published_catalogue(tmp_path):
    output = tmp_path / "catalogue.json"
    original = json.dumps({"publication_scope": "github_release_20261104", "entries": []})
    output.write_text(original)
    backup = tmp_path / "previous.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/build_work_catalog.py"),
        "--output", str(output), "--previous-output", str(backup),
    ], capture_output=True, text=True)
    assert result.returncode != 0
    assert "release reconciliation" in result.stderr
    assert output.read_text() == original
    assert not backup.exists()


def test_published_media_have_per_file_downloads_and_digest_evidence():
    data = json.loads((ROOT / "作品/目录.json").read_text())
    if not data.get("publication_scope", "").startswith("github_release"):
        return
    for entry in data["entries"]:
        receipt = json.loads((ROOT / entry["publication_receipt"]["path"]).read_text())
        assets = {a["sha256"]: a for a in receipt["assets"]}
        assert entry["public_url"] == receipt["public_url"]
        for video in entry["videos"]:
            asset = assets[video["sha256"]]
            assert video["public_url"] == asset["public_url"]
            assert video["public_url"].startswith("https://github.com/gduf-community/ManiMind/releases/download/")
            assert video["size_bytes"] == asset["size_bytes"]
            assert asset["github_digest"] == "sha256:" + video["sha256"]
            assert asset["state"] == "uploaded"
            assert asset["anonymous_range_status"] == 206
            assert asset["mp4_header"] == "ftyp"
        assert receipt["content_stage"] == entry["stage"]


def test_canvas_paths_and_current_formula_node_are_preserved():
    canvas = json.loads((ROOT / "docs/architecture.canvas").read_text())
    nodes = {n["id"]: n for n in canvas["nodes"]}
    assert "traceable_film_v3" in nodes["node-formula-continuity"]["text"]
    assert nodes["node-file-current-gate"]["file"] == "src/manimind/postproduce/traceable_film_v3.py"
    assert "archive/legacy/backend/" in nodes["node-backend-api"]["text"]
    for node in canvas["nodes"]:
        if node.get("type") == "file":
            assert (ROOT / node["file"]).is_file()
