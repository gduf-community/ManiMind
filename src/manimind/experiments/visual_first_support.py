"""Typography and measured visual events for narration-free ManimGL scenes."""

import json

from manimlib import Scene

from manimind.experiments.freeform_support import LessonScene
from manimind.experiments.visual_first_data import validate_events


class VisualLessonScene(LessonScene):
    def setup(self):
        super().setup()
        if self.timeline.get("mode") != "visual_first_silent":
            raise ValueError("This runtime requires a visual clock, not a speech clock")
        if any(cue.get("spoken_spans") for cue in self.cues):
            raise ValueError("Silent visual review cannot contain narration subtitles")
        self.visual_events = []

    def mark(self, event_id):
        """Record an actual visual event after the corresponding state is visible."""
        self.visual_events.append({"id": event_id, "time": float(self.get_time())})

    def tear_down(self):
        events = {"duration": float(self.get_time()), "events": self.visual_events,
                  "writer": "visual render runtime", "consumers": ["reviewer", "later narrator"],
                  "lifecycle": "This actual render", "invalidation": "New source, plan or render"}
        validate_events(self.timeline, events)
        (self.out / "visual-events.json").write_text(json.dumps(events))
        (self.out / "sound-events.json").write_text(json.dumps({"events": self.sound_events}))
        Scene.tear_down(self)
