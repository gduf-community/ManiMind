from manimind.postproduce import pilot


def test_v2_only_clarifies_runtime_interfaces_without_a_lesson_template():
    first = pilot.read_json(pilot.ROOT / "configs/learning-workflow-v1.json")
    second = pilot.read_json(pilot.ROOT / "configs/learning-workflow-v2.json")
    assert second["version"] != first["version"]
    assert second["evaluation"] == first["evaluation"]
    assert second["author_guidance"] == first["author_guidance"]
    assert len(second["technical_guidance"]) == 4
    assert "1至4项" in second["technical_guidance"][0]
    assert all(topic not in str(second) for topic in ("平抛", "条件概率", "并联", "4h", "2T"))
