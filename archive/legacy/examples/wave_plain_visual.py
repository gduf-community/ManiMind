"""Plain-language display cases inheriting frozen positive wrappers.

Only exact original-source display keys change. Geometry, clocks, durations and
focus methods stay inherited. The lead must add the declared eager-import
dependencies to plan.sources; declarations do not register themselves.
"""

from wave_positive_visual import (
    PLAN_REQUIRED_SOURCES as POSITIVE_REQUIRED_SOURCES,
    WaveFormationPositiveLesson,
    WaveReadingPositiveLesson,
    WaveSuperpositionPositiveLesson,
)


PLAN_REQUIRED_SOURCES = (
    "examples/wave_positive_visual.py",
    *POSITIVE_REQUIRED_SOURCES,
)
PLAN_SOURCE_DEPENDENCIES = {
    name: PLAN_REQUIRED_SOURCES for name in (
        "WaveFormationPlainLesson",
        "WaveReadingPlainLesson",
        "WaveSuperpositionPlainLesson",
    )
}


class WaveFormationPlainLesson(WaveFormationPositiveLesson):
    title_replacements = {
        **WaveFormationPositiveLesson.title_replacements,
        "扰动怎样到达邻处？": "绳上的起伏怎样传到旁边？",
        "后一处，稍后重复同一个状态": "同样一段升降，后面晚两秒",
        "过一个周期：谁回原处，谁前进？": "一个周期：质点回到起点，波峰前进",
    }
    label_replacements = {
        **WaveFormationPositiveLesson.label_replacements,
        "局部形变通过相邻部分的相互作用传下去": "一小段绳上下动，带动旁边的一小段",
        "同一状态到达另一位置，不是同一个质点走过去": "后一处晚两秒重复这段升降",
        "质点：回到原来的状态": "质点：完成一轮，回到起点",
        "状态：向前传播": "起伏：沿绳向前传",
    }


class WaveReadingPlainLesson(WaveReadingPositiveLesson):
    title_replacements = {
        **WaveReadingPositiveLesson.title_replacements,
        "空间快照：相邻同相位点相隔多远？": "同一时刻，相邻两个波峰相隔多远？",
        "先看横轴，再读重复的距离": "两张图，分别读出波长和周期",
    }
    label_replacements = {
        **WaveReadingPositiveLesson.label_replacements,
        "从这张已建立的波形重新计时：t = 0": "接着眼前的波形，从 t = 0 重新计时",
        "全绳的空间快照，不是一个质点的运动轨迹": "同一时刻：绳上各处的位移",
        "空间向右变低，为什么这里却向上？": "对照灰线，五米处的位移怎样变？",
    }


class WaveSuperpositionPlainLesson(WaveSuperpositionPositiveLesson):
    title_replacements = {
        **WaveSuperpositionPositiveLesson.title_replacements,
    }
    label_replacements = {
        **WaveSuperpositionPositiveLesson.label_replacements,
        "同处同时：实际位移仍是两分量之和": "同一处、同一刻：两个分量的位移相加",
    }
