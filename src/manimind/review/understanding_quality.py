"""Evidence-backed editorial review, separate from engineering release checks."""

from __future__ import annotations

from .learning_quality import validate_learning_review
from .semantic_focus import finite

CHECKS = ("mechanism", "attention", "pacing", "meaning_alignment", "transfer")

REVIEW_FORMAT = """
新增跨题目编辑审核，不规定作者如何分镜或必须采用哪一种教学法。
先看实际呈现的理由，不能凭作者意图、数学常识或工程测试替影片补解释。
同一总时长内增加动作不自动增分；多次重放应检查每次观察任务。
检查讲述一个结果时，结果是否仍大而可读，是否过早引入下一个推导。
不要把符号的移动、句子起点晚于事件、读数正确当作理解/全句同步的证明。

保留learning_quality的viewer_test、六维quality和action=review，另外返回：
"editorial_checks":{
 "mechanism":{"status":"pass|revise","evidence":[{"time":实看秒数,"finding":"可见理由及缺口"}]},
 "attention":同结构,"pacing":同结构,
 "meaning_alignment":同结构,"transfer":同结构},
"listening_reviewed":false,"student_tested":false,
"release_authorized":true或false,"blocking_findings":[具体阻断问题]
每个维度要引用真实媒体时点，缺少证据应要求补帧或返工，不编造已观察。
静音视觉首看中的meaning_alignment应为status=not_applicable且说明没有音轨/讲稿；
后写讲稿审核时需要检查语义焦点区间，但仍不能称为真实音频对齐或听审。
pass不允许有revise/阻断，也不能只有数学终态正确。允许非阻断美术偏好。
观众新例预测是内容支持度的编辑判断，不是真学生实验。只批准当前绑定版本。
"""


def validate_editorial_review(value, *, duration=None, stage="visual"):
    if stage not in {"visual", "narration"}:
        raise ValueError("Unknown editorial review stage")
    if value.get("action") != "review" or value.get("status") not in {"pass", "revise"}:
        raise ValueError("An explicit editorial review judgment is required")
    validate_learning_review(value, whole=True)
    checks = value.get("editorial_checks")
    if not isinstance(checks, dict) or set(checks) != set(CHECKS):
        raise ValueError("Every topic-independent editorial check needs actual evidence")
    for name, row in checks.items():
        status = row.get("status")
        allowed = {"pass", "revise", "not_applicable"} if name == "meaning_alignment" and stage == "visual" else {"pass", "revise"}
        if status not in allowed:
            raise ValueError(f"Invalid editorial status for {name}")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"Actual media evidence is required for {name}")
        for item in evidence:
            if (not finite(item.get("time")) or item["time"] < 0
                    or duration is not None and item["time"] > duration
                    or not isinstance(item.get("finding"), str) or not item["finding"].strip()):
                raise ValueError("Editorial evidence must identify an actual in-range time and observation")
    if value.get("listening_reviewed") is not False or value.get("student_tested") is not False:
        raise ValueError("This sampled visual/text review cannot certify listening or real students")
    if not isinstance(value.get("blocking_findings"), list) or type(value.get("release_authorized")) is not bool:
        raise ValueError("Declare blockers and explicit publication authorization separately")
    if value["status"] == "pass" and (
            any(row["status"] == "revise" for row in checks.values())
            or value["blocking_findings"] or value["release_authorized"] is not True):
        raise ValueError("Pass contradicts editorial findings or publication authorization")
    if value["status"] != "pass" and value["release_authorized"]:
        raise ValueError("A revision request cannot authorize publication")
    return value
