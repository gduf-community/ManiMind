"""The new editing guidance uses the existing evidence contract, not a word ban."""

import hashlib
import json
from pathlib import Path

import pytest

from manimind.review.understanding_quality import CHECKS
from manimind.review.meaning_units import SOURCE_CONTRACT


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_unit_profile_remains_unchanged():
    original = ROOT / "configs/visual-first-workflow-v4-unit.json"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == "ae00dd9f63190a29f4745c54bfd83d2ae36468d459f456509907edefa095adfd"


@pytest.mark.parametrize("name", ("v4.1", "v4.2"))
def test_positive_profile_reuses_the_current_editorial_and_delivery_contract(name):
    profile = json.loads((ROOT / f"configs/visual-first-workflow-{name}-unit.json").read_text())
    assert profile["version"] == "understanding-first-v3"
    assert profile["delivery_contract"] == SOURCE_CONTRACT
    assert set(profile["review_checks"]) == set(CHECKS)
    assert profile["review"]["critical_minimum"] == {
        "science": 3, "causality": 3, "visual_explanation": 3, "pacing": 3,
    }
    assert "整课连续讲稿" in profile["review"]["post_visual_narration"]
    assert "具体句意和画面" in profile["review"]["post_visual_narration"]
    assert "只帮助定位" in profile["prose_review_scope"]
    assert "数学否定" in profile["prose_review_scope"]
    assert all(name not in profile for name in ("forbidden_words", "negation_limit", "maximum_contrasts"))


def test_positive_v4_1_source_remains_frozen():
    original = ROOT / "configs/visual-first-workflow-v4.1-unit.json"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == "274474e4fd9297a318b8ff2c5e131df99fbc716e6c851d056832320cf4efcb28"


def test_plain_language_guidance_preserves_science_and_listening_boundaries():
    profile = json.loads((ROOT / "configs/visual-first-workflow-v4.2-unit.json").read_text())
    assert profile["based_on"] == "configs/visual-first-workflow-v4.1-unit.json"
    guidance = " ".join(profile["author_guidance"])
    assert "学科通行术语" in guidance
    assert "条件、单位、方向和中间理由" in guidance
    assert "按真实口语通读" in guidance
    assert "文字通读不等于真实声音已通过听审" in profile["prose_review_scope"]
    assert all(key not in profile for key in ("maximum_sentence_length", "spoken_word_quota", "banned_terms"))
