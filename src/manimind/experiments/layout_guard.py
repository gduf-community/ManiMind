"""Deterministic label-box checks; not a pixel or educational-quality judge."""

from itertools import combinations
import math


def check_boxes(boxes: dict, bounds: list, gap: float = 0.03) -> list[str]:
    issues = []
    valid = {}
    for name, box in boxes.items():
        if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                or box[0] >= box[1] or box[2] >= box[3]):
            issues.append(f"invalid_box:{name}")
            continue
        valid[name] = box
        if box[0] < bounds[0] or box[1] > bounds[1] or box[2] < bounds[2] or box[3] > bounds[3]:
            issues.append(f"out_of_bounds:{name}")
    for (a, x), (b, y) in combinations(valid.items(), 2):
        if x[0] < y[1] + gap and y[0] < x[1] + gap and x[2] < y[3] + gap and y[2] < x[3] + gap:
            issues.append(f"label_collision:{a}:{b}")
    return issues


def validate_report(report: dict, contract: dict, cue_count: int) -> None:
    if report.get("contract") != contract:
        raise ValueError("Layout contract changed or missing")
    checkpoints = report.get("checkpoints", [])
    required = set(contract["required_labels"])
    for index in range(cue_count):
        if not any(p.get("cue") == index and p.get("fraction") == 1 for p in checkpoints):
            raise ValueError("Incomplete layout checkpoints")
    for point in checkpoints:
        boxes = point.get("boxes", {})
        if not required.issubset(boxes):
            raise ValueError("Missing required registered labels")
        if check_boxes(boxes, contract["bounds"], contract.get("gap", 0.03)):
            raise ValueError("Layout checks blocked delivery")
