import math
import os
import shutil
from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("manimlib")

from PIL import Image, ImageFont
from manimlib import Dot, Group, ImageMobject

from manimind.components import typography
from manimind.components.catalog import (
    FONT_INDEX, FONT_PATH, FONT_SEMIBOLD_INDEX, NUMBER_FONT_INDEX, NUMBER_FONT_PATH,
)
from manimind.components.typography import RasterNumber, bitmap_colors, text_image


@pytest.fixture
def number_font():
    if not NUMBER_FONT_PATH.is_file():
        pytest.skip("The configured number font is not installed")
    return NUMBER_FONT_PATH


@pytest.fixture
def text_font():
    if not FONT_PATH.is_file():
        pytest.skip("The configured text TTC is not installed")
    return FONT_PATH


def test_text_index_has_distinct_font_and_asset_cache(tmp_path, text_font):
    typography._load_font.cache_clear()
    regular = text_image("Component 128", tmp_path, font_index=FONT_INDEX)
    first = typography._load_font.cache_info()
    again = text_image("Component 128", tmp_path, font_index=FONT_INDEX)
    assert typography._load_font.cache_info().hits == first.hits + 1
    bold = text_image("Component 128", tmp_path, font_index=FONT_SEMIBOLD_INDEX)
    assert regular.image_path == again.image_path
    assert regular.image_path != bold.image_path
    assert (regular.image.size, regular.image.tobytes()) != (bold.image.size, bold.image.tobytes())
    assert typography._load_font.cache_info().currsize == 2
    assert typography._load_font.cache_info().maxsize == 32
    assert text_image("Component 128", tmp_path).image_path == regular.image_path


def test_text_preserves_four_times_raster_and_explicit_assets(tmp_path, number_font):
    face = ImageFont.truetype(str(number_font), 96, index=NUMBER_FONT_INDEX)
    left, top, right, bottom = face.getbbox("12.34")
    obj = text_image("12.34", tmp_path, size=24, font_path=number_font,
                     font_index=NUMBER_FONT_INDEX)
    assert obj.image.size == (right - left + 4, bottom - top + 4)
    assert obj.get_height() == pytest.approx(obj.image.height / 400)
    assert Path(obj.image_path).is_relative_to(tmp_path)


