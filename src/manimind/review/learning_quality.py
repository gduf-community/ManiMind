"""Topic-independent subtitle diagnostics and evidence-bound editorial scoring."""

from __future__ import annotations

import math
import unicodedata

DIMENSIONS = {"science": 20, "causality": 25, "visual_explanation": 20,
              "finish": 15, "pacing": 10, "interest": 10}
CRITICAL = {"science", "causality", "visual_explanation", "pacing"}

QUALITY_FORMAT = """
本轮增加固定的教学质量检查，不规定镜头、角色、配色、公式数量或统一节奏。
先判断观众从实际画面能得到什么，不把自己已知的知识或作者意图补进画面。
短暂动作要核对前、中、后；静止画面也可以非常有效，不按运动量评分。
说明主张的依据是推导、模型模拟、类比还是观察，不能把模拟当独立实验证据。
不得把尚未实际听审或学生测试的内容写成已验证。

仍返回原 review JSON。每份最终审核另加：
"viewer_test":{"can_explain":"画面支持观众说清的理由，不复述结论",
 "missing_links":["未被呈现的必要连接，没有则空数组"],
 "transfer_question":"检验同一机制而非背数值的新问题",
 "supported_answer":"视频是否为该问题提供推理依据，不能冒充学生实测"}

整片审核（stage含whole或source-audit）另加quality，六项均有：
"quality":{"science":{"rating":0到4的整数,"evidence":"具体时间及观察"},
 "causality":同结构,"visual_explanation":同结构,"finish":同结构,
 "pacing":同结构,"interest":同结构}
锚点：0=缺失/错误；1=严重缺陷；2=有内容但存在重要缺口；
3=目标受众可跟随、有明确证据；4=完整且精炼、关键过程和迁移联系清楚。
science20、causality25、visual_explanation20、finish15、pacing10、interest10。
整片pass须加权至少80/100，science/causality/visual_explanation/pacing均至少3。
分数不能抵消blocker；不满足就如实revise，不能为了完成制作提高评分。
非阻断的个人美术偏好可记minor，不强迫作者接受你的分镜方案。
观测记录的time引用提供的原帧时间；时序联系表内的其他时刻可在issues中举证。
"""


def quality_score(quality: dict) -> float:
    if not isinstance(quality, dict) or set(quality) != set(DIMENSIONS):
        raise ValueError("quality must contain exactly the six frozen dimensions")
    for name, row in quality.items():
        if (not isinstance(row, dict) or type(row.get("rating")) is not int
                or not 0 <= row["rating"] <= 4
                or not isinstance(row.get("evidence"), str) or not row["evidence"].strip()):
            raise ValueError(f"Malformed evidence-backed quality dimension: {name}")
    return sum(DIMENSIONS[k] * quality[k]["rating"] / 4 for k in DIMENSIONS)


def validate_learning_review(value: dict, *, whole: bool) -> None:
    if value.get("action") != "review":
        return
    viewer = value.get("viewer_test")
    if not isinstance(viewer, dict):
        raise ValueError("A viewer_test is required; do not substitute an author-intent summary")
    for key in ("can_explain", "transfer_question", "supported_answer"):
        if not isinstance(viewer.get(key), str) or not viewer[key].strip():
            raise ValueError(f"viewer_test.{key} is required")
    if (not isinstance(viewer.get("missing_links"), list)
            or not all(isinstance(x, str) and x.strip() for x in viewer["missing_links"])):
        raise ValueError("viewer_test.missing_links must be an explicit list")
    if whole:
        score = quality_score(value.get("quality"))
        if value.get("status") == "pass" and (
                score < 80 or any(value["quality"][k]["rating"] < 3 for k in CRITICAL)):
            raise ValueError("Pass contradicts the frozen quality threshold or a critical dimension")


def runtime_wrap(text: str, width) -> list[str]:
    """Mirror the existing frozen helper for diagnosis, without changing its output."""
    lines, current = [], ""
    for char in text:
        if current and width(current + char) > 12.3:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def subtitle_audit(timeline: dict, width) -> dict:
    rows, blockers, advisories = [], [], []
    duration = timeline["duration"]
    last_end = 0.0
    for cue in timeline["cues"]:
        spans = cue.get("spoken_spans", [])
        if cue.get("spoken", "").strip() and not spans:
            blockers.append({"cue": cue["id"], "problem": "Spoken cue has no measured subtitle spans"})
        for i, span in enumerate(spans):
            start = span["start"]
            end = spans[i + 1]["start"] if i + 1 < len(spans) else cue["start"] + cue["duration"]
            if (any(type(t) not in (float, int) or not math.isfinite(t) for t in (start, end))
                    or not 0 <= start < end <= duration + .001 or start < last_end - .001):
                blockers.append({"cue": cue["id"], "problem": "Invalid or overlapping subtitle interval"})
            last_end = end
            lines = runtime_wrap(span["text"], width)
            row = {"cue": cue["id"], "start": start, "end": end, "text": span["text"], "lines": lines}
            rows.append(row)
            if len(lines) > 2 or any(line.strip() and all(
                    unicodedata.category(c).startswith(("P", "Z")) for c in line) for line in lines):
                blockers.append({"cue": cue["id"], "time": start,
                                 "problem": "Subtitle exceeds two lines or leaves punctuation alone", "lines": lines})
            if len(span["text"]) > 40:
                advisories.append({"cue": cue["id"], "time": start,
                                   "problem": "Long subtitle span; inspect reading load and premature reveal",
                                   "characters": len(span["text"])})
    return {"scope": "Mechanical subtitle diagnosis, not semantic approval", "rows": rows,
            "blockers": blockers, "advisories": advisories,
            "writer": "learning_quality.subtitle_audit", "consumers": ["creator", "reviewer", "release gate"],
            "lifecycle": "Current measured timeline and frozen font only",
            "invalidation": "Any timeline, font or subtitle helper change"}


def font_width():
    from PIL import ImageFont
    from manimind.components.catalog import FONT_INDEX, FONT_PATH
    font = ImageFont.truetype(str(FONT_PATH), 27 * 4, index=FONT_INDEX)

    def width(text):
        left, _, right, _ = font.getbbox(text)
        return max(1, right - left + 4) / 400
    return width
