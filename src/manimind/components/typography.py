"""Parameterised version of experiments.scene_support's FreeType workaround.

Bitmaps are disposable render assets, written below the caller's explicit asset
directory. No environment variable or working directory determines their path.

The bounded FreeType LRU is only a process-local font cache, not collaboration
state. This module writes it; text_image and RasterNumber consume it. Font file
metadata changes invalidate its keys; eviction or process exit releases entries.
Each RasterNumber owns at most 12 immutable glyph templates for its fixed style,
released with that object. Recreate the number after a font/style change. PNGs
are rebuildable, versioned assets whose lifetime is the caller's asset directory.
"""

import hashlib
import json
import math
from functools import lru_cache
from numbers import Integral
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from manimlib import Group, ImageMobject, RIGHT


from .catalog import FONT, FONT_INDEX, FONT_PATH, NUMBER_FONT_INDEX, NUMBER_FONT_PATH


_RASTER_SCALE = 4
_PIXELS_PER_UNIT = 400
_PADDING = 2
_NUMBER_CHARS = "0123456789-."


def _font_spec(asset_dir, font_path, size, font_index):
    asset_dir, font_path = Path(asset_dir), Path(font_path)
    if not asset_dir.is_absolute() or not font_path.is_absolute():
        raise ValueError("Typography requires absolute asset and font paths")
    if not math.isfinite(size) or size <= 0 or round(size * _RASTER_SCALE) < 1:
        raise ValueError("Typography requires a positive raster font size")
    if not isinstance(font_index, Integral) or isinstance(font_index, bool) or font_index < 0:
        raise ValueError("Typography requires a nonnegative integer font index")
    stat = font_path.stat()
    return asset_dir, (str(font_path), round(size * _RASTER_SCALE), int(font_index),
                       stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)


@lru_cache(maxsize=32)
def _load_font(path, pixel_size, font_index, mtime_ns, ctime_ns, file_size):
    return ImageFont.truetype(path, pixel_size, index=font_index)


def _asset_path(asset_dir, kind, parameters):
    key = hashlib.sha256(json.dumps(parameters).encode()).hexdigest()[:24]
    directory = asset_dir / "text-assets"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{kind}-{key}.png"


def _image_mobject(path, height):
    result = ImageMobject(str(path), height=height / _PIXELS_PER_UNIT)
    # Decode once and release Pillow's file handle, including on cached glyphs.
    result.image.load()
    return result


def text_image(text, asset_dir: Path, size=24, color="#F0F3F6", *,
               font=FONT, font_path: Path = FONT_PATH, font_index=FONT_INDEX):
    """Use the project's 4x FreeType raster, without unreliable Pango glyph boxes."""
    asset_dir, spec = _font_spec(asset_dir, font_path, size, font_index)
    face = _load_font(*spec)
    left, top, right, bottom = face.getbbox(text)
    width, height = max(1, right - left + 4), max(1, bottom - top + 4)
    path = _asset_path(asset_dir, "text", ["text-v2", text, color, font, spec])
    if not path.exists():
        bitmap = Image.new("RGBA", (width, height))
        ImageDraw.Draw(bitmap).text((2 - left, 2 - top), text, font=face, fill=color)
        bitmap.save(path)
    # One font point is 0.01 scene units, close to the existing Text sizing.
    # Preserve the raster's aspect ratio instead of stretching a bad Pango box.
    return _image_mobject(path, height)


