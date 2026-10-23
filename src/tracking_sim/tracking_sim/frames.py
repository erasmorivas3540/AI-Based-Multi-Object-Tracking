"""Frame storage layout and the post-render blur condition.

Flight folder layout (data/<flight_id>/):
    scenario.json / scenario.npz   every pose of every object (from build_scenario)
    truth.jsonl                    analytic labels (from truth.compute_truth)
    frames/000001.png ...          canonical un-blurred frames (Gazebo or toy renderer)
    render.json                    which renderer produced the frames, versions, timing
    gz_boxes.jsonl                 Gazebo bounding-box camera output (Gazebo only)

Blur variants are generated deterministically from the canonical frame, so both
blur conditions of a flight share identical content apart from the degradation.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .scenario import Scenario


def frame_path(flight_dir: Path, frame: int) -> Path:
    return Path(flight_dir) / "frames" / f"{frame:06d}.png"


def motion_blur_kernel(length: int, angle_rad: float) -> np.ndarray:
    k = np.zeros((length, length), np.float32)
    c = (length - 1) / 2
    dx, dy = np.cos(angle_rad), np.sin(angle_rad)
    for t in np.linspace(-c, c, 4 * length):
        x, y = int(round(c + t * dx)), int(round(c + t * dy))
        k[y, x] = 1.0
    return k / k.sum()


def blur_angles(sc: Scenario) -> np.ndarray:
    """Per-frame image-motion direction from the scripted camera rotation.

    Used only to orient the synthetic blur when generating data. The direction
    of the frame's own camera motion: a yaw turn smears horizontally, a pitch
    change vertically.
    """
    d = np.diff(sc.cam_ypr[:, :2], axis=0, prepend=sc.cam_ypr[:1, :2])
    d[0] = d[1] if len(d) > 1 else d[0]
    dx = sc.cam.fx * d[:, 0]
    dy = -sc.cam.fy * d[:, 1]
    ang = np.arctan2(dy, dx)
    ang[np.hypot(dx, dy) < 1e-6] = 0.0
    return ang


def apply_blur(img: np.ndarray, length: int, angle_rad: float) -> np.ndarray:
    if length <= 1:
        return img
    return cv2.filter2D(img, -1, motion_blur_kernel(int(length), float(angle_rad)),
                        borderType=cv2.BORDER_REFLECT)


def load_frame(flight_dir: Path, frame: int, blur_px: int = 0, angles: np.ndarray | None = None) -> np.ndarray:
    img = cv2.imread(str(frame_path(flight_dir, frame)), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(frame_path(flight_dir, frame))
    if blur_px > 1:
        if angles is None:
            angles = blur_angles(Scenario.load(Path(flight_dir) / "scenario"))
        img = apply_blur(img, blur_px, angles[frame - 1])
    return img
