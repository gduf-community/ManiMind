"""Local scalar replacement after the real v010 probe, with fixed math factors.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. The cue owns the active
formula and diagnostic driver; cleanup replaces them natively. Any source,
clock, geometry or pixels change invalidates this revision's observations.
"""

from derivative_ch04_traceable_v010 import (
    DerivativeChainTraceableV010, PRODUCT, FINAL, align_native_glyphs,
    geometry_signature, remainder,
)
from manimlib import Group, VGroup
from manimind.components.formula_motion import matching_transform


def glyph_opacity(part, present):
    return max((float(glyph.get_opacity()) for glyph in part.family_members_with_points()
                if id(glyph) in present), default=0)


class DerivativeChainTraceableV011(DerivativeChainTraceableV010):
    def carry(self, source, target, start, end, role):
        if role != "collect_4_times_3":
            return super().carry(source, target, start, end, role)
        self.at(start)
        active = super().semantic(PRODUCT, {"lhs": "y'=", "factor": r"(3x-1)^3",
            "four": "4", "three": ("3", 2), "times": r"\cdot"}, y=-.3, size=43)
        source_lhs = VGroup(*source.tag("prefix").submobjects, *source.tag("relation").submobjects)
        source_factor = remainder(source, [source.tag(k) for k in
                                  ("prefix", "relation", "coefficient", "rate", "times")])
        for key, part in (("lhs", source_lhs), ("factor", source_factor),
                          ("four", source.tag("coefficient")), ("three", source.tag("rate")),
                          ("times", source.tag("times"))):
            align_native_glyphs(active.tag(key), part)
        final = super().semantic(FINAL, {"lhs": "y'=", "factor": r"(3x-1)^3", "twelve": "12"},
                                 y=-.3, size=43)
        align_native_glyphs(final.tag("lhs"), active.tag("lhs"))
        align_native_glyphs(final.tag("factor"), active.tag("factor"))
        final.tag("twelve").move_to(active.tag("four").get_center())
        self.remove(source)
        self.add(active)
        driver = Group()
        frame = getattr(self.camera, "frame", None)
        camera = None if frame is None else dict(width=float(frame.get_width()),
            height=float(frame.get_height()), center=frame.get_center().tolist())
        self.sample("collection_fixed_regions", factor_box=active.tag("factor").get_bounding_box().tolist(),
                    lhs_box=active.tag("lhs").get_bounding_box().tolist(), camera=camera)

        def record(_):
            self.sample("collection_fixed_geometry", factor=geometry_signature(active.tag("factor")),
                        lhs=geometry_signature(active.tag("lhs")))
            present = {id(node) for mob in self.mobjects for node in mob.get_family()}
            self.sample("collection_scalar_visibility",
                old=max(glyph_opacity(active.tag(k), present) for k in ("four", "three", "times")),
                new=glyph_opacity(final.tag("twelve"), present))

        driver.add_updater(record)
        self.add(driver)
        self.sample("collection_constants_begin", operation="4 times 3 equals 12")
        # Native serial timing holds the identical matched regions, then removes
        # all old constants before introducing 12. No scalar crossfade overlap.
        animation = matching_transform(active, final,
            pairs=[("lhs", "lhs"), ("factor", "factor")],
            unmatched_in_place=True, lag_ratio=1)
        self.at(end, animation)
        driver.clear_updaters()
        self.remove(driver)
        self.sample("collection_constants_finalize", factor=geometry_signature(final.tag("factor")),
                    lhs=geometry_signature(final.tag("lhs")))


class DerivativeChainRepairProbeV011(DerivativeChainTraceableV011):
    def construct(self):
        self.motion_samples = []
        for cue in self.cues:
            self.begin_chapter(cue)
            getattr(self, cue["id"])()
            self.end_chapter()
