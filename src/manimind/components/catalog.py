"""Capabilities describe reusable visual objects, never a completed lesson."""

from pathlib import Path

VERSION = "0.1"
FONT = "PingFang SC"
FONT_PATH = Path("/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc")
FONT_INDEX, FONT_MEDIUM_INDEX, FONT_SEMIBOLD_INDEX = 3, 7, 11
NUMBER_FONT_PATH = Path("/System/Library/Fonts/HelveticaNeue.ttc")
NUMBER_FONT_INDEX = 0
COLORS = {"ink": "#E8EAED", "muted": "#A2A9B2", "cyan": "#72C9D8",
          "yellow": "#E8C476", "coral": "#E68D86", "green": "#94CDB3"}
CATALOG = {
    "axes": {"version": VERSION, "purpose": "带刻度与单位的二维坐标系", "layer": "component"},
    "curve": {"version": VERSION, "purpose": "安全表达式驱动的参数化函数曲线", "layer": "component"},
    "point": {"version": VERSION, "purpose": "绑定数学坐标的点", "layer": "component"},
    "segment": {"version": VERSION, "purpose": "绑定两个数学坐标的线段或辅助线", "layer": "component"},
    "vector": {"version": VERSION, "purpose": "从起点到终点的有向量", "layer": "component"},
    "formula": {"version": VERSION, "purpose": "由安全表达式生成的符号公式", "layer": "component"},
    "readout": {"version": VERSION, "purpose": "绑定同一数学状态的固定位置数值与单位", "layer": "component"},
}
PLANNED = ["number_line", "angle_arc", "riemann_sum", "probability_distribution",
           "formula_transform", "local_zoom", "matrix_transform", "circuit", "free_body_diagram"]


def catalog():
    return {"version": VERSION, "implemented": CATALOG, "planned_not_implemented": PLANNED,
            "legacy_patterns": {"scene_spec/renderer.py": "多项式割线/切线的组合演示，不是任意镜头",
                                "examples/instantaneous_velocity.py": "完整固定选题模板，不是通用组件"},
            "boundary": "Native ManimGL supplies drawing/animation. Components add typed bindings, layout and evidence. No model-specific code."}
