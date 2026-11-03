"""Local pacing revision; frozen drawing code and physical clocks stay intact.

The lead owns render, contract, independent review, V01 speech and release.
Offsets, step cursors and pending local plays live only in one chapter/scene;
runtime samplers write evidence during animation, never reconstructed events.
"""

import json
import sys

_host_argv = sys.argv
try:
    sys.argv = sys.argv[:1]
    from manimlib import *
    from projectile_integrated import IntegratedLesson, LEGACY_CUE_BOUNDARIES
    from projectile_formula_motion_full import FullFormulaLesson
    from projectile_formula_motion import _LandingChapter
    from manimind.experiments.understanding_support import UnderstandingScene
finally:
    sys.argv = _host_argv
del _host_argv


# Checked against the frame-stepped inherited control flow, not a playback rate.
CUE_BOUNDARIES = (0, 18, 57.2, 79.2, 118.7, 161.2, 185.2, 252.8, 272.8, 305.8)
HEIGHT_FOCI = ("height_substitution", "root_split", "root_four_evaluated",
               "original_time_identified", "range_time_substitution",
               "range_factor_extracted", "original_range_identified")
LANDING_STEPS = {
    "ground_condition": ("landing_ground_condition", (2.,), 2.8),
    "relocated_term": ("landing_relocate", (.5, 1., .5), 2.8),
    "twice_height": ("landing_multiply_two", (.45, .7, .45), 2.6),
    "isolated_square": ("landing_divide_gravity", (.5, .8, .5), 2.6),
    "positive_root": ("landing_positive_root", (2.2,), 3.4),
}


