"""Opt-in instrumentation for collaboration trials, without changing old support.

The renderer owns the report path for one attempt. The scene writes measured
label boxes at beat endpoints; benchmark/reviewer consume them. Source or
contract changes invalidate this evidence. Intermediate pixels remain reviewed.
"""

import json
import os
from pathlib import Path

from .scene_support import BenchmarkScene, output_dir
from .layout_guard import check_boxes


class GuardedBenchmarkScene(BenchmarkScene):
    def setup(self):
        super().setup()
        self.layout_contract = json.loads((output_dir() / "design-brief.json").read_text())["layout_contract"]
        self.layout_labels = {}
        self.layout_checkpoints = []

    def register_labels(self, labels):
        if self.layout_labels or not isinstance(labels, dict) or not labels:
            raise ValueError("Register all label objects exactly once")
        self.layout_labels = dict(labels)

    def beat(self, fraction, *animations, rate_func=None):
        super().beat(fraction, *animations, rate_func=rate_func)
        boxes = {name: [float(obj.get_left()[0]), float(obj.get_right()[0]),
                        float(obj.get_bottom()[1]), float(obj.get_top()[1])]
                 for name, obj in self.layout_labels.items()}
        issues = check_boxes(boxes, self.layout_contract["bounds"], self.layout_contract.get("gap", 0.03))
        missing = set(self.layout_contract["required_labels"]) - boxes.keys()
        issues.extend(f"missing_label:{name}" for name in sorted(missing))
        self.layout_checkpoints.append({"cue": self.cue_index, "fraction": fraction,
                                        "time": self.get_time(), "boxes": boxes, "issues": issues})
        # Keep failed measurements available even when a later animation crashes.
        Path(os.environ["MANIMIND_LAYOUT_REPORT"]).write_text(json.dumps({
            "contract": self.layout_contract, "checkpoints": self.layout_checkpoints,
            "limitations": ["Registered labels only", "Beat endpoints, not all intermediate frames",
                            "Grouped rows require internal-spacing visual review", "Not delivery approval"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
