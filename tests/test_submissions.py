"""Member submissions under 作品/投稿/ follow the guide, and the checker enforces it."""

import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_submissions", ROOT / "scripts/check_submissions.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

TEMPLATE = ROOT / check.SUBMISSIONS / "_模板"
GUIDE = ROOT / check.SUBMISSIONS / "投稿指南.md"
SCENES = {"CA-010"}
ID = "20261126-someone-accumulation-rate"
RECORD = """# 累积量的变化率

## 目标
让学过导数的学生看懂累积量对上限求导为什么回到被积函数。

## 成片
v002，4:50，静音；作者 1 倍速完整看过一遍。

## 制作过程
1. 选 CA-010。2. 渲染 v001、v002。渲染命令：manimgl 源码/scene.py AccumulationScene

## 优化了什么
| 版本 | 问题 | 改法 | 结果 |
| --- | --- | --- | --- |
| v001→v002 | 01:10 闪回 | 对应变换 | 已复查 |

## 未解决的问题
- [ ] 02:30 标签偏挤
- [x] 01:10 闪回，已改

## 可复用做法
- 做法：同一舍入；适用：近似值相减；证据：源码/scene.py
"""


def filled(tmp_path, **overrides):
    folder = tmp_path / ID
    shutil.copytree(TEMPLATE, folder)
    meta = json.loads((folder / "投稿.json").read_text(encoding="utf-8"))
    meta.update({
        "id": ID, "title": "累积量的变化率", "subject": "微积分", "scene_id": "CA-010",
        "author": {"github": "someone"}, "created_at": "2026-11-26", "status": "self_checked",
        "watched_full": True,
        "tools": {"model": "deepseek-v4", "agent": "Cline 3.0", "renderer": "manimgl 1.7.2", "tts": None},
        "videos": [{
            "version": "v002", "role": "final",
            "url": f"{check.RELEASE_PREFIX}{ID}-v002.mp4",
            "sha256": "a" * 64, "size_bytes": 1000, "duration_seconds": 290.0,
            "resolution": "1920x1080", "audio": "none", "captions": False,
        }],
    })
    meta.update(overrides)
    (folder / "投稿.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (folder / "制作记录.md").write_text(RECORD, encoding="utf-8")
    return folder


def errors_of(folder):
    return check.check_submission(folder, known_scenes=SCENES)[0]


def test_every_real_submission_passes():
    for folder in check.submission_folders():
        errors, _ = check.check_submission(folder)
        assert errors == [], f"{folder.name}: {errors}"


def test_template_covers_every_required_field_and_section():
    meta = json.loads((TEMPLATE / "投稿.json").read_text(encoding="utf-8"))
    assert set(check.REQUIRED_KEYS) <= meta.keys()
    record = check.sections((TEMPLATE / "制作记录.md").read_text(encoding="utf-8"))
    assert set(check.REQUIRED_SECTIONS) <= record.keys()
    assert errors_of(TEMPLATE), "the unfilled template must not pass"


def test_guide_documents_what_the_checker_enforces():
    guide = GUIDE.read_text(encoding="utf-8")
    for name in (*check.REQUIRED_SECTIONS, *check.REQUIRED_KEYS, *check.STATUSES, *check.SUBJECTS):
        assert name in guide, name
    assert "scripts/check_submissions.py" in guide
    assert check.RELEASE_PREFIX in guide and "--clobber" in guide
    assert "submissions-" not in guide and "release create" not in guide


def test_filled_template_passes(tmp_path):
    assert errors_of(filled(tmp_path)) == []


def test_record_needs_all_sections(tmp_path):
    folder = filled(tmp_path)
    (folder / "制作记录.md").write_text(RECORD.replace("## 未解决的问题", "## 其他"), encoding="utf-8")
    assert any("未解决的问题" in e for e in errors_of(folder))


def test_media_secrets_and_size_are_rejected(tmp_path):
    folder = filled(tmp_path)
    (folder / "成片.mp4").write_bytes(b"\0" * 10)
    (folder / "提示词/01.md").write_text("key: sk-" + "A" * 30, encoding="utf-8")
    (folder / "截图/huge.png").write_bytes(b"\0" * (check.MAX_FILE_BYTES + 1))
    errors = " ".join(errors_of(folder))
    assert ".mp4" in errors and "token_literal" in errors and "2 MB" in errors
    assert "sk-" not in errors


def test_honesty_rules(tmp_path):
    assert any("watched_full" in e for e in errors_of(filled(tmp_path / "a", watched_full=False)))
    videos = json.loads((filled(tmp_path / "b") / "投稿.json").read_text(encoding="utf-8"))["videos"]
    two_finals = videos + [dict(videos[0], version="v003")]
    assert any("只能有一条" in e for e in errors_of(filled(tmp_path / "c", videos=two_finals)))
    assert any("scene_id" in e for e in errors_of(filled(tmp_path / "d", scene_id="XX-999")))
    assert any("id 必须" in e for e in errors_of(filled(tmp_path / "e", id="20261126-other-x")))


def test_video_url_rules(tmp_path):
    video = json.loads((filled(tmp_path / "a") / "投稿.json").read_text(encoding="utf-8"))["videos"][0]
    outside = filled(tmp_path / "b", videos=[dict(video, url="https://pan.example.com/x.mp4")])
    assert any("Release" in e for e in errors_of(outside))
    pending = filled(tmp_path / "c", videos=[dict(video, url=None)])
    errors, warnings = check.check_submission(pending, known_scenes=SCENES)
    assert errors == [] and warnings


def test_local_video_comparison(tmp_path):
    folder = filled(tmp_path)
    media = tmp_path / "final.mp4"
    media.write_bytes(b"ftyp-test")
    errors = []
    check.compare_local_video(folder / "投稿.json", media, errors)
    assert len(errors) == 2
    meta = json.loads((folder / "投稿.json").read_text(encoding="utf-8"))
    meta["videos"][0].update(sha256=check.file_sha256(media), size_bytes=media.stat().st_size)
    (folder / "投稿.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    errors = []
    check.compare_local_video(folder / "投稿.json", media, errors)
    assert errors == []


def test_overview_counts_open_issues(tmp_path):
    base = tmp_path / check.SUBMISSIONS
    base.mkdir(parents=True)
    filled(base)
    shutil.copytree(TEMPLATE, base / "_模板")
    assert check.overview(tmp_path) == [("CA-010", ID, "someone", "self_checked", 1, 1)]


def test_comment_only_sections_and_template_samples_fail(tmp_path):
    folder = filled(tmp_path / "a")
    record = RECORD.replace("- [ ] 02:30 标签偏挤\n- [x] 01:10 闪回，已改", "<!-- 以后再写 -->")
    (folder / "制作记录.md").write_text(record, encoding="utf-8")
    assert any("未解决的问题" in e and "空" in e for e in errors_of(folder))
    folder = filled(tmp_path / "b")
    (folder / "制作记录.md").write_text(RECORD + "\n见 提示词/01-初稿.md\n", encoding="utf-8")
    assert any("模板样例" in e for e in errors_of(folder))
    folder = filled(tmp_path / "c")
    (folder / "讲稿.md").write_text("【待填】", encoding="utf-8")
    assert any("讲稿.md" in e and "占位符" in e for e in errors_of(folder))


def test_voice_url_name_and_date_rules(tmp_path):
    video = json.loads((filled(tmp_path / "a") / "投稿.json").read_text(encoding="utf-8"))["videos"][0]
    voiced = filled(tmp_path / "b", videos=[dict(video, audio="tts")])
    errors = errors_of(voiced)
    assert any("讲稿.md" in e for e in errors) and any("tools.tts" in e for e in errors)
    renamed = filled(tmp_path / "c", videos=[dict(video, url=f"{check.RELEASE_PREFIX}other.mp4")])
    assert any("url 应为" in e for e in errors_of(renamed))
    assert any("created_at" in e for e in errors_of(filled(tmp_path / "d", created_at="20261126")))


def test_utf8_bom_from_windows_editors_is_accepted(tmp_path):
    folder = filled(tmp_path)
    meta = folder / "投稿.json"
    meta.write_bytes(b"\xef\xbb\xbf" + meta.read_bytes())
    assert errors_of(folder) == []


def test_pr_scope_splits_submissions_maintainer_files_and_outside():
    changed = [f"{check.SUBMISSIONS}/{ID}/投稿.json", f"{check.SUBMISSIONS}/{ID}/截图/a.png",
               f"{check.SUBMISSIONS}/经验库.md", f"{check.SUBMISSIONS}/_模板/投稿.json", "README.md"]
    assert check.pr_scope(changed) == (
        [ID], [f"{check.SUBMISSIONS}/_模板/投稿.json", f"{check.SUBMISSIONS}/经验库.md"], ["README.md"])


def test_pr_warnings_cover_scope_and_ownership(tmp_path):
    filled(tmp_path / check.SUBMISSIONS)
    assert check.pr_warnings([ID], [], [], root=tmp_path, pr_author="SomeOne") == []
    warnings = " ".join(check.pr_warnings([ID, "20261127-x-y"], ["作品/投稿/经验库.md"], ["src/a.py"],
                                          root=tmp_path, pr_author="other"))
    for expected in ("只放一个", "维护者", "src/a.py", "登记作者是 someone", "被删除"):
        assert expected in warnings
    assert check.pr_warnings([], [], ["src/a.py"], root=tmp_path) == []


def test_actions_annotations_and_summary(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    check.report("错误", ID, "缺少 投稿.json")
    assert f"::error title=投稿检查 {ID}::缺少 投稿.json" in capsys.readouterr().out
    check.write_summary([(ID, ["x"], [])])
    assert f"| {ID} | 不通过 | 1 | 0 |" in summary.read_text(encoding="utf-8")
