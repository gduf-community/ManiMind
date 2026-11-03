"""Native geometry/cleanup checks, not a real-TeX or pixel approval."""

import numpy as np
import pytest

from test_formula_motion import native_tex, formulas, scene_without_renderer, transforms
from manimind.components.formula_transfer import copy_formula_transform


def test_copy_starts_at_the_actual_source_and_preserves_history(native_tex):
    source, target = formulas()
    source.shift([-2, 1, 0])
    target.shift([1, -2, 0])
    original = source.get_all_points().copy()
    animation = copy_formula_transform(source, target, run_time=2)
    assert animation.retained_source is source
    np.testing.assert_allclose(animation.source.get_all_points(), original)
    assert animation.source is not source
    parts = transforms(animation)
    start = parts[0].mobject.get_center().copy()
    end = parts[0].target_mobject.get_center().copy()
    assert not np.allclose(start, end)
    animation.begin()
    animation.interpolate(.5)
    middle = parts[0].mobject.get_center()
    assert not np.allclose(start, middle) and not np.allclose(end, middle)
    np.testing.assert_allclose(source.get_all_points(), original)
    scene = scene_without_renderer()
    scene.add(source, animation.source)
    animation.finish()
    animation.clean_up_from_scene(scene)
    assert source in scene.mobjects and target in scene.mobjects
    assert animation.source not in scene.mobjects
    np.testing.assert_allclose(source.get_all_points(), original)


def test_explicit_no_pairs_does_not_invent_symbol_matches(native_tex):
    source, target = formulas()
    animation = copy_formula_transform(source, target, pairs=[])
    assert not transforms(animation)


def test_copy_rejects_self_destination(native_tex):
    source, _ = formulas()
    with pytest.raises(ValueError, match="separate"):
        copy_formula_transform(source, source)