def test_font_file_change_invalidates_font_and_bitmap(tmp_path, number_font):
    font = tmp_path / number_font.name
    shutil.copyfile(number_font, font)
    typography._load_font.cache_clear()
    first = text_image("128", tmp_path, font_path=font, font_index=NUMBER_FONT_INDEX)
    stat = font.stat()
    os.utime(font, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    second = text_image("128", tmp_path, font_path=font, font_index=NUMBER_FONT_INDEX)
    assert first.image_path != second.image_path
    assert typography._load_font.cache_info().misses == 2


@pytest.mark.parametrize("factory", [text_image, RasterNumber])
def test_relative_paths_are_rejected(tmp_path, number_font, factory):
    value = "12" if factory is text_image else 12
    with pytest.raises(ValueError, match="absolute"):
        factory(value, Path("relative"), font_path=number_font)
    with pytest.raises(ValueError, match="absolute"):
        factory(value, tmp_path, font_path=Path("font.ttc"))


def test_digits_have_equal_advance_and_share_baseline(tmp_path, number_font):
    obj = RasterNumber(1023456789, tmp_path, decimals=0, font_path=number_font)
    assert isinstance(obj, Group)
    assert obj.num_string == "1023456789"
    assert all(isinstance(glyph, ImageMobject) for glyph in obj)
    widths = [glyph.get_width() for glyph in obj]
    assert widths == pytest.approx([widths[0]] * 10)
    centers = [glyph.get_center() for glyph in obj]
    assert [center[1] for center in centers] == pytest.approx([centers[0][1]] * 10)
    assert [centers[i + 1][0] - centers[i][0] for i in range(9)] == pytest.approx(widths[:9])


def test_linebox_and_punctuation_use_real_font_metrics(tmp_path, number_font):
    obj = RasterNumber(-12.34, tmp_path, size=32, font_path=number_font)
    face = ImageFont.truetype(str(number_font), 128, index=NUMBER_FONT_INDEX)
    ascent, descent = face.getmetrics()
    line_height = ascent + descent + 4
    baseline = ascent + 2
    assert obj.get_height() == pytest.approx(line_height / 400)
    assert {glyph.image.height for glyph in obj} == {line_height}
    for char, glyph in zip(obj.num_string, obj):
        ink = glyph.image.getchannel("A").getbbox()
        mask, offset = face.getmask2(char, anchor="ls")
        bounds = mask.getbbox()
        assert ink[1] == baseline + offset[1] + bounds[1]
        assert ink[3] == baseline + offset[1] + bounds[3]
        assert glyph.get_center()[1] == pytest.approx(0, abs=1e-6)
    dot = obj[obj.num_string.index(".")].image.getchannel("A").getbbox()
    assert (dot[1] + dot[3]) / 2 > line_height * .65


@pytest.mark.parametrize(("value", "decimals", "expected"), [
    (-0.0, 2, "0.00"), (-0.004, 2, "0.00"), (-0.4, 0, "0"),
    (-0.006, 2, "-0.01"), (-1.25, 2, "-1.25"), (1.6, 0, "2"),
    (2.5, 0, "2"), (9.999, 2, "10.00"),
])
def test_number_format_and_displayed_value(tmp_path, number_font, value, decimals, expected):
    obj = RasterNumber(value, tmp_path, decimals=decimals, font_path=number_font)
    assert obj.num_string == expected
    assert obj.num_string.isascii()
    assert obj.get_value() == float(expected)
    if obj.get_value() == 0:
        assert math.copysign(1, obj.get_value()) == 1


def test_updates_bind_group_value_and_reuse_only_glyph_assets(tmp_path, number_font):
    obj = RasterNumber(0, tmp_path, font_path=number_font)
    original = list(obj.submobjects)
    assert obj.set_value(0.001) is obj
    assert obj.submobjects == original
    for value in (-1023456789.12, 8.56, 0, 7.43):
        assert obj.set_value(value) is obj
        assert obj.get_value() == float(obj.num_string)
        assert len(obj) == len(obj.num_string)
        for char, glyph in zip(obj.num_string, obj):
            assert glyph.image_path == obj._glyphs[char].image_path
    assets = set(tmp_path.rglob("*.png"))
    assert len(assets) == len(obj._glyphs) == 12
    for value in (42.34, 567.89, -1023456789.12):
        obj.set_value(value)
    assert set(tmp_path.rglob("*.png")) == assets
    assert all(member.shader_wrapper is None for member in obj.get_family())


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_update_leaves_display_unchanged(tmp_path, number_font, value):
    obj = RasterNumber(12.34, tmp_path, font_path=number_font)
    children = list(obj.submobjects)
    with pytest.raises(ValueError, match="finite"):
        obj.set_value(value)
    assert obj.num_string == "12.34"
    assert obj.get_value() == 12.34
    assert obj.submobjects == children


@pytest.mark.parametrize("decimals", [-1, 1.5, True])
def test_invalid_precision_is_rejected(tmp_path, number_font, decimals):
    with pytest.raises(ValueError, match="decimals"):
        RasterNumber(1, tmp_path, decimals=decimals, font_path=number_font)


def test_bitmap_colors_sample_native_images_not_target_color(tmp_path):
    path = tmp_path / "actual.png"
    bitmap = Image.new("RGBA", (4, 1))
    bitmap.putdata([(1, 2, 3, 255), (10, 20, 30, 255),
                    (255, 0, 0, 0), (60, 70, 80, 100)])
    bitmap.save(path)
    obj = ImageMobject(str(path))
    obj.set_color("#FFFFFF")
    assert bitmap_colors(obj) == {"#010203", "#0A141E", "#3C4650"}
    vector = Dot(color="#FFFFFF")
    vector.image = Image.new("RGB", (1, 1), "#ABCDEF")
    assert bitmap_colors(vector) == set()
    assert bitmap_colors(Group(Group(obj), vector)) == bitmap_colors(obj)


def test_bitmap_colors_reread_changed_live_image(tmp_path):
    path = tmp_path / "actual.png"
    Image.new("RGB", (2, 1), "#112233").save(path)
    obj = ImageMobject(str(path))
    assert bitmap_colors(obj) == {"#112233"}
    obj.image.putpixel((0, 0), (68, 85, 102))
    assert bitmap_colors(obj) == {"#112233", "#445566"}
    obj.image = Image.new("RGBA", (1, 1), (200, 100, 50, 0))
    assert bitmap_colors(obj) == set()
    obj.image = Image.new("RGB", (1, 1), "#778899")
    assert bitmap_colors(obj) == {"#778899"}
    obj.set_opacity(0)
    assert bitmap_colors(obj) == set()


def test_generated_label_and_number_report_actual_ink(tmp_path, number_font):
    label = text_image("value", tmp_path, color="#123456", font_path=number_font,
                       font_index=NUMBER_FONT_INDEX)
    number = RasterNumber(-12.34, tmp_path, color="#ABCDEF", font_path=number_font)
    assert bitmap_colors(Group(label, number)) == {"#123456", "#ABCDEF"}
    number.set_value(98.76)
    assert bitmap_colors(number) == {"#ABCDEF"}
