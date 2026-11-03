"""Small native presentation helpers for new derivative-chapter lessons.

Each construct owns its cue, motion journal and current formula objects. The
scene writes actual events; reviewers consume them. Any source, timing, geometry
or wording change invalidates the journal. This supplies no review authority.
"""

import json
import sys

_argv = sys.argv
try:
    sys.argv = _argv[:1]
    from manimlib import FadeIn, FadeOut, Group, Transform, UpdateFromAlphaFunc
    from manimind.experiments.understanding_support import UnderstandingScene
    from manimind.components.formula_motion import SemanticFormula
finally:
    sys.argv = _argv
del _argv

INK = "#EEF1F4"
MUTED = "#A5AFB3"
CURVE = "#58CFA9"
RATE = "#F08D85"
ACCENT = "#F1CD68"
BG = "#101416"
H_COLOR = ACCENT
DERIVATIVE = RATE


class ChapterScene(UnderstandingScene):
    def setup(self):
        super().setup()
        self.camera.background_color = BG
        self.motion_samples = []
        self._cue = None

    def put(self, latex, x=0, y=0, size=40, color=INK, width=12.6):
        result = self.formula(latex, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def label(self, text, x=0, y=0, size=30, color=INK, width=12.6):
        result = self.cn(text, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def stage_time(self, fraction):
        if self._cue is None or not 0 <= fraction <= 1:
            raise ValueError("A beat belongs to an active cue")
        offset = self._cue.get("stage_times", {}).get(f"{fraction:.2f}", fraction*self._cue["duration"])
        if not 0 <= offset <= self._cue["duration"]:
            raise ValueError("Actual stage time must stay inside its cue")
        return self._cue["start"] + offset

    def beat(self, fraction, *animations, **kwargs):
        self.until(self.stage_time(fraction), *animations, **kwargs)

    def begin_chapter(self, cue):
        if self._open_focus:
            raise ValueError("The previous cue must close its measured referents")
        self._cue = cue
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        for obj in old:
            obj.clear_updaters()
        self.beat(.025, *(FadeOut(obj) for obj in old))
        self.beat(.06, FadeIn(self.label(cue["heading"], 0, 3.38, size=36)))

    def end_chapter(self):
        self.beat(1)
        for identity in tuple(self._open_focus):
            self.focus_end(identity)

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "time": float(self.get_time()), **values})

    def safe_formula(self, source, target, end, *, stage="formula", pairs=None):
        """Keep history intact; move explicit identities without crossfade layers.

        Authors choose the target row and semantic pairing. For expressions with
        order-changing terms, compose explicit native waypoint actions instead
        of asserting that a generic straight path is collision-free.
        """
        if not isinstance(source, SemanticFormula) or not isinstance(target, SemanticFormula):
            raise TypeError("Formula transfer requires native semantic formula objects")
        common = tuple(pairs or (key for key in source.semantic_ids if key in target.semantic_ids))
        moving = source.copy()
        moving.shift([target.get_left()[0]-moving.get_left()[0],
                      target.get_center()[1]-moving.get_center()[1], 0])
        left = {key: moving.tag(key) for key in common}
        occupied = {id(g) for key in common for g in moving.tag(key).family_members_with_points()}
        old_syntax = Group(*(g for g in moving.family_members_with_points() if id(g) not in occupied))
        occupied = {id(g) for key in common for g in target.tag(key).family_members_with_points()}
        new_syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in occupied))
        start, finish = float(self.get_time()), self.stage_time(end)
        span = finish-start
        if round(span*self.camera.fps) < 20:
            raise ValueError("A staged transfer needs actual animation frames")
        new_syntax.set_opacity(0)
        moving.set_opacity(0)
        self.add(moving)
        self.until(start+.25*span, UpdateFromAlphaFunc(moving, lambda mob, a: mob.set_opacity(a)))
        self.sample("formula_copy", stage=stage, source=source.get_tex(), time_end=float(self.get_time()))
        self.until(start+.40*span, UpdateFromAlphaFunc(moving, lambda _, a: old_syntax.set_opacity(1-a)))
        old_syntax.set_opacity(0)
        if common:
            self.until(start+.80*span, *(Transform(left[key], target.tag(key), path_arc=0) for key in common))
        else:
            self.until(start+.80*span)
        self.remove(moving, *left.values())
        self.add(target)
        self.until(finish, UpdateFromAlphaFunc(target, lambda _, a: new_syntax.set_opacity(a)))
        self.sample("formula_complete", stage=stage, target=target.get_tex())
        return target

    def tear_down(self):
        self.sample("lesson_end")
        (self.out / "chapter-motion.json").write_text(json.dumps({
            "events": self.motion_samples, "writer": "Actual ChapterScene runtime",
            "consumers": ["pixel reviewer", "timing reviewer"],
            "lifecycle": "This exact construct", "invalidation": "Source, timing, geometry or text changes"
        }, ensure_ascii=False), encoding="utf-8")
        super().tear_down()
