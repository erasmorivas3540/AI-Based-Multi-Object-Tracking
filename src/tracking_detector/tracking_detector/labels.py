"""Which truth objects are training boxes, evaluation targets, or ignored."""
from __future__ import annotations


def classify_object(o: dict, min_vis: float, min_side: float, need_in_fov: bool = True) -> str:
    """'target' (counts), 'ignore' (partly visible: neither rewarded nor penalised), 'absent'."""
    vb = o.get("visible_box")
    if not vb:
        return "absent"
    side = min(vb[2] - vb[0], vb[3] - vb[1])
    if o["vis"] >= min_vis and side >= min_side and (o["in_fov"] or not need_in_fov):
        return "target"
    return "ignore"


def yolo_line(o: dict, cls_index: int, width: int, height: int) -> str:
    x1, y1, x2, y2 = o["visible_box"]
    return (f"{cls_index} {(x1 + x2) / 2 / width:.6f} {(y1 + y2) / 2 / height:.6f} "
            f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}")
