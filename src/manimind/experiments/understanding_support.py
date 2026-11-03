"""Measured readability windows over the existing visual-first ManimGL runtime."""

import json

from manimind.experiments.visual_first_support import VisualLessonScene
from manimind.review.semantic_focus import focus_windows, safe_id


class UnderstandingScene(VisualLessonScene):
    def setup(self):
        super().setup()
        self._open_focus = {}
        self._closed_focus = []

    def focus_begin(self, identity):
        """Call when the named referent is readable; pixel review must verify it."""
        if not safe_id(identity) or identity in self._open_focus or any(row["id"] == identity for row in self._closed_focus):
            raise ValueError("Focus IDs must be unique throughout this render")
        self._open_focus[identity] = float(self.get_time())

    def focus_end(self, identity):
        if identity not in self._open_focus:
            raise ValueError("Cannot close a focus that is not active")
        start, end = self._open_focus.pop(identity), float(self.get_time())
        if end <= start:
            raise ValueError("A readable focus must have nonzero measured duration")
        self._closed_focus.append({"id": identity, "start": start, "end": end})

    def tear_down(self):
        if self._open_focus:
            raise ValueError("Close every measured focus before finishing the scene")
        report = {"duration": float(self.get_time()), "windows": self._closed_focus,
                  "writer": "Actual UnderstandingScene render runtime", "consumers": ["narrator", "independent reviewer", "speech aligner"],
                  "lifecycle": "This exact visual render", "invalidation": "Any visual source, timing or media change",
                  "limitation": "Annotations are not proof of visibility; inspect actual pixels"}
        focus_windows(report, report["duration"])
        super().tear_down()
        with (self.out / "focus-events.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
