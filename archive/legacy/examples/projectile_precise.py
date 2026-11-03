"""Terminology-only revision of the complete, paced projectile animation.

All diagrams, motion routes, measured focus windows and physical clocks inherit
the approved paced scene. This scene owns only display-language substitutions;
the lead owns fresh media, independent review, narration and caption release.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = sys.argv[:1]
    from projectile_paced import PacedLesson
finally:
    sys.argv = _host_argv
del _host_argv


DISPLAY_TERMS = {
    "横速改变了什么？": "水平速度改变了什么？",
    "同高度 · 横速 ×2": "同一高度 · 水平速度 ×2",
    "同横速 · 高度 ×4": "相同水平速度 · 高度 ×4",
    "横向初速度": "水平速度",
    "同一段时间，横向走多远？": "相同时间内，水平位移有多大？",
    "同一时刻，接上不同的横向位移": "同一时刻，接上不同的水平位移",
    "横向展开不是实际运动": "水平展开仅用于位置分解",
}


def display_term(text):
    return DISPLAY_TERMS.get(text, text)


class PreciseLesson(PacedLesson):
    def cn(self, text, size=32, color="#EEF1F4"):
        return super().cn(display_term(text), size=size, color=color)
