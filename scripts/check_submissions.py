"""Check member submissions under 作品/投稿/ (standard library only).

Usage from the repository root:
    python3 scripts/check_submissions.py                     # check every submission
    python3 scripts/check_submissions.py 作品/投稿/<id>       # check one
    python3 scripts/check_submissions.py 作品/投稿/<id> --video 本地.mp4   # also compare the local MP4
    python3 scripts/check_submissions.py --list              # overview grouped by scene
    python3 scripts/check_submissions.py 作品/投稿/<id> --online          # also probe the Release URL

Exit code 0 means no errors; warnings never fail the check.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS = "作品/投稿"
SCENE_LIBRARY = "docs/curricula/scene-library"
RELEASE_PREFIX = "https://github.com/gduf-community/ManiMind/releases/download/submissions-"

ID_PATTERN = re.compile(r"^(\d{8})-[a-z0-9]+(?:-[a-z0-9]+)+$")
VERSION_PATTERN = re.compile(r"^v\d{3}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")

STATUSES = ("draft", "self_checked", "peer_reviewed", "adopted")
SUBJECTS = ("高中数学", "高中物理", "微积分", "线性代数", "概率论", "数理统计", "其他")
VIDEO_ROLES = ("final", "intermediate")
AUDIO_KINDS = ("none", "tts", "human")
REQUIRED_KEYS = ("schema_version", "id", "title", "subject", "scene_id", "author", "created_at",
                 "based_on", "tools", "status", "watched_full", "listened_full", "videos")
REQUIRED_SECTIONS = ("目标", "成片", "制作过程", "优化了什么", "未解决的问题", "可复用做法")
REQUIRED_FILES = ("投稿.json", "制作记录.md")

ALLOWED_SUFFIXES = {".md", ".json", ".py", ".txt", ".csv", ".yml", ".yaml", ".toml", ".cfg", ".tex",
                    ".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".csv", ".yml", ".yaml", ".toml", ".cfg", ".tex",
                 ".html", ".css", ".js", ".svg"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024


def _load_secret_scanner():
    spec = importlib.util.spec_from_file_location("repository_check", ROOT / "scripts/check_repository_organization.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.public_findings


public_findings = _load_secret_scanner()


def scene_ids(root=ROOT):
    ids = set()
    for path in sorted((root / SCENE_LIBRARY).glob("*.csv")):
        if path.name == "sources.csv":
            continue
        with path.open(encoding="utf-8") as handle:
            ids.update(row["id"] for row in csv.DictReader(handle) if row.get("id"))
    return ids


def strip_comments(markdown):
    return re.sub(r"<!--.*?-->", "", markdown, flags=re.S)


def sections(markdown):
    """Map each level-2 heading to its body text (HTML comments do not count as content)."""
    found, current = {}, None
    for line in strip_comments(markdown).splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: "\n".join(body).strip() for name, body in found.items()}


def open_issues(markdown):
    body = sections(markdown).get("未解决的问题", "")
    return len(re.findall(r"^\s*- \[ \]", body, re.M))


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_video(index, video, status, errors, warnings):
    where = f"videos[{index}]"
    if not isinstance(video, dict):
        errors.append(f"{where} 必须是对象")
        return
    for key in ("version", "role", "url", "sha256", "size_bytes", "duration_seconds", "resolution", "audio", "captions"):
        if key not in video:
            errors.append(f"{where} 缺少字段 {key}")
    if not VERSION_PATTERN.match(str(video.get("version", ""))):
        errors.append(f"{where}.version 应为 v001 这样的三位版本号")
    if video.get("role") not in VIDEO_ROLES:
        errors.append(f"{where}.role 只能是 {'/'.join(VIDEO_ROLES)}")
    if not SHA_PATTERN.match(str(video.get("sha256", ""))):
        errors.append(f"{where}.sha256 应为 64 位小写十六进制（上传前对本地 MP4 计算）")
    if not isinstance(video.get("size_bytes"), int) or video.get("size_bytes", 0) <= 0:
        errors.append(f"{where}.size_bytes 应为正整数")
    if not isinstance(video.get("duration_seconds"), (int, float)) or video.get("duration_seconds", 0) <= 0:
        errors.append(f"{where}.duration_seconds 应为正数")
    if not re.match(r"^\d{3,4}x\d{3,4}$", str(video.get("resolution", ""))):
        errors.append(f"{where}.resolution 应写成 1920x1080")
    if video.get("audio") not in AUDIO_KINDS:
        errors.append(f"{where}.audio 只能是 {'/'.join(AUDIO_KINDS)}")
    if not isinstance(video.get("captions"), bool):
        errors.append(f"{where}.captions 应为 true/false")
    url = video.get("url")
    if url is None:
        if status != "draft":
            warnings.append(f"{where}.url 为空：视频还没上传，请维护者代传后补链接")
    elif not (isinstance(url, str) and url.startswith(RELEASE_PREFIX) and url.endswith(".mp4")):
        errors.append(f"{where}.url 必须是本仓库 submissions-YYYYMM Release 里的 .mp4 附件链接，或 null")


def check_submission(folder, root=ROOT, known_scenes=None):
    """Return (errors, warnings) for one submission folder."""
    folder = Path(folder)
    errors, warnings = [], []
    name = folder.name
    if not ID_PATTERN.match(name):
        errors.append("目录名应为 YYYYMMDD-作者-主题，只用小写字母、数字和连字符")
    for required in REQUIRED_FILES:
        if not (folder / required).is_file():
            errors.append(f"缺少 {required}")

    total = 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink():
            errors.append(f"{rel}: 不允许符号链接")
            continue
        if path.name in {".DS_Store"} or path.name.startswith("._"):
            errors.append(f"{rel}: 系统垃圾文件，删除")
            continue
        if path.name == ".gitkeep":
            continue
        size = path.stat().st_size
        total += size
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            errors.append(f"{rel}: 不收 {suffix or '无后缀'} 文件；视频音频走 Release，压缩包和二进制不入库")
        if size > MAX_FILE_BYTES:
            errors.append(f"{rel}: {size / 1048576:.1f} MB，单个文件不超过 2 MB")
        if suffix in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                errors.append(f"{rel}: 不是 UTF-8 文本")
                continue
            if PLACEHOLDER in text:
                errors.append(f"{rel}: 还有模板占位符“{PLACEHOLDER}”没替换")
            for finding in public_findings(text):
                errors.append(f"{rel}:{finding['line']}: 疑似隐私或密钥（{finding['type']}），删除后再提交")
    if total > MAX_TOTAL_BYTES:
        errors.append(f"整个投稿 {total / 1048576:.1f} MB，不超过 10 MB；截图精选、压缩")

    record_path = folder / "制作记录.md"
    if record_path.is_file():
        record_text = record_path.read_text(encoding="utf-8-sig")
        for sample in TEMPLATE_SAMPLES:
            if sample in record_text:
                errors.append(f"制作记录.md 还留着模板样例“{sample}”，换成真实内容")
        found = sections(record_text)
        for title in REQUIRED_SECTIONS:
            if title not in found:
                errors.append(f"制作记录.md 缺少“## {title}”")
            elif not found[title]:
                errors.append(f"制作记录.md 的“## {title}”是空的；确实没有就写“无”并说明原因")

    meta_path = folder / "投稿.json"
    if not meta_path.is_file():
        return errors, warnings
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"投稿.json 不是合法 JSON：{exc}")
        return errors, warnings
    for key in REQUIRED_KEYS:
        if key not in meta:
            errors.append(f"投稿.json 缺少字段 {key}")
    if meta.get("schema_version") != 1:
        errors.append("schema_version 应为 1")
    if meta.get("id") != name:
        errors.append("投稿.json 的 id 必须与目录名相同")
    match = ID_PATTERN.match(name)
    created = str(meta.get("created_at", ""))
    try:
        valid_date = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", created)) and bool(date.fromisoformat(created))
    except ValueError:
        valid_date = False
    if not valid_date or (match and created.replace("-", "") != match.group(1)):
        errors.append("created_at 应为真实日期 YYYY-MM-DD，且与目录名开头日期一致")
    if not str(meta.get("title", "")).strip():
        errors.append("title 不能为空")
    if meta.get("subject") not in SUBJECTS:
        errors.append(f"subject 只能是：{'、'.join(SUBJECTS)}")
    scene = meta.get("scene_id")
    known = scene_ids(root) if known_scenes is None else known_scenes
    if scene is not None and scene not in known:
        errors.append(f"scene_id {scene} 不在场景库里；不对应任何场景时写 null")
    author = meta.get("author")
    if not isinstance(author, dict) or not re.match(r"^[A-Za-z0-9-]+$", str(author.get("github", ""))):
        errors.append("author.github 应为 GitHub 用户名")
    if not isinstance(meta.get("based_on"), list):
        errors.append("based_on 应为列表（借鉴的投稿 id 或经验库编号，没有就写 []）")
    tools = meta.get("tools")
    if not isinstance(tools, dict) or not all(str(tools.get(k, "")).strip() for k in ("model", "agent", "renderer")):
        errors.append("tools 需写明 model、agent、renderer（含版本）")
    status = meta.get("status")
    if status not in STATUSES:
        errors.append(f"status 只能是 {'/'.join(STATUSES)}")
    for flag in ("watched_full", "listened_full"):
        if not isinstance(meta.get(flag), bool):
            errors.append(f"{flag} 应为 true/false")
    if status in ("self_checked", "peer_reviewed", "adopted") and meta.get("watched_full") is not True:
        errors.append("status 不是 draft 时，必须有人以 1 倍速完整看过成片（watched_full: true）")
    videos = meta.get("videos")
    if not isinstance(videos, list) or (status != "draft" and not videos):
        errors.append("videos 至少登记一条成片（status 为 draft 时可以为空列表）")
        videos = videos if isinstance(videos, list) else []
    for index, video in enumerate(videos):
        check_video(index, video, status, errors, warnings)
        if isinstance(video, dict) and isinstance(video.get("url"), str) and \
                not video["url"].endswith(f"/{name}-{video.get('version')}.mp4"):
            errors.append(f"videos[{index}].url 的文件名应为 {name}-{video.get('version')}.mp4")
    voiced = [v for v in videos if isinstance(v, dict) and v.get("audio") in ("tts", "human")]
    if voiced and not (folder / "讲稿.md").is_file():
        errors.append("有配音的投稿必须附 讲稿.md")
    if any(v.get("audio") == "tts" for v in voiced) and isinstance(tools, dict) and not tools.get("tts"):
        errors.append("用了合成配音（audio: tts）时，tools.tts 要写配音工具及版本")
    keys = [(v.get("version"), v.get("role")) for v in videos if isinstance(v, dict)]
    if len({k[0] for k in keys}) != len(keys):
        errors.append("videos 里的 version 不能重复")
    if status != "draft" and not any(role == "final" for _, role in keys):
        errors.append("videos 需要恰好一条 role 为 final 的成片")
    if sum(role == "final" for _, role in keys) > 1:
        errors.append("videos 只能有一条 role 为 final；旧成片改为 intermediate")
    return errors, warnings


PLACEHOLDER = "【待填】"
# Example text shipped inside the template's comments; it must never survive into a real record.
TEMPLATE_SAMPLES = ("样例：", "01-初稿.md", "v002-0213.png")


def compare_local_video(meta_path, video_path, errors):
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8-sig"))
    final = next((v for v in meta.get("videos", []) if v.get("role") == "final"), None)
    if final is None:
        errors.append("没有 final 成片可对比")
        return
    path = Path(video_path)
    if final.get("sha256") != file_sha256(path):
        errors.append("本地 MP4 的 SHA256 与 final 登记不一致")
    if final.get("size_bytes") != path.stat().st_size:
        errors.append("本地 MP4 的字节数与 final 登记不一致")


def probe_online(meta_path, errors):
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8-sig"))
    for video in meta.get("videos", []):
        url = video.get("url")
        if not url:
            continue
        request = urllib.request.Request(url, headers={"Range": "bytes=0-63", "User-Agent": "manimind-submission-check"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                head = response.read(64)
                if response.status not in (200, 206) or b"ftyp" not in head:
                    errors.append(f"{video.get('version')}: 下载到的不是 MP4（HTTP {response.status}）")
        except OSError as exc:
            errors.append(f"{video.get('version')}: 匿名下载失败：{exc}")


def submission_folders(root=ROOT):
    base = root / SUBMISSIONS
    return sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))) if base.is_dir() else []


def overview(root=ROOT):
    rows = []
    for folder in submission_folders(root):
        try:
            meta = json.loads((folder / "投稿.json").read_text(encoding="utf-8-sig"))
            record = (folder / "制作记录.md").read_text(encoding="utf-8-sig")
        except (OSError, json.JSONDecodeError):
            rows.append((folder.name, "?", "?", "无法读取", 0, 0))
            continue
        rows.append((meta.get("scene_id") or "-", folder.name, meta.get("author", {}).get("github", "?"),
                     meta.get("status", "?"), len(meta.get("videos", [])), open_issues(record)))
    return sorted(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", nargs="*", help="投稿目录；省略时检查全部")
    parser.add_argument("--video", help="本地 final MP4，用来核对 SHA256 和大小（只能配合单个投稿）")
    parser.add_argument("--online", action="store_true", help="匿名请求 Release 链接，确认能下载")
    parser.add_argument("--list", action="store_true", help="按场景列出全部投稿和未解决问题数")
    args = parser.parse_args(argv)

    if args.list:
        print("场景\t投稿\t作者\t状态\t视频数\t未解决")
        for row in overview():
            print("\t".join(map(str, row)))
        return 0

    folders = [Path(f).resolve() for f in args.folders] or submission_folders()
    if args.video and len(folders) != 1:
        parser.error("--video 只能配合一个投稿目录")
    known = scene_ids()
    failed = False
    for folder in folders:
        errors, warnings = check_submission(folder, known_scenes=known)
        if args.video and not errors:
            compare_local_video(folder / "投稿.json", args.video, errors)
        if args.online and not errors:
            probe_online(folder / "投稿.json", errors)
        label = folder.name
        for message in errors:
            print(f"错误 {label}: {message}")
        for message in warnings:
            print(f"提醒 {label}: {message}")
        if not errors:
            print(f"通过 {label}" + (f"（{len(warnings)} 条提醒）" if warnings else ""))
        failed = failed or bool(errors)
    if not folders:
        print("还没有投稿")
    elif args.online is False and not failed:
        print("说明：未加 --online，没有验证 Release 链接能否下载；“提醒”不算失败，但要在 PR 里照实说明")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
