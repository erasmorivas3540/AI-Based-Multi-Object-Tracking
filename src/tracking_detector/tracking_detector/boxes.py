"""Box utilities with no detector dependency: letterbox and its inverse, NMS,
greedy class-aware matching. Unit-tested in tests/test_detector_utils.py."""
from __future__ import annotations

import numpy as np


def letterbox_params(h: int, w: int, imgsz: int):
    """Scale and padding that fit an h x w image into imgsz x imgsz, centred."""
    r = min(imgsz / h, imgsz / w)
    nh, nw = round(h * r), round(w * r)
    return r, (imgsz - nw) / 2, (imgsz - nh) / 2


def to_letterbox(boxes, h, w, imgsz):
    r, px, py = letterbox_params(h, w, imgsz)
    b = np.asarray(boxes, float).reshape(-1, 4) * r
    b[:, [0, 2]] += px
    b[:, [1, 3]] += py
    return b


def from_letterbox(boxes, h, w, imgsz):
    """Inverse of to_letterbox: model-input coordinates -> original image pixels."""
    r, px, py = letterbox_params(h, w, imgsz)
    b = np.asarray(boxes, float).reshape(-1, 4).copy()
    b[:, [0, 2]] -= px
    b[:, [1, 3]] -= py
    b /= r
    b[:, [0, 2]] = b[:, [0, 2]].clip(0, w)
    b[:, [1, 3]] = b[:, [1, 3]].clip(0, h)
    return b


def nms(boxes, scores, iou_thr: float) -> np.ndarray:
    """Indices kept by greedy NMS, highest score first."""
    from tracking_sim.geometry import iou_matrix

    boxes = np.asarray(boxes, float).reshape(-1, 4)
    order = np.argsort(-np.asarray(scores, float), kind="stable")
    keep = []
    suppressed = np.zeros(len(boxes), bool)
    iou = iou_matrix(boxes, boxes)
    for i in order:
        if suppressed[i]:
            continue
        keep.append(i)
        suppressed |= iou[i] > iou_thr
    return np.array(keep, int)


def classwise_nms(boxes, scores, classes, iou_thr: float) -> np.ndarray:
    classes = np.asarray(classes)
    keep = []
    for c in np.unique(classes):
        idx = np.flatnonzero(classes == c)
        keep.extend(idx[nms(np.asarray(boxes)[idx], np.asarray(scores)[idx], iou_thr)])
    return np.array(sorted(keep, key=lambda i: -scores[i]), int)


def greedy_match(det_boxes, det_scores, gt_boxes, iou_thr: float):
    """Detections in descending score claim the highest-IoU unclaimed truth box.

    Returns (det_to_gt: (N,) index or -1, best_iou_per_gt: (M,)).
    """
    from tracking_sim.geometry import iou_matrix

    det_boxes = np.asarray(det_boxes, float).reshape(-1, 4)
    gt_boxes = np.asarray(gt_boxes, float).reshape(-1, 4)
    iou = iou_matrix(det_boxes, gt_boxes)
    det_to_gt = -np.ones(len(det_boxes), int)
    taken = np.zeros(len(gt_boxes), bool)
    for i in np.argsort(-np.asarray(det_scores, float), kind="stable"):
        if len(gt_boxes) == 0:
            break
        cand = np.where(taken, -1.0, iou[i])
        j = int(np.argmax(cand))
        if cand[j] >= iou_thr:
            det_to_gt[i] = j
            taken[j] = True
    best = iou.max(axis=0) if len(det_boxes) else np.zeros(len(gt_boxes))
    return det_to_gt, best
