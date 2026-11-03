"""Mock only TeX compilation/selection; exercise native GL animations/cleanup.

Rendering-owner follow-up: compile the five authored y/h/g/t/T states using
basic_ctex, check native occurrence counts (two `2`s until the last state),
and inspect intermediate frames plus the scene's final target-only membership.
These tests do not claim to validate real LaTeX/SVG glyph ordering or pixels.
"""

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


motion = pytest.importorskip("manimind.components.formula_motion")

from manimlib.animation.fading import FadeInFromPoint, FadeOutToPoint
from manimlib.animation.transform import Transform
from manimlib.animation.transform_matching_parts import TransformMatchingParts
from manimlib.mobject.geometry import Rectangle
from manimlib.mobject.svg.tex_mobject import Tex
from manimlib.mobject.types.vectorized_mobject import VGroup, VMobject
from manimlib.scene.scene import Scene
from manimlib.utils.color import color_to_hex


@pytest.fixture
def native_tex(monkeypatch):
    calls = []

    def initialize(self, latex, *, isolate, font_size, template, **kwargs):
        VMobject.__init__(self)
        self.string = self.tex_string = latex
        self.font_size, self.template = font_size, template
        self._fake_config = {"isolate": list(isolate), **kwargs}
        # Identical native shapes make accidental shape fallback detectable.
        self.add(*(Rectangle(width=.1, height=.2, fill_opacity=1, stroke_width=0).shift([index * .15, 0, 0])
                   for index in range(len(latex))))
        calls.append((latex, list(isolate), font_size, template, kwargs))

    def select(self, substring):
        if substring == "empty-rendered-part":
            return VGroup(VGroup())
        return VGroup(*(VGroup(*self.submobjects[match.start():match.end()])
                        for match in re.finditer(re.escape(substring), self.string)))

    monkeypatch.setattr(Tex, "__init__", initialize)
    monkeypatch.setattr(Tex, "get_parts_by_tex", select)
    return calls


def glyph_ids(part):
    return {id(glyph) for glyph in part.family_members_with_points()}


def test_optional_unmatched_syntax_fades_in_place_and_cleanup_is_target_only(native_tex):
    from manimlib.animation.fading import FadeIn, FadeOut
    source, target = formulas()
    animation = motion.matching_transform(source, target, unmatched_in_place=True)
    assert any(type(part) is FadeIn for part in animation.anims)
    assert any(type(part) is FadeOut for part in animation.anims)
    assert not any(isinstance(part, (FadeInFromPoint, FadeOutToPoint)) for part in animation.anims)
    fade = next(part for part in animation.anims if type(part) is FadeOut)
    centers = [glyph.get_center().copy() for glyph in fade.mobject.family_members_with_points()]
    animation.begin()
    animation.interpolate(.5)
    for glyph, center in zip(fade.mobject.family_members_with_points(), centers, strict=True):
        assert list(glyph.get_center()) == pytest.approx(list(center))
    scene = scene_without_renderer()
    scene.add(source)
    animation.finish()
    animation.clean_up_from_scene(scene)
    assert scene.mobjects == [target]


def test_in_place_option_cannot_be_an_ambiguous_truthy_value(native_tex):
    source, target = formulas()
    with pytest.raises(ValueError, match="boolean"):
        motion.matching_transform(source, target, unmatched_in_place="yes")


def formulas():
    source = motion.SemanticFormula("h=gt^2/2", tokens={"height": "h", "eq": "=", "gravity": "g", "time": "t",
                                                        "power": ("2", 0), "factor": ("2", 1)})
    target = motion.SemanticFormula("T=2h/g", tokens={"time": "T", "eq": "=", "factor": ("2", 0), "height": "h", "gravity": "g"})
    return source, target


def transforms(animation):
    return [part for part in animation.anims if type(part) is Transform]


def scene_without_renderer():
    scene = Scene.__new__(Scene)
    scene.mobjects = []
    scene.id_to_mobject_map = {}
    scene.assemble_render_groups = lambda: None
    return scene


def test_native_tex_subclass_and_isolation_deduplicate_literal_occurrences(native_tex):
    source, _ = formulas()
    assert isinstance(source, Tex)
    _, isolated, size, template, _ = native_tex[0]
    assert isolated == ["h", "=", "g", "t", "2"]
    assert size == 44 and template == "basic_ctex"
    assert source.semantic_ids == ("height", "eq", "gravity", "time", "power", "factor")
    assert glyph_ids(source.tag("power")) == glyph_ids(source.get_parts_by_tex("2")[0])
    assert glyph_ids(source.tag("factor")) == glyph_ids(source.get_parts_by_tex("2")[1])
    assert glyph_ids(source.tag("power")).isdisjoint(glyph_ids(source.tag("factor")))


