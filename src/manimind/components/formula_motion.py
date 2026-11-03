"""Semantic identities over native ManimGL 1.7.2 vector Tex and transforms.

Tokens are authored selectors, not inferred algebra. A bare selector must select
one rendered part; repeated literals require (selector, zero_based_occurrence).
For example, tokens={"power": ("2", 0), "factor": ("2", 1)} distinguishes the
exponent from the denominator in y=h-\\frac{gt^2}{2}. Colors address semantic IDs.

Use scene.play(matching_transform(source, target, path_arc=...)); keep target as
the next formula. Unmapped glyphs fade through the native animation, and native
cleanup replaces the source with target. No same-shape or same-text fallback is
allowed to invent identity matches. Explicit pairs may rename semantic IDs.

Selectors live only on their formula, written at construction and consumed by
tag/transform. Move, scale and native copy are supported; rebuild the formula
after replacing its LaTeX or glyph structure. No glyph wrappers are cached,
because ManimGL's shallow-copy machinery would retain references to old glyphs.

Real-TeX verification for the rendering owner: compile all five algebra states
with basic_ctex, assert len(get_parts_by_tex("2")), inspect power/factor colors,
then play the chain and check source glyphs are absent and only target remains.
This module supplies no scene template or alternative LaTeX renderer.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
import sys


# ManimGL reads CLI arguments on first import; do not consume the host CLI.
_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from manimlib.animation.transform_matching_parts import TransformMatchingParts
    from manimlib.animation.composition import AnimationGroup
    from manimlib.animation.fading import FadeIn, FadeOut
    from manimlib.animation.transform import Transform
    from manimlib.mobject.svg.tex_mobject import Tex
    from manimlib.mobject.types.vectorized_mobject import VGroup
finally:
    sys.argv = _host_argv
del _host_argv


__all__ = ["SemanticFormula", "matching_transform"]


class SemanticFormula(Tex):
    def __init__(self, latex, *, tokens, colors=None, font_size=44,
                 template="basic_ctex", **kwargs):
        if not isinstance(latex, str) or not latex.strip():
            raise ValueError("A nonempty native LaTeX formula is required")
        if not isinstance(tokens, Mapping):
            raise TypeError("tokens must map semantic IDs to selectors")
        selectors = {}
        for identity, selector in tokens.items():
            if not isinstance(identity, str) or not identity.strip():
                raise ValueError("Semantic IDs must be nonempty strings")
            if isinstance(selector, str):
                substring, occurrence = selector, None
            elif (isinstance(selector, tuple) and len(selector) == 2
                  and isinstance(selector[0], str) and type(selector[1]) is int and selector[1] >= 0):
                substring, occurrence = selector
            else:
                raise ValueError(f"Invalid token {identity!r}; use text or (text, nonnegative occurrence)")
            if not substring.strip():
                raise ValueError(f"Empty selector for {identity!r}")
            selectors[identity] = (substring, occurrence)
        if colors is not None and not isinstance(colors, Mapping):
            raise TypeError("colors must map semantic IDs to native colors")
        colors = dict(colors or {})
        if colors.keys() - selectors.keys():
            raise ValueError("Colors must refer to declared semantic IDs")
        if kwargs.get("use_labelled_svg", True) is not True:
            raise ValueError("Semantic selection requires native labelled SVG")
        extra = kwargs.pop("isolate", [])
        if isinstance(extra, (str, re.Pattern)) or (
                isinstance(extra, tuple) and len(extra) == 2
                and all(value is None or type(value) is int for value in extra)):
            extra = [extra]
        isolated = []
        for selector in [*(value[0] for value in selectors.values()), *extra]:
            if selector not in isolated:
                isolated.append(selector)
        self._semantic_selectors = selectors
        self.semantic_ids = tuple(selectors)
        super().__init__(latex, isolate=isolated, font_size=font_size, template=template, **kwargs)
        parts = self._resolve_tags()
        for identity, color in colors.items():
            parts[identity].set_color(color)

    def _resolve_tags(self):
        parts, occupied = {}, {}
        for identity, (substring, occurrence) in self._semantic_selectors.items():
            matches = self.get_parts_by_tex(substring)
            if occurrence is None:
                if len(matches) != 1:
                    raise ValueError(f"Tag {identity!r}: {substring!r} selects {len(matches)} occurrences; specify (text, occurrence)")
                occurrence = 0
            if occurrence >= len(matches):
                raise ValueError(f"Tag {identity!r}: occurrence {occurrence} is absent for {substring!r}")
            part = matches[occurrence]
            glyphs = part.family_members_with_points()
            if not glyphs:
                raise ValueError(f"Tag {identity!r} selects no rendered glyphs")
            for glyph in glyphs:
                previous = occupied.get(id(glyph))
                if previous is not None:
                    raise ValueError(f"Tags {previous!r} and {identity!r} overlap on native glyphs")
                occupied[id(glyph)] = identity
            parts[identity] = part
        return parts

    def tag(self, identity):
        """Return the native occurrence group containing this formula's glyphs."""
        if identity not in self._semantic_selectors:
            raise KeyError(f"Unknown semantic ID: {identity!r}")
        return self._resolve_tags()[identity]


