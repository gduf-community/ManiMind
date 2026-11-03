"""Positive-narration case wrappers; inherited geometry and clocks stay intact.

The lead must include every eager import below in plan.sources. This declaration
is not automatic dependency registration. Each
class changes display strings only; inherited cue/focus IDs remain stable.
"""

from wave_formation_visual import WaveFormationLesson
from wave_reading_visual import WaveReadingLesson
from wave_superposition_visual import WaveSuperpositionLesson


PLAN_REQUIRED_SOURCES = (
    "examples/wave_formation_visual.py",
    "examples/wave_reading_visual.py",
    "examples/wave_superposition_visual.py",
    "examples/wave_unit_shared.py",
    "examples/wave_unit_model.py",
)
PLAN_SOURCE_DEPENDENCIES = {
    name: PLAN_REQUIRED_SOURCES for name in (
        "WaveFormationPositiveLesson",
        "WaveReadingPositiveLesson",
        "WaveSuperpositionPositiveLesson",
    )
}


class _PositiveDisplayText:
    label_replacements = {}
    title_replacements = {}

    def label(self, text, *args, **kwargs):
        return super().label(self.label_replacements.get(text, text), *args, **kwargs)

    def title(self, text):
        return super().title(self.title_replacements.get(text, text))


class WaveFormationPositiveLesson(_PositiveDisplayText, WaveFormationLesson):
    title_replacements = {
        "波峰向前，质点呢？": "质点上下振动，波峰向前传播",
        "后一处，稍后重复同一个状态": "沿着升降过程，看两处的传播延迟",
        "过一个周期：谁回原处，谁前进？": "一个周期：质点复位，波峰前进",
    }
    label_replacements = {
        "绷紧的长绳，小幅横向振动；先看反射返回之前": "绷紧的长绳，小幅横向振动；观察反射返回前的一段",
        "同一状态到达另一位置，不是同一个质点走过去": "各处依次重复升降，振动沿绳传播",
        "同一段时间，不同的运动": "四秒：质点完成一轮，波峰前进四米",
        "波峰再向右 1 m，质点也会向右 1 m 吗？": "再过 1 s，分别观察黄色质点与绿环的位置",
    }


class WaveReadingPositiveLesson(_PositiveDisplayText, WaveReadingLesson):
    title_replacements = {
        "先看横轴，再读重复的距离": "空间重复的距离，时间重复的间隔",
    }
    label_replacements = {
        "全绳的一张快照，还是一个质点的轨迹？": "把同一时刻各处的位移连起来，会得到什么？",
        "全绳的空间快照，不是一个质点的运动轨迹": "空间快照：这一时刻，各处位移的分布",
        "空间向右变低，为什么这里却向上？": "对照原来斜坡，看同一位置的位移怎样变化",
    }


class WaveSuperpositionPositiveLesson(_PositiveDisplayText, WaveSuperpositionLesson):
    title_replacements = {
        "两个脉冲相遇，会反弹吗？": "两个脉冲相遇时，绳形怎样变化？",
        "一上一下，平直的一刻意味着消失吗？": "一上一下：相消时的位移与速度",
    }
    label_replacements = {
        "均匀长绳，小幅扰动；相遇期间没有边界反射": "均匀长绳，小幅扰动；观察边界反射到达前的相遇",
    }