def test_color_targets_one_semantic_occurrence_not_every_literal(native_tex):
    formula = motion.SemanticFormula("2+2", tokens={"power": ("2", 0), "factor": ("2", 1)},
                                     colors={"power": "#FF0000", "factor": "#00FF00"}, font_size=68)
    assert color_to_hex(formula.tag("power")[0].get_color()).upper() == "#FF0000"
    assert color_to_hex(formula.tag("factor")[0].get_color()).upper() == "#00FF00"
    assert formula.font_size == 68


@pytest.mark.parametrize("extra, expected", [("x", ["x"]), (["x", "y", "x"], ["x", "y"]),
                                             ((0, 1), ["x", (0, 1)])])
def test_extra_native_isolates_are_preserved_without_duplicates(native_tex, extra, expected):
    formula = motion.SemanticFormula("xy", tokens={"x": "x"}, isolate=extra, additional_preamble="fixture")
    assert formula._fake_config["isolate"] == expected
    assert native_tex[0][-1]["additional_preamble"] == "fixture"


@pytest.mark.parametrize("tokens", [{"ambiguous": "2"}, {"missing": "z"}, {"out_of_bounds": ("2", 2)},
                                     {"blank": "empty-rendered-part"}])
def test_ambiguous_absent_or_empty_parts_are_rejected(native_tex, tokens):
    with pytest.raises(ValueError):
        motion.SemanticFormula("2+2", tokens=tokens)


@pytest.mark.parametrize("tokens", [{"left": "g", "alias": "g"}, {"product": "gt", "time": "t"},
                                     {"first": ("2", 0), "alias": ("2", 0)}])
def test_distinct_semantic_tags_cannot_overlap_native_glyphs(native_tex, tokens):
    with pytest.raises(ValueError, match="overlap"):
        motion.SemanticFormula("gt+2", tokens=tokens)


@pytest.mark.parametrize("selector", ["", "  ", ("2", -1), ("2", True), ("2", 0.0), (2, 0),
                                       ("2", 0, 1), ["2", 0], None])
def test_selectors_must_be_explicit_valid_text_occurrences(native_tex, selector):
    with pytest.raises(ValueError):
        motion.SemanticFormula("2", tokens={"value": selector})
    assert not native_tex


@pytest.mark.parametrize("latex", [None, "", "  "])
def test_empty_formula_is_not_silently_replaced_by_tex(native_tex, latex):
    with pytest.raises(ValueError):
        motion.SemanticFormula(latex, tokens={})
    assert not native_tex


def test_unknown_color_and_unlabelled_svg_are_not_silent_fallbacks(native_tex):
    with pytest.raises(ValueError, match="declared"):
        motion.SemanticFormula("h", tokens={"height": "h"}, colors={"unknown": "#FFFFFF"})
    with pytest.raises(ValueError, match="labelled"):
        motion.SemanticFormula("h", tokens={"height": "h"}, use_labelled_svg=False)
    assert not native_tex


def test_tags_use_live_copied_glyphs_and_do_not_cache_source_wrappers(native_tex):
    original, _ = formulas()
    copied = original.copy().shift([2, 0, 0])
    assert glyph_ids(copied.tag("height")).isdisjoint(glyph_ids(original.tag("height")))
    assert glyph_ids(copied.tag("height")) <= glyph_ids(copied)
    assert copied.tag("height").get_center()[0] == pytest.approx(original.tag("height").get_center()[0] + 2)
    with pytest.raises(KeyError, match="Unknown semantic"):
        original.tag("not-a-tag")


def test_caller_token_edits_do_not_change_the_formula_identity_map(native_tex):
    tokens = {"height": "h"}
    formula = motion.SemanticFormula("h+g", tokens=tokens)
    tokens["height"] = "g"
    assert glyph_ids(formula.tag("height")) == glyph_ids(formula.get_parts_by_tex("h")[0])


