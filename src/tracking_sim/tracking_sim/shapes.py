"""Target shapes as compositions of boxes.

ONE definition drives three things: the Gazebo visuals (world_sdf.py), the toy
renderer, and the analytic silhouettes used for labels. Because all three use the
same parts, analytic boxes are pixel-tight and should match Gazebo's own
bounding-box camera closely (checked in the Week 2 audit).

Offsets are in the object frame (x forward, y left, z up) relative to the
object's pose centre. Colours are RGB 0-1 (Gazebo) and are converted for OpenCV.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .geometry import project_box, rot_zyx

GREY = (0.18, 0.18, 0.2)
DARK = (0.08, 0.08, 0.09)

SHAPES = {
    # Quadrotor, overall about 0.60 x 0.60 x 0.19 m ("+" configuration)
    "uav": [
        {"name": "body",    "offset": (0, 0, 0),          "size": (0.22, 0.22, 0.10), "rgb": GREY},
        {"name": "arm_x",   "offset": (0, 0, 0.02),       "size": (0.46, 0.04, 0.03), "rgb": DARK},
        {"name": "arm_y",   "offset": (0, 0, 0.02),       "size": (0.04, 0.46, 0.03), "rgb": DARK},
        {"name": "rotor_f", "offset": (0.23, 0, 0.06),    "size": (0.14, 0.14, 0.01), "rgb": DARK},
        {"name": "rotor_b", "offset": (-0.23, 0, 0.06),   "size": (0.14, 0.14, 0.01), "rgb": DARK},
        {"name": "rotor_l", "offset": (0, 0.23, 0.06),    "size": (0.14, 0.14, 0.01), "rgb": DARK},
        {"name": "rotor_r", "offset": (0, -0.23, 0.06),   "size": (0.14, 0.14, 0.01), "rgb": DARK},
        {"name": "leg_l",   "offset": (0, 0.08, -0.09),   "size": (0.20, 0.02, 0.07), "rgb": DARK},
        {"name": "leg_r",   "offset": (0, -0.08, -0.09),  "size": (0.20, 0.02, 0.07), "rgb": DARK},
    ],
    # Car, overall 4.5 x 1.9 x 1.5 m, pose centre 0.75 m above the ground
    "ground": [
        {"name": "body",    "offset": (0, 0, -0.15),      "size": (4.5, 1.9, 0.8),  "rgb": (0.62, 0.16, 0.12)},
        {"name": "cabin",   "offset": (-0.3, 0, 0.5),     "size": (2.4, 1.7, 0.5),  "rgb": (0.25, 0.3, 0.35)},
        {"name": "wheel_fl", "offset": (1.4, 0.8, -0.5),  "size": (0.7, 0.3, 0.5),  "rgb": DARK},
        {"name": "wheel_fr", "offset": (1.4, -0.8, -0.5), "size": (0.7, 0.3, 0.5),  "rgb": DARK},
        {"name": "wheel_rl", "offset": (-1.4, 0.8, -0.5), "size": (0.7, 0.3, 0.5),  "rgb": DARK},
        {"name": "wheel_rr", "offset": (-1.4, -0.8, -0.5), "size": (0.7, 0.3, 0.5), "rgb": DARK},
    ],
}

PLAIN = {"clutter": (0.42, 0.33, 0.25), "occluder": (0.75, 0.75, 0.74)}


def parts_for(obj) -> list[dict]:
    if obj.kind == "target":
        return SHAPES[obj.cls]
    return [{"name": "box", "offset": (0, 0, 0), "size": tuple(obj.size), "rgb": PLAIN[obj.kind]}]


def bgr(rgb) -> tuple:
    return tuple(int(255 * c) for c in rgb[::-1])


def silhouette(obj, f: int, cam_pos, R, cam):
    """Project an object's parts.

    Returns (union_polygon, [(part, hull)], depth_m, center_px, in_front) or None
    if nothing is in front of the camera.
    """
    pos, yaw, pitch = obj.pose_at(f)
    Ro = rot_zyx(yaw, pitch, 0.0)
    polys, hulls = [], []
    for part in parts_for(obj):
        c = np.asarray(pos, float) + Ro @ np.asarray(part["offset"], float)
        p = project_box(c, part["size"], yaw, cam_pos, R, cam, pitch)
        if p is None or len(p.hull) < 3:
            continue
        poly = Polygon(p.hull).buffer(0)
        if poly.area > 0:
            polys.append(poly)
            hulls.append((part, p.hull))
    if not polys:
        return None
    centre = project_box(pos, [0.01, 0.01, 0.01], yaw, cam_pos, R, cam)
    depth = float((np.asarray(pos, float) - cam_pos) @ R[:, 0])
    in_front = centre is not None and centre.in_front
    return unary_union(polys), hulls, depth, (centre.center_px if in_front else (np.nan, np.nan)), in_front
