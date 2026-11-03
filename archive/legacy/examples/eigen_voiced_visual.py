"""Case-local reading extension for the 27 measured eigen speech takes.

The author owns these frozen budgets; renderer and native tests consume them.
They expire on baseline source, speech PCM, focus or plan changes. No media is
loaded here, and no visual, narration or release approval is granted.
"""

import eigen_visual as baseline


CUE_DURATIONS = (29, 28, 34, 34, 35, 46, 28, 20)
# ceil(full WAV seconds + .5), bounded below by each original read duration.
READ_DURATIONS = {
    "matrix_map": 7,
    "general_turn": 6,
    "definition": 10,
    "vector_equation": 5,
    "subtract": 7,
    "factor": 4,
    "equal_nonzero": 7,
    "equal_substitute": 4,
    "equal_value": 5,
    "plus_direction": 6,
    "other_value": 7,
    "other_reduce": 4,
    "all_directions": 7,
    "decompose": 8,
    "recombine": 6,
    "linearity_check": 8,
    "rotation_input": 5,
}


class EigenDirectionsVoicedLesson(baseline.EigenDirectionsLesson):
    def read(self, identity, duration, event=None):
        super().read(identity, max(duration, READ_DURATIONS.get(identity, duration)), event)

    def construct(self):
        self.motion_samples, self.symbol_transitions, self.chapter_times = [], [], []
        methods = (self.opening, self.directions, self.equations, self.equal_case,
                   self.other_case, self.decomposition, self.rotation, self.closing)
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Scene and plan cue durations differ")
            self.until(cue["start"])
            begin = float(self.get_time())
            method()
            self.until(cue["start"] + duration)
            self.chapter_times.append({"id": cue["id"], "start": begin, "end": float(self.get_time())})
