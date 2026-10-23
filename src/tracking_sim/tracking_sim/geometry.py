"""Camera model and box projection. Pure NumPy, no ROS or Gazebo.

Conventions (match Gazebo):
  World frame: x forward, y left, z up. Metres.
  Camera link frame: the camera looks along +x; image x (right) is -y of the
  link, image y (down) is -z of the link.
  Pose: position (x, y, z) and yaw/pitch/roll in radians, R = Rz(yaw) Ry(pitch) Rx(roll).
  Positive pitch tilts the camera nose DOWN.
  Image: pixel x right, pixel y down, origin at the top-left pixel corner.
  Boxes: (x1, y1, x2, y2) in pixels unless a function says otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

NEAR_PLANE_M = 0.05


def rot_zyx(yaw: float, pitch: float, roll: float) -> np.ndarray:
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll), np.sin(roll)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return rz @ ry @ rx


def look_at_angles(eye: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    """Yaw and pitch that point the camera +x axis from eye toward target."""
    d = np.asarray(target, float) - np.asarray(eye, float)
    yaw = float(np.arctan2(d[1], d[0]))
    pitch = float(np.arctan2(-d[2], np.hypot(d[0], d[1])))  # positive = look down
    return yaw, pitch


@dataclass(frozen=True)
class Camera:
    width: int = 1280
    height: int = 720
    hfov_rad: float = np.deg2rad(80.0)

    @property
    def fx(self) -> float:
        # Gazebo derives focal length from horizontal FOV with square pixels.
        return self.width / (2.0 * np.tan(self.hfov_rad / 2.0))

    @property
    def fy(self) -> float:
        return self.fx

    @property
    def cx(self) -> float:
        return self.width / 2.0

    @property
    def cy(self) -> float:
        return self.height / 2.0

    def K(self) -> np.ndarray:
        return np.array([[self.fx, 0, self.cx], [0, self.fy, self.cy], [0, 0, 1.0]])


def world_to_cam(points_w: np.ndarray, cam_pos: np.ndarray, cam_R: np.ndarray) -> np.ndarray:
    """(N,3) world points -> (N,3) camera-link coordinates (x forward = depth)."""
    return (np.asarray(points_w, float) - cam_pos) @ cam_R  # == R^T (p - t) row-wise


def project_cam(points_c: np.ndarray, cam: Camera) -> np.ndarray:
    """(N,3) camera-link points with x > 0 -> (N,2) pixel coordinates."""
    x = points_c[:, 0]
    u = cam.fx * (-points_c[:, 1] / x) + cam.cx
    v = cam.fy * (-points_c[:, 2] / x) + cam.cy
    return np.stack([u, v], axis=1)


def box_corners(center: np.ndarray, size: np.ndarray, yaw: float, pitch: float = 0.0) -> np.ndarray:
    """8 corners of an oriented 3D box (size = length, width, height)."""
    l, w, h = size
    sx = np.array([1, 1, 1, 1, -1, -1, -1, -1]) * l / 2
    sy = np.array([1, 1, -1, -1, 1, 1, -1, -1]) * w / 2
    sz = np.array([1, -1, 1, -1, 1, -1, 1, -1]) * h / 2
    local = np.stack([sx, sy, sz], axis=1)
    return local @ rot_zyx(yaw, pitch, 0.0).T + np.asarray(center, float)


_BOX_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
              (0, 4), (1, 5), (2, 6), (3, 7)]


def _clip_to_near(corners_c: np.ndarray) -> np.ndarray:
    """Points of the box in front of the near plane, adding edge intersections."""
    front = corners_c[:, 0] > NEAR_PLANE_M
    if front.all():
        return corners_c
    pts = [p for p, f in zip(corners_c, front) if f]
    for i, j in _BOX_EDGES:
        if front[i] != front[j]:
            a, b = corners_c[i], corners_c[j]
            t = (NEAR_PLANE_M - a[0]) / (b[0] - a[0])
            pts.append(a + t * (b - a))
    return np.array(pts) if pts else np.empty((0, 3))


def convex_hull(points: np.ndarray) -> np.ndarray:
    """Monotone-chain convex hull of (N,2) points, counter-clockwise."""
    pts = sorted(set(map(tuple, np.round(points, 6))))
    if len(pts) <= 2:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


@dataclass
class Projection:
    hull: np.ndarray        # (K,2) projected silhouette hull in pixels (unclipped)
    full_box: tuple         # (x1,y1,x2,y2) unclipped projected extent
    depth: float            # camera-frame x of the box centre (m)
    center_px: tuple        # projected 3D centre (may lie outside the image)
    in_front: bool          # box centre is in front of the camera


def project_box(center, size, yaw, cam_pos, cam_R, cam: Camera, pitch: float = 0.0) -> Projection | None:
    """Project an oriented 3D box. Returns None if fully behind the camera."""
    corners_c = world_to_cam(box_corners(center, size, yaw, pitch), cam_pos, cam_R)
    pts = _clip_to_near(corners_c)
    if len(pts) == 0:
        return None
    uv = project_cam(pts, cam)
    hull = convex_hull(uv)
    c_c = world_to_cam(np.asarray(center, float)[None], cam_pos, cam_R)[0]
    in_front = bool(c_c[0] > NEAR_PLANE_M)
    center_px = tuple(project_cam(c_c[None], cam)[0]) if in_front else (np.nan, np.nan)
    x1, y1 = uv.min(axis=0)
    x2, y2 = uv.max(axis=0)
    return Projection(hull, (float(x1), float(y1), float(x2), float(y2)),
                      float(c_c[0]), center_px, in_front)


def clip_box(box, width: int, height: int):
    x1, y1, x2, y2 = box
    cb = (max(0.0, x1), max(0.0, y1), min(float(width), x2), min(float(height), y2))
    if cb[2] <= cb[0] or cb[3] <= cb[1]:
        return None
    return cb


def box_iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between (N,4) and (M,4) xyxy arrays."""
    a = np.asarray(a, float).reshape(-1, 4)
    b = np.asarray(b, float).reshape(-1, 4)
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    ix1 = np.maximum(a[:, None, 0], b[None, :, 0])
    iy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    ix2 = np.minimum(a[:, None, 2], b[None, :, 2])
    iy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-12), 0.0)