class RasterNumber(Group):
    """A current displayed value composed from native ImageMobject glyphs.

    Digits have a common advance; punctuation retains its own fixed advance.
    Every glyph has the same ascender/descender linebox and baseline, including
    the decimal point. Height is (ascent + descent + 4) / 400 scene units, not
    the cropped ink height. set_value preserves the right edge and uniform scale;
    the renderer still owns the final row anchor. get_value reports the rounded
    value actually on screen, and num_string always uses ASCII minus.
    """

    def __init__(self, value, asset_dir: Path, size=32, color="#F0F3F6", decimals=2,
                 font_path: Path = NUMBER_FONT_PATH, font_index=NUMBER_FONT_INDEX):
        if not isinstance(decimals, Integral) or isinstance(decimals, bool) or decimals < 0:
            raise ValueError("RasterNumber requires nonnegative integer decimals")
        self.decimals = int(decimals)
        self.asset_dir, self._font_spec = _font_spec(asset_dir, font_path, size, font_index)
        self._face = _load_font(*self._font_spec)
        self._glyph_color = color
        self._glyphs = {}
        ascent, descent = self._face.getmetrics()
        self._baseline_px = _PADDING + ascent
        self._line_height_px = ascent + descent + 2 * _PADDING
        self._advances = {char: self._face.getlength(char) for char in _NUMBER_CHARS}
        self._digit_advance = math.ceil(max(self._advances[c] for c in "0123456789"))
        # Include bearings without cropping overhangs or moving each glyph's ink
        # to its own bounding-box center (which would lift the decimal point).
        boxes = {char: self._face.getbbox(char, anchor="ls") for char in _NUMBER_CHARS}
        self._left_pad = _PADDING + math.ceil(max(0, *(-box[0] for box in boxes.values())))
        self._right_pad = _PADDING + math.ceil(max(
            0, *(box[2] - self._advances[char] for char, box in boxes.items())
        ))
        self.num_string = ""
        self.number = 0.0
        super().__init__()
        self.set_value(value)

    def _glyph(self, char):
        if char not in self._glyphs:
            advance = self._digit_advance if char.isdigit() else math.ceil(self._advances[char])
            width = advance + self._left_pad + self._right_pad
            path = _asset_path(self.asset_dir, "number", [
                "number-v1", char, self._glyph_color, self._font_spec,
                width, self._line_height_px, self._baseline_px,
                self._left_pad, self._right_pad,
            ])
            if not path.exists():
                bitmap = Image.new("RGBA", (width, self._line_height_px))
                x = self._left_pad + (advance - self._advances[char]) / 2
                ImageDraw.Draw(bitmap).text(
                    (x, self._baseline_px), char, font=self._face,
                    fill=self._glyph_color, anchor="ls",
                )
                bitmap.save(path)
            self._glyphs[char] = _image_mobject(path, self._line_height_px)
        return self._glyphs[char]

    def set_value(self, number):
        number = float(number)
        if not math.isfinite(number):
            raise ValueError("RasterNumber requires a finite value")
        text = f"{number:.{self.decimals}f}"
        displayed = float(text)
        if displayed == 0:
            displayed = 0.0
            text = text.removeprefix("-")
        if text != self.num_string:
            right = self.get_right().copy() if self.submobjects else None
            height = self._line_height_px / _PIXELS_PER_UNIT
            scale = self.get_height() / height if self.submobjects else 1
            glyphs, x = [], 0.0
            for char in text:
                glyph = self._glyph(char).copy().scale(scale)
                width = glyph.get_width()
                glyph.move_to([x + width / 2, 0, 0])
                glyphs.append(glyph)
                x += width
            self.set_submobjects(glyphs)
            if right is None:
                self.center()
            else:
                self.move_to(right, aligned_edge=RIGHT)
            self.num_string = text
        self.number = displayed
        return self

    def get_value(self):
        return self.number


def bitmap_colors(mobject):
    """Read RGB colors of nontransparent pixels in native image family members.

    This is source-ink evidence, not composited framebuffer color. Sample the
    current Pillow image each time: no target-color shortcut or stale path cache
    can conceal an edited/replaced bitmap. Vector and fully hidden members do
    not contribute; antialiased pixels with nonzero alpha do contribute.
    """
    colors = set()
    for member in mobject.get_family():
        if not isinstance(member, ImageMobject) or not member.has_points():
            continue
        if not (member.data["opacity"] > 0).any():
            continue
        rgba = member.image.convert("RGBA")
        for _, (red, green, blue, alpha) in rgba.getcolors(rgba.width * rgba.height):
            if alpha:
                colors.add(f"#{red:02X}{green:02X}{blue:02X}")
    return colors
