"""Validate current navigation, migration hashes and public/local boundaries."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "archive/migrations/20261103/manifest.json"
TEXT_SUFFIXES = {".md", ".py", ".json", ".txt", ".sh", ".ps1", ".yml", ".yaml", ".toml", ".cfg", ".csv", ".canvas"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_findings(text):
    patterns = {
        "private_key": r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
        "token_literal": r"\b(?:sk-[A-Za-z0-9_-]{18,}|gh[pousr]_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,})\b",
        "url_credentials": r"https?://[^\s/@:]+:[^\s/@]+@",
        "private_network": r"\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)\b",
        "personal_host_path": r"(?:/" r"Users/[^/\s`]+/|[A-Z]:\\Users\\[^\\\s`]+\\)",
    }
    return [{"type": kind, "line": text.count("\n", 0, match.start()) + 1}
            for kind, pattern in patterns.items() for match in re.finditer(pattern, text)]


def local_links(text):
    for match in re.finditer(r"!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)", text):
        target = match.group(1).strip().strip("<>")
        if target.startswith("#"):
            continue
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        path = unquote(url.path)
        if path:
            yield path


def checked_target(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        return None, "migration_target_outside_root"
    target = root / relative
    if not target.resolve().is_relative_to(root):
        return None, "migration_target_outside_root"
    if any(p.is_symlink() for p in [target, *target.parents] if p != root and p.is_relative_to(root)):
        return None, "symlink_migration_target"
    return target, None


def publication_error(root, entry, scope):
    url = entry.get("public_url")
    if url is None:
        return None
    if scope == "local_only_20261103":
        return "public_url_outside_current_snapshot_scope"
    receipt = entry.get("publication_receipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("path"), str):
        return "verified_publication_receipt_required"
    target, error = checked_target(root, receipt["path"])
    if error or not target.is_file() or sha(target) != receipt.get("sha256"):
        return "publication_receipt_binding_invalid"
    record = json.loads(target.read_text())
    hashes = sorted(v["sha256"] for v in entry["videos"])
    if (record.get("status") != "verified" or record.get("public_url") != url
            or sorted(record.get("asset_sha256", [])) != hashes):
        return "publication_receipt_contents_invalid"
    return None


def metadata_digest(path):
    rows = []
    entries = [path] + sorted(path.rglob("*")) if path.is_dir() else [path]
    for entry in entries:
        info = entry.lstat()
        rows.append({"relative": "." if entry == path else entry.relative_to(path).as_posix(),
                     "kind": "symlink" if stat.S_ISLNK(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "file",
                     "inode": info.st_ino, "device": info.st_dev, "size": info.st_size, "mode": stat.S_IMODE(info.st_mode)})
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def stale_imports(root, migrations):
    moved = {}
    for row in migrations:
        old = Path(row["old"])
        if old.suffix != ".py":
            continue
        if row["old"].startswith("src/"):
            parts = list(old.relative_to("src").with_suffix("").parts)
        elif row["old"].startswith("backend/"):
            parts = list(old.with_suffix("").parts)
        elif row["old"].startswith("examples/"):
            parts = [old.stem]
        else:
            continue
        if parts[-1] == "__init__":
            parts.pop()
        moved[".".join(parts)] = row["old"]
    errors = []
    files = [*(root / "src/manimind").rglob("*.py"), *(root / "tests").glob("*.py"), *(root / "scripts").glob("*.py")]
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel.startswith("src/"):
            module = list(path.relative_to(root / "src").with_suffix("").parts)
            package = module[:-1]
        else:
            package = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package) - node.level + 1] if node.level else []
                base = ".".join(prefix + ([node.module] if node.module else []))
                names = [base] + [base + "." + a.name for a in node.names]
            for name in names:
                if name in moved:
                    errors.append({"path": rel, "type": "retained_import_to_archived_module", "module": name})
    return errors


def validate(root=ROOT, require_local=False):
    root = Path(root).resolve()
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    errors, findings, skipped_local = [], [], []
    for row in manifest["migrations"]:
        target, error = checked_target(root, row["new"])
        if error:
            errors.append({"path": row["new"], "type": error})
            continue
        if row["publication"] == "local_ignored" and not row["new"].startswith("archive/local/"):
            errors.append({"path": row["new"], "type": "private_destination_not_local"})
            continue
        if row["publication"] == "local_ignored" and not target.exists() and not require_local:
            skipped_local.append(row["new"])
            continue
        if not target.is_file():
            errors.append({"path": row["new"], "type": "missing_migration_target"})
        elif sha(target) != row["current_sha256"]:
            errors.append({"path": row["new"], "type": "destination_sha_changed"})
        if row["new"].startswith("archive/") and target.exists() and sha(target) != row["source_sha256"]:
            errors.append({"path": row["new"], "type": "historical_original_changed"})
    for rel in manifest["active_navigation"]:
        source = root / rel
        if not source.is_file():
            errors.append({"path": rel, "type": "missing_active_document"})
            continue
        for target in local_links(source.read_text(encoding="utf-8")):
            resolved = (source.parent / target).resolve()
            if not resolved.is_relative_to(root):
                errors.append({"path": rel, "target": target, "type": "nonportable_local_link"})
            elif resolved.is_relative_to(root / "archive/local"):
                errors.append({"path": rel, "target": target, "type": "public_link_to_private_archive"})
            elif not resolved.exists():
                errors.append({"path": rel, "target": target, "type": "broken_active_link"})
    for rel in manifest["public_files"]:
        source = root / rel
        if source.suffix in TEXT_SUFFIXES and source.is_file():
            for finding in public_findings(source.read_text(encoding="utf-8")):
                findings.append({"path": rel, **finding})
    catalog = json.loads((root / "作品/目录.json").read_text(encoding="utf-8"))
    for entry in catalog["entries"]:
        error = publication_error(root, entry, catalog.get("publication_scope"))
        if error:
            errors.append({"path": "作品/目录.json", "type": error})
        if entry["location"]["kind"] != "local_viewing_package":
            errors.append({"path": "作品/目录.json", "type": "incorrect_media_access_scope"})
    ignored = (root / ".gitignore").read_text()
    if "/archive/local/" not in ignored.splitlines():
        errors.append({"path": ".gitignore", "type": "private_archive_ignore_missing"})
    opaque = manifest.get("local_opaque_evidence", {})
    receipt_path = root / opaque.get("receipt", "__absent_private_receipt__")
    opaque_checked = 0
    if opaque and receipt_path.is_file():
        for row in json.loads(receipt_path.read_text())["operations"]:
            target, error = checked_target(root, row["new"])
            if error or not target.exists():
                errors.append({"path": "archive/local/", "type": error or "missing_local_opaque_asset"})
            elif metadata_digest(target) != row["tree"]["metadata_sha256"]:
                errors.append({"path": "archive/local/", "type": "local_opaque_metadata_changed"})
            else:
                opaque_checked += 1
    elif opaque and require_local:
        errors.append({"path": "archive/local/", "type": "missing_local_opaque_receipt"})
    canvas = json.loads((root / "docs/architecture.canvas").read_text())
    for node in canvas["nodes"]:
        if node.get("type") == "file":
            target, error = checked_target(root, node["file"])
            if error or not target.is_file():
                errors.append({"path": "docs/architecture.canvas", "target": node["file"], "type": error or "missing_canvas_file"})
    errors.extend(stale_imports(root, manifest["migrations"]))
    return {"success": not errors and not findings, "errors": errors, "public_safety_findings": findings,
            "physical_moves": len(manifest["migrations"]), "active_documents": len(manifest["active_navigation"]),
            "public_files_scanned": len(manifest["public_files"]),
            "skipped_local_archives": skipped_local, "require_local": require_local,
            "opaque_roots_checked": opaque_checked, "canvas_file_nodes": sum(n.get("type") == "file" for n in canvas["nodes"]),
            "scope": "Current navigation and proposed public files only; historical MD links retained as original evidence"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-local", action="store_true")
    args = parser.parse_args()
    report = validate(args.root, require_local=args.require_local)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
