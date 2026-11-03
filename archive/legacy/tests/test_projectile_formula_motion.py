"""Focused native geometry/sampler tests, without rendering a lesson or TeX."""

import importlib.util
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("landing_chapter_test_module", ROOT / "examples" / "projectile_formula_motion.py")
landing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(landing)


def test_actual_image_mobject_uses_native_opacity_without_vector_getters(tmp_path):
    path = tmp_path / "caption.png"
    Image.new("RGBA", (8, 4), (255, 255, 255, 255)).save(path)
    image = landing.ImageMobject(str(path)).set_opacity(.4)
    result = landing._opacity(image)
    assert result == pytest.approx({"min": .4, "max": .4})
    image.set_opacity(0)
    assert landing._opacity(image) == {"min": 0, "max": 0}


def test_mixed_native_header_group_reports_images_and_vectors(tmp_path):
    path = tmp_path / "caption.png"
    Image.new("RGBA", (8, 4), (255, 255, 255, 255)).save(path)
    image = landing.ImageMobject(str(path)).set_opacity(.35)
    line = landing.Line([-1, 0, 0], [1, 0, 0], stroke_opacity=.8)
    result = landing._opacity(landing.Group(image, line))
    assert result["min"] == pytest.approx(.35)
    assert result["max"] == pytest.approx(.8)


def test_stroke_width_zero_does_not_make_faded_vector_appear_visible():
    glyph = landing.Rectangle(fill_opacity=0, stroke_width=0, stroke_opacity=1)
    assert landing._opacity(glyph) == {"min": 0, "max": 0}


def test_empty_native_group_opacity_is_zero():
    assert landing._opacity(landing.Group()) == {"min": 0, "max": 0}


def test_full_term_three_phase_route_is_visible_and_clears_fixed_h_and_eq():
    source = np.array([[3.55, -.75, 0], [4.85, .85, 0]])
    target = np.array([[-.25, -.75, 0], [1.05, .85, 0]])
    obstacles = [[2.175, 2.625, -.3, .4], [1.375, 1.825, -.15, .25]]
    source_box = [source[0, 0], source[1, 0], source[0, 1], source[1, 1]]
    target_box = [target[0, 0], target[1, 0], target[0, 1], target[1, 1]]
    lane = landing._lane(source_box, target_box, obstacles, "above")
    phases = []
    path = landing._lane_path(source.mean(axis=0), target.mean(axis=0), lane, (.2, .45, .25), phases.append)
    for elapsed in np.linspace(0, .9, 181):
        points = path(source, target, elapsed / .9)
        box = [points[:, 0].min(), points[:, 0].max(), points[:, 1].min(), points[:, 1].max()]
        assert box[3] < landing.TITLE_Y
        for obstacle in obstacles:
            assert not landing._overlap(box, obstacle)
            if phases[-1] == "across":
                assert box[2] - obstacle[3] >= landing.CORRIDOR_GAP - 1e-8
    np.testing.assert_allclose(path(source, target, 0), source)
    np.testing.assert_allclose(path(source, target, 1), target)
    assert {"lift", "across", "settle"} <= set(phases)


@pytest.mark.parametrize("durations", [(.18, .34, .18), (.2, .35, .25)])
def test_factor_and_gravity_move_in_a_separate_lower_corridor(durations):
    source = np.array([[-1.5, -.75, 0], [-1.1, -.15, 0]])
    target = np.array([[.5, -.3, 0], [.9, .3, 0]])
    obstacles = [[-.9, -.3, -.3, .8], [1.1, 1.6, -.3, .3], [-.2, .2, -.1, .1]]
    lane = landing._lane([-1.5, -1.1, -.75, -.15], [.5, .9, -.3, .3], obstacles, "below")
    phases = []
    path = landing._lane_path(source.mean(axis=0), target.mean(axis=0), lane, durations, phases.append)
    for alpha in np.linspace(0, 1, 121):
        points = path(source, target, alpha)
        box = [points[:, 0].min(), points[:, 0].max(), points[:, 1].min(), points[:, 1].max()]
        for obstacle in obstacles:
            assert not landing._overlap(box, obstacle)
            if phases[-1] == "across":
                assert obstacle[2] - box[3] >= landing.CORRIDOR_GAP - 1e-8


def test_title_line_is_a_hard_route_bound():
    with pytest.raises(ValueError, match="title"):
        landing._lane([3, 4, -1, 1], [-1, 0, -1, 1], [[1, 2, 0, 1.5]], "above")


def test_all_chapter_until_calls_use_the_absolute_start(tmp_path):
    targets = []
    scene = SimpleNamespace(out=tmp_path, until=targets.append)
    chapter = landing._LandingChapter(scene, 38)
    for local in (1, 3, 8.3, 11.7, 13.6, 14.4, 20):
        chapter.until(local)
    assert targets == pytest.approx([39, 41, 46.3, 49.7, 51.6, 52.4, 58])


def test_composable_entry_does_not_replace_caller_methods_or_chapter_fields(tmp_path, monkeypatch):
    class Caller:
        def __init__(self):
            self.out, self.time, self.objects = tmp_path, 38., []
            self.current_page = landing.Group()
            self.active_formula, self.stage, self.motion_samples = "other chapter", "untouched", ["old"]

        def get_time(self):
            return self.time

        def add(self, *objects):
            self.objects.extend(objects)

        def remove(self, *objects):
            self.objects = [obj for obj in self.objects if obj not in objects]

        def update_mobjects(self, dt):
            return "caller sampling"

        def label(self):
            return "caller label"

        def equation(self):
            return "caller equation"

    seen = []
    page = landing.Group(landing.Rectangle())

    def play(chapter, previous):
        seen.append((chapter.start, previous))
        chapter.scene.add(chapter.driver)
        chapter.scene.time = chapter.start + 20
        chapter.scene.current_page = page
        return page

    monkeypatch.setattr(landing._LandingChapter, "play", play)
    scene = Caller()
    previous = scene.current_page
    original_methods = (scene.update_mobjects.__func__, scene.label.__func__, scene.equation.__func__)
    assert landing.play_landing_derivation(scene, start=38, previous_page=previous) is page
    assert seen == [(38, previous)] and scene.time == 58 and scene.current_page is page
    assert not scene.objects
    assert (scene.update_mobjects.__func__, scene.label.__func__, scene.equation.__func__) == original_methods
    assert (scene.active_formula, scene.stage, scene.motion_samples) == ("other chapter", "untouched", ["old"])
    assert read_report(tmp_path)["start"] == 38


def read_report(directory):
    return json.loads((directory / "motion-samples.json").read_text())


def test_report_is_create_only_and_does_not_overwrite_previous_evidence(tmp_path):
    chapter = landing._LandingChapter(SimpleNamespace(out=tmp_path), 0)
    chapter.write_report()
    previous = (tmp_path / "motion-samples.json").read_bytes()
    with pytest.raises(FileExistsError):
        chapter.write_report()
    assert (tmp_path / "motion-samples.json").read_bytes() == previous


def test_standalone_scene_is_only_a_composable_entry_delegate():
    source = inspect.getsource(landing.FormulaDerivation.construct)
    assert "play_landing_derivation(self)" in source
    assert "update_mobjects" not in landing.FormulaDerivation.__dict__