def test_default_matches_common_ids_only_never_old_power_to_new_factor(native_tex):
    source, target = formulas()
    animation = motion.matching_transform(source, target, run_time=2.5, path_arc=.4, lag_ratio=.1)
    assert isinstance(animation, TransformMatchingParts)
    assert animation.run_time == 2.5 and animation.lag_ratio == .1
    matches = transforms(animation)
    assert len(matches) == 5
    expected_ids = [key for key in source.semantic_ids if key in target.semantic_ids]
    assert [glyph_ids(part.mobject) for part in matches] == [glyph_ids(source.tag(key)) for key in expected_ids]
    assert [glyph_ids(part.target_mobject) for part in matches] == [glyph_ids(target.tag(key)) for key in expected_ids]
    assert not any(glyph_ids(part.mobject) & glyph_ids(source.tag("power")) for part in matches)
    assert any(isinstance(part, FadeOutToPoint) and glyph_ids(part.mobject) == glyph_ids(source.tag("power"))
               for part in animation.anims)
    assert all(part.path_arc == .4 for part in animation.anims)


def test_explicit_pairs_replace_the_default_and_allow_intentional_renaming(native_tex):
    source = motion.SemanticFormula("t=2", tokens={"time": "t", "power": "2", "eq": "="})
    target = motion.SemanticFormula("T=2", tokens={"clock": "T", "factor": "2", "eq": "="})
    animation = motion.matching_transform(source, target, pairs={"time": "clock"})
    assert len(transforms(animation)) == 1
    assert glyph_ids(transforms(animation)[0].mobject) == glyph_ids(source.tag("time"))
    assert glyph_ids(transforms(animation)[0].target_mobject) == glyph_ids(target.tag("clock"))
    assert animation.find_pairs_with_matching_shapes(source.submobjects, target.submobjects) == []


def test_empty_pairs_fades_even_identical_shapes_and_text(native_tex):
    source, target = formulas()
    animation = motion.matching_transform(source, target, pairs=[])
    assert not transforms(animation)
    assert all(isinstance(part, (FadeOutToPoint, FadeInFromPoint)) for part in animation.anims)


@pytest.mark.parametrize("pairs", [[("missing", "height")], [("height", "missing")],
                                   [("height", "height"), ("height", "gravity")],
                                   [("height", "height"), ("gravity", "height")], ["height"], [("height",)]])
def test_invalid_or_many_to_one_pairs_are_rejected(native_tex, pairs):
    source, target = formulas()
    with pytest.raises(ValueError):
        motion.matching_transform(source, target, pairs=pairs)


@pytest.mark.parametrize("override", ["matched_pairs", "matched_keys", "key_map"])
def test_native_matching_overrides_cannot_bypass_semantic_ids(native_tex, override):
    source, target = formulas()
    with pytest.raises(ValueError, match="semantic pairs"):
        motion.matching_transform(source, target, **{override: []})


def test_shared_source_target_is_rejected(native_tex):
    source, _ = formulas()
    with pytest.raises(ValueError, match="separate"):
        motion.matching_transform(source, source)


def test_native_lifecycle_removes_old_formula_without_double_exposure(native_tex):
    source, target = formulas()
    background = Rectangle()
    scene = scene_without_renderer()
    scene.add(background, source)
    animation = motion.matching_transform(source, target, path_arc=.3)
    assert type(animation).clean_up_from_scene is TransformMatchingParts.clean_up_from_scene
    scene.begin_animations([animation])
    animation.interpolate(.5)
    animation.finish()
    animation.clean_up_from_scene(scene)
    assert scene.mobjects == [background, target]
    assert not any(glyph_ids(source) & glyph_ids(obj) for obj in scene.mobjects)


def test_no_common_ids_still_uses_native_fades_and_target_cleanup(native_tex):
    source = motion.SemanticFormula("2", tokens={"power": "2"})
    target = motion.SemanticFormula("2", tokens={"factor": "2"})
    scene = scene_without_renderer()
    scene.add(source)
    animation = motion.matching_transform(source, target)
    assert not transforms(animation)
    scene.begin_animations([animation])
    animation.finish()
    animation.clean_up_from_scene(scene)
    assert scene.mobjects == [target]


def test_real_native_import_preserves_unrelated_host_cli_arguments():
    command = """
import json, sys
sys.argv = ['host', '--not-a-manimgl-option', 'leave-this-alone']
original = sys.argv
from manimind.components.formula_motion import SemanticFormula
from manimlib import Tex, __version__
assert sys.argv is original
print(json.dumps({'argv': sys.argv, 'native': issubclass(SemanticFormula, Tex), 'version': __version__}))
"""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-B", "-c", command], cwd=root, capture_output=True, text=True, check=True)
    value = json.loads(result.stdout.strip().splitlines()[-1])
    assert value == {"argv": ["host", "--not-a-manimgl-option", "leave-this-alone"], "native": True, "version": "1.7.2"}
