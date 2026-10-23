"""Toy renderer: draws a scenario with OpenCV, no Gazebo needed.

Purpose: run and test the whole offline pipeline (labels, audit, events, detector
export/training, TrackEval) before Gazebo is available, and cross-check the
analytic visibility labels against a rendered instance mask.

It is NOT a substitute for Gazebo frames in the study: its images are flat-shaded
silhouettes. Never mix toy frames into the real dataset (the clip manifest records
the renderer used).
"""
from __future__ import annotations

import cv2
import numpy as np
from shapely.geometry import Polygon, box as sbox

from .geometry import NEAR_PLANE_M, project_box, project_cam, rot_zyx, world_to_cam
from .scenario import Scenario
from .shapes import bgr, silhouette

SKY = (205, 190, 170)          # BGR
GRID_STEP_M, GRID_HALF_M = 5.0, 150.0
BG_LABEL, OCC_LABEL = 0, 255


def _segment(p, q, cam_pos, R, cam):
    a, b = world_to_cam(np.array([p, q], float), cam_pos, R)
    if a[0] <= NEAR_PLANE_M and b[0] <= NEAR_PLANE_M:
        return None
    if a[0] <= NEAR_PLANE_M or b[0] <= NEAR_PLANE_M:
        t = (NEAR_PLANE_M - a[0]) / (b[0] - a[0])
        c = a + t * (b - a)
        a, b = (c, b) if a[0] <= NEAR_PLANE_M else (a, c)
    uv = project_cam(np.array([a, b]), cam)
    return np.clip(uv, -1e5, 1e5).astype(np.int32)


def _part_depth(part_hull, o, f, sc, R):
    part, _ = part_hull
    pos, yaw, pitch = o.pose_at(f)
    c = np.asarray(pos, float) + rot_zyx(yaw, pitch, 0.0) @ np.asarray(part["offset"], float)
    return float((c - sc.cam_pos[f]) @ R[:, 0])


def render_frame(sc: Scenario, f: int, ground_bgr=(80, 120, 96)):
    """Returns (image BGR uint8, instance mask uint8: target id, 255 = occluder/clutter, 0 = background)."""
    cam = sc.cam
    R = rot_zyx(*sc.cam_ypr[f])
    img = np.full((cam.height, cam.width, 3), SKY, np.uint8)
    mask = np.zeros((cam.height, cam.width), np.uint8)

    ground = project_box([sc.cam_pos[f][0], sc.cam_pos[f][1], -0.01], [6000, 6000, 0.001], 0.0,
                         sc.cam_pos[f], R, cam)
    if ground is not None and len(ground.hull) >= 3:
        # Clip the (possibly enormous) projected polygon to a margin around the
        # image as a polygon; clamping vertices would distort its shape.
        g = Polygon(ground.hull).buffer(0).intersection(
            sbox(-cam.width, -cam.height, 2 * cam.width, 2 * cam.height))
        for poly in getattr(g, "geoms", [g]):
            if poly.geom_type == "Polygon" and poly.area > 0:
                cv2.fillPoly(img, [np.round(np.asarray(poly.exterior.coords)).astype(np.int32)], ground_bgr)
    line_col = tuple(int(c * 0.82) for c in ground_bgr)
    for x in np.arange(-GRID_HALF_M, GRID_HALF_M + 1, GRID_STEP_M):
        for p, q in (([x, -GRID_HALF_M, 0], [x, GRID_HALF_M, 0]), ([-GRID_HALF_M, x, 0], [GRID_HALF_M, x, 0])):
            seg = _segment(p, q, sc.cam_pos[f], R, cam)
            if seg is not None:
                cv2.line(img, tuple(seg[0]), tuple(seg[1]), line_col, 1, cv2.LINE_AA)

    drawn = []
    for o in sc.objects:
        if o.kind == "occluder" and not o.active[f]:
            continue
        sil = silhouette(o, f, sc.cam_pos[f], R, cam)
        if sil is not None:
            drawn.append((sil[2], o, sil[1]))
    for _depth, o, hulls in sorted(drawn, key=lambda x: -x[0]):   # far to near
        label = o.obj_id if o.kind == "target" else OCC_LABEL
        # draw parts back to front (larger depth first) within the object
        hulls = sorted(hulls, key=lambda ph: -_part_depth(ph, o, f, sc, R))
        for part, hull in hulls:
            h = np.clip(hull, -1e5, 1e5).astype(np.int32)
            color = bgr(part["rgb"])
            cv2.fillPoly(img, [h], color, cv2.LINE_AA)
            cv2.polylines(img, [h], True, tuple(max(0, c - 20) for c in color), 1, cv2.LINE_AA)
            cv2.fillPoly(mask, [h], int(label))
    return img, mask


def mask_visibility(mask: np.ndarray, sc: Scenario, f: int) -> dict:
    """Visible fraction per target measured from the rendered mask, using the
    target's own silhouette rendered alone as the denominator."""
    cam = sc.cam
    R = rot_zyx(*sc.cam_ypr[f])
    out = {}
    for o in sc.targets():
        sil = silhouette(o, f, sc.cam_pos[f], R, cam)
        if sil is None:
            continue
        alone = np.zeros_like(mask)
        for _part, hull in sil[1]:
            cv2.fillPoly(alone, [np.clip(hull, -1e5, 1e5).astype(np.int32)], 1)
        full = int(alone.sum())
        if full == 0:
            continue
        out[o.obj_id] = float(((mask == o.obj_id) & (alone == 1)).sum()) / full
    return out
