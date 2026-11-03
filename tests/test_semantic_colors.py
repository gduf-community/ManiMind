from manimind.review import (
    assess_semantic_color_consistency,
    extract_semantic_color_map,
)


def test_extract_semantic_color_map_reads_common_manim_patterns() -> None:
    code = """
eq = MathTex(r"x", r"=", r"2", tex_to_color_map={r"x": BLUE, "y": GREEN})
eq.set_color_by_tex(r"z", YELLOW)
"""

    assert extract_semantic_color_map(code) == {
        "x": "BLUE",
        "y": "GREEN",
        "z": "YELLOW",
    }


def test_assess_semantic_color_consistency_blocks_conflicts() -> None:
    finding = assess_semantic_color_consistency([
        {
            "segment_id": "seg-1",
            "content": {
                "scene_code": 'MathTex(r"x", tex_to_color_map={r"x": BLUE})',
            },
        },
        {
            "segment_id": "seg-2",
            "content": {
                "scene_code": 'MathTex(r"x", tex_to_color_map={r"x": YELLOW})',
            },
        },
    ])

    assert finding.status == "block"
    assert any("inconsistent colors" in issue for issue in finding.issues)


def test_assess_semantic_color_consistency_passes_stable_colors() -> None:
    finding = assess_semantic_color_consistency([
        {
            "segment_id": "seg-1",
            "content": {
                "scene_code": 'MathTex(r"x", tex_to_color_map={r"x": BLUE})',
            },
        },
        {
            "segment_id": "seg-2",
            "content": {
                "scene_code": 'MathTex(r"x", tex_to_color_map={r"x": BLUE})',
            },
        },
    ])

    assert finding.status == "pass"
    assert finding.issues == []