class _SemanticMatchingParts(TransformMatchingParts):
    def find_pairs_with_matching_shapes(self, chars1, chars2):
        return []


class _InPlaceSemanticParts(AnimationGroup):
    """Public native animations with stationary unmatched syntax, not a matcher."""

    def __init__(self, source, target, matched, *, run_time, path_arc, lag_ratio=0, **kwargs):
        self.source, self.target = source, target
        used_source = {id(glyph) for left, _ in matched for glyph in left.family_members_with_points()}
        used_target = {id(glyph) for _, right in matched for glyph in right.family_members_with_points()}
        self.anims = [Transform(left, right, path_arc=path_arc, **kwargs) for left, right in matched]
        remaining_source = VGroup(*(glyph for glyph in source.family_members_with_points() if id(glyph) not in used_source))
        remaining_target = VGroup(*(glyph for glyph in target.family_members_with_points() if id(glyph) not in used_target))
        if len(remaining_source):
            self.anims.append(FadeOut(remaining_source))
        if len(remaining_target):
            self.anims.append(FadeIn(remaining_target))
        super().__init__(*self.anims, run_time=run_time, lag_ratio=lag_ratio)

    def clean_up_from_scene(self, scene):
        super().clean_up_from_scene(scene)
        scene.remove(self.source, self.mobject, *(animation.mobject for animation in self.anims))
        scene.add(self.target)


def matching_transform(source, target, *, pairs=None, run_time=1, path_arc=0,
                       unmatched_in_place=False, **kwargs):
    """Native replacement transform using only explicit semantic matches.

    pairs=None matches common IDs in source order. An explicit mapping or an
    iterable of (source_id, target_id) pairs replaces that default, never adds
    fallback matches. Each endpoint may be used once; pairs=[] fades everything.
    unmatched_in_place=True fades unmatched syntax at its own position rather
    than using the native matcher's center-seeking fade. Default behavior stays
    unchanged for existing scenes. Remaining options go to native animations.
    """
    if not isinstance(source, SemanticFormula) or not isinstance(target, SemanticFormula):
        raise TypeError("Source and target must be SemanticFormula objects")
    if source is target or ({id(glyph) for glyph in source.family_members_with_points()}
                            & {id(glyph) for glyph in target.family_members_with_points()}):
        raise ValueError("Source and target must have separate native glyphs")
    if type(unmatched_in_place) is not bool:
        raise ValueError("unmatched_in_place must be a boolean")
    if {"matched_pairs", "matched_keys", "key_map"} & kwargs.keys():
        raise ValueError("Use semantic pairs rather than native matching overrides")
    source_parts, target_parts = source._resolve_tags(), target._resolve_tags()
    if pairs is None:
        pairs = [(identity, identity) for identity in source.semantic_ids if identity in target_parts]
    elif isinstance(pairs, Mapping):
        pairs = list(pairs.items())
    matched, used_source, used_target = [], set(), set()
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Each semantic pair must contain two IDs")
        left, right = pair
        if left not in source_parts or right not in target_parts:
            raise ValueError(f"Unknown semantic pair: {pair!r}")
        if left in used_source or right in used_target:
            raise ValueError("Semantic pairs must be one-to-one")
        used_source.add(left)
        used_target.add(right)
        matched.append((source_parts[left], target_parts[right]))
    if unmatched_in_place:
        return _InPlaceSemanticParts(source, target, matched, run_time=run_time, path_arc=path_arc, **kwargs)
    return _SemanticMatchingParts(source, target, matched_pairs=matched,
                                  run_time=run_time, path_arc=path_arc, **kwargs)