class PacedLandingChapter(_LandingChapter):
    """Reuse the complete portable play; change only local waits/transitions."""

    def __init__(self, scene, start):
        super().__init__(scene, start)
        self.extra = 0.

    def until(self, local):
        self.scene.until(self.start + local + self.extra)
        if local == 14.4:
            self.scene._read("landing_numeric_check")

    def transition(self, target, stage, groups, **kwargs):
        identity, durations, hold = LANDING_STEPS[stage]
        original = sum(kwargs["durations"])
        kwargs["durations"] = durations
        begin = float(self.scene.get_time())
        self.scene._paced_step(identity, original,
            lambda _: super(PacedLandingChapter, self).transition(target, stage, groups, **kwargs),
            motion=sum(durations), hold=hold)
        self.extra += float(self.scene.get_time()) - begin - original

    def write_report(self):
        # The parent's report fixes duration=20; retain its actual samples, not
        # that obsolete clock or a file rewritten after the fact.
        pairs = [pair for sample in self.samples for pair in sample["pairs"]]
        moving = [sample["moving"] for sample in self.samples if "moving" in sample]
        violations = [pair for pair in pairs if pair["overlap"] or
            (pair["corridor_required"] is not None and
             pair["corridor_clearance"] < pair["corridor_required"] - 1e-5)]
        report = {
            "start": self.start, "duration": float(self.scene.get_time()) - self.start,
            "samples": self.samples, "routes": self.routes,
            "summary": {"pair_violations": len(violations),
                "opacity_violations": sum(row["opacity"]["min"] < .98 for row in moving),
                "title_violations": sum(row["title_clearance"] < .02 for row in moving),
                "moving_opacity_min": min((row["opacity"]["min"] for row in moving), default=None),
                "title_clearance_min": min((row["title_clearance"] for row in moving), default=None)},
            "writer": "PacedLandingChapter live native frame sampler",
            "consumers": ["independent pixel reviewer", "lead regression gate"],
            "lifecycle": "One actual landing chapter, driver removed in finally",
            "invalidation": "Any source, TeX, geometry, timing, plan or media change",
            "limitations": "Geometry is not pixel review or speech approval"}
        with (self.scene.out / "motion-samples.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)


class PacedLesson(IntegratedLesson):
    def setup(self):
        super().setup()
        self._direct_steps = []
        self._expansion_plays = []

    def _read(self, identity):
        if identity in {"vertical_equations", "landing_algebra", "height_scaling_chain", "range_products"}:
            return
        super()._read(identity)

    def _paced_step(self, identity, original, action, *, motion=1.8, hold=2.4):
        self._read(identity)
        begin = float(self.get_time())
        self._event("paced_step_begin", focus=identity, motion=motion, hold=hold)
        action(motion)
        self.mark(identity + "_ready")
        self.wait(hold)
        self._event("paced_step_end", focus=identity)
        if self._legacy_offset is not None:
            self._legacy_extra += float(self.get_time()) - begin - original
        self._close_focus()

    def _hold_legacy(self, duration):
        begin = float(self.get_time())
        self.wait(duration)
        self._legacy_extra += float(self.get_time()) - begin

    def until(self, absolute_seconds, *animations, **kwargs):
        if self._chapter_id == "conclusion" and absolute_seconds == 114:
            absolute_seconds += .8
        if self._chapter_id == "height" and absolute_seconds == 102 and self._legacy_offset is not None:
            # Bypass IntegratedLesson's old forced 48-second height ending.
            target = absolute_seconds + self._legacy_offset + self._legacy_extra
            UnderstandingScene.until(self, target, *animations, **kwargs)
        else:
            super().until(absolute_seconds, *animations, **kwargs)
        if self._chapter_id == "horizontal" and absolute_seconds == 67.3:
            self._direct_steps = [("horizontal_ruler_translation", 1.1, 1.8, 2.4)]

    def mark(self, identity):
        super().mark(identity)
        if identity == "equal_gravity_visible":
            self._hold_legacy(3.)
        elif identity == "height_prediction_ready":
            self._hold_legacy(2.)
        elif identity == "low_ball_landed_high_ball_flying":
            self._hold_legacy(3.)
        elif identity in {"fixed_height_relation_highlighted", "height_relation_highlighted"}:
            self._hold_legacy(4.)

    def _event(self, kind, **data):
        super()._event(kind, **data)
        if kind == "substitute_products_begin":
            self._direct_steps = [("horizontal_product_blue", .4, 1.8, 2.6),
                                  ("horizontal_product_orange", .4, 1.6, 1.6)]
        elif kind == "substitute_products_end":
            if self._direct_steps:
                raise ValueError("Both numerical product moves must execute")
        elif kind == "time_correspondence":
            self._read("final_time_correspondence")
            self._hold_legacy(4.2)

    def play(self, *animations, run_time=None, **kwargs):
        parent = super().play
        if self._direct_steps:
            identity, original, motion, hold = self._direct_steps.pop(0)
            if abs(run_time - original) > 1e-6:
                raise ValueError("Local pacing hook no longer matches frozen play")
            return self._paced_step(identity, original,
                lambda seconds: parent(*animations, run_time=seconds, **kwargs), motion=motion, hold=hold)
        if self._expansion_plays:
            original, seconds = self._expansion_plays.pop(0)
            if abs(run_time - original) > 1e-6:
                raise ValueError("Local radical expansion hook changed")
            run_time = seconds
        return parent(*animations, run_time=run_time, **kwargs)

    def _show(self, name, formula, root, duration=.4, *extra):
        identity = {"vertical": "vertical_general", "range_ratio": "horizontal_speed_ratio"}.get(name)
        if identity:
            return self._paced_step(identity, duration,
                lambda seconds: FullFormulaLesson._show(self, name, formula, root, seconds, *extra),
                motion=duration, hold=4.2 if name == "vertical" else 2.6)
        return super()._show(name, formula, root, duration, *extra)

    def _height_algebra(self, root):
        if self.get_time() < self._legacy_offset + self._legacy_extra + 90.4 - 1e-5:
            raise ValueError("Keep both full-size landing results before algebra")
        self._direct_steps = [("height_laws", .4, .8, 4.2)]
        FullFormulaLesson._height_algebra(self, root)

    def _height_transition(self, original_duration, action):
        identity = HEIGHT_FOCI[self._height_step]
        self._height_step += 1
        self._paced_step(identity, original_duration, action)

    def _morph(self, name, target, root, duration, operation, *, arc=0, extra=()):
        parent = lambda seconds: FullFormulaLesson._morph(
            self, name, target, root, seconds, operation, arc=arc, extra=extra)
        if self._chapter_id == "height" and name in {"height_time", "height_range"}:
            return self._height_transition(duration, parent)
        if self._chapter_id == "vertical" and name == "vertical":
            identity = ("vertical_initial_substitution" if "{0}{t}" in target.get_tex() else
                        "vertical_zero_removed" if "{g}{t}" in target.get_tex() else "vertical_equal_positions")
            motion, hold = {"vertical_initial_substitution": (2., 3.2),
                            "vertical_zero_removed": (2., 2.6),
                            "vertical_equal_positions": (1.8, 2.4)}[identity]
            return self._paced_step(identity, duration, parent, motion=motion, hold=hold)
        if self._chapter_id == "horizontal":
            if name in {"range1", "range2"}:
                suffix = "blue" if name == "range1" else "orange"
                motion, hold = (1.8, 2.4) if name == "range1" else (1.6, 1.6)
                return self._paced_step("horizontal_units_" + suffix, duration, parent, motion=motion, hold=hold)
            identity = {"range": "horizontal_range_law", "range_ratio": "horizontal_ratio_result"}.get(name)
            if identity:
                return self._paced_step(identity, duration, parent)
        return super()._morph(name, target, root, duration, operation, arc=arc, extra=extra)

    def _merge(self, name, target, root, sources, duration, operation, *, consume=(), arc=0, paths=None):
        parent = lambda seconds: FullFormulaLesson._merge(self, name, target, root, sources, seconds,
            operation, consume=consume, arc=arc, paths=paths)
        if self._chapter_id == "height" and name in {"height_time", "height_range"}:
            return self._height_transition(duration, parent)
        if self._chapter_id == "conclusion" and name == "final_range":
            return self._paced_step("final_time_transport", duration, parent)
        return super()._merge(name, target, root, sources, duration, operation,
                             consume=consume, arc=arc, paths=paths)

    def _expand_time_here(self, target, root):
        self._expansion_plays = [(.2, .4), (.4, 1.8)]
        try:
            self._paced_step("final_radical_expansion", .6,
                lambda _: FullFormulaLesson._expand_time_here(self, target, root), motion=2.2, hold=2.6)
            if self._expansion_plays:
                raise ValueError("Both local radical expansion plays must execute")
        finally:
            self._expansion_plays = []

    def _transfer(self):
        start = float(self.get_time())
        self._chapter_id = "transfer"
        root = Group(self.heading(8, "换成45米，先想时间，再想射程"),
            self.tex(r"h:5\to45\,\mathrm m\qquad v_x=4\,\mathrm{m/s}", 0, 1.85, 41, width=11),
            self.tex(r"T:\ 1\,\mathrm s\to\ ?\qquad R:\ 4\,\mathrm m\to\ ?", 0, .4, 43, width=11))
        self.page(root)
        self.mark("ninefold_question_ready")
        self._read("ninefold_prediction")
        self.until(start + 5)
        self.mark("prediction_pause_started")
        self._read("prediction_space")
        self.until(start + 7)
        evaluated = self._formula(r"T'=\sqrt{\frac{2\cdot45}{10}}=3\,\mathrm s",
            {"new_time": "T'", "eq": ("=", 0)}, 0, -1., size=41, width=10)
        self._paced_step("ninefold_time_check", .8,
            lambda seconds: FullFormulaLesson._show(self, "transfer_time", evaluated, root, seconds), motion=.8, hold=4.2)
        answer = self._formula(r"R'=4\,\mathrm{m/s}\times3\,\mathrm s=12\,\mathrm m",
            {"new_range": "R'", "eq": ("=", 0)}, 0, -2.3, size=39, width=11)
        self._paced_step("ninefold_range_check", .8,
            lambda seconds: FullFormulaLesson._show(self, "transfer_range", answer, root, seconds), motion=.8, hold=4.2)
        self.mark("ninefold_answer_ready")
        self._read("ninefold_check")
        self.until(start + 20)
        self._close_focus()

    def construct(self):
        self.current_page = None
        self.add(Rectangle(width=14.3, height=8.1, fill_color=self.BG, fill_opacity=1, stroke_width=0))
        self._legacy_chapter("opening", 0, self._opening)
        self._legacy_chapter("vertical", 18, self._vertical)
        self._clear_formulas()
        self._recombine()
        self._chapter_id = "landing"
        chapter = PacedLandingChapter(self, self.get_time())
        try:
            self.current_page = chapter.play(self.current_page)
        finally:
            chapter.driver.clear_updaters()
            self.remove(chapter.driver)
            chapter.write_report()
        self._close_focus()
        self._legacy_chapter("horizontal", 58, self._horizontal)
        self._clear_formulas()
        self._height_steps()
        self._legacy_chapter("height", 74, self._height)
        self._clear_formulas()
        self._transfer()
        self._clear_formulas()
        self._legacy_chapter("conclusion", 102, self._conclusion)
        self._event("complete", duration=float(self.get_time()))

    def tear_down(self):
        self._close_focus()
        report = {"schema_version": 1, "duration": float(self.get_time()),
            "cue_boundaries": CUE_BOUNDARIES, "source_cue_boundaries": LEGACY_CUE_BOUNDARIES,
            "baseline_cue_boundaries": (0, 18, 38, 60, 80, 96, 120, 168, 182, 194),
            "events": self.full_formula_events, "samples": self.full_formula_frames,
            "writer": "PacedLesson actual runtime and native frame samplers",
            "consumers": ["independent pixel reviewer", "regression reviewer", "lead narrator"],
            "lifecycle": "This exact scene execution; portable landing logged separately",
            "invalidation": "Source, dependencies, plan, contract, TeX, timing or media change",
            "limitations": "Sampling is not rendered-pixel review, listening review or approval"}
        with (self.out / "full-formula-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        UnderstandingScene.tear_down(self)
