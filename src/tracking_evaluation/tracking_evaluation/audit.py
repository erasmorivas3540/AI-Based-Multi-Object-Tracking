"""Visual label audit: draw truth on frames so a person can check it.

Legend:
  solid box, id + vis   visible box of an observable target
  thin box              full projected extent when partly hidden
  X + id                centre of a hidden target that is still in view
  magenta box           Gazebo bounding-box camera output, when available
"""
from __future__ import annotations

import colorsys

import cv2
import numpy as np


def id_color(i: int):
    h = (i * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return int(b * 255), int(g * 255), int(r * 255)


def draw_truth(img, frame_truth: dict, vis_thr: float = 0.5, gz_boxes=None, header: str = ""):
    out = img.copy()
    for o in frame_truth["objects"]:
        c = id_color(o["id"])
        if o["visible_box"]:
            x1, y1, x2, y2 = map(int, o["visible_box"])
            th = 2 if o["vis"] >= vis_thr else 1
            cv2.rectangle(out, (x1, y1), (x2, y2), c, th)
            if o["vis"] < 0.999 and o["full_box"]:
                fx1, fy1, fx2, fy2 = map(int, o["full_box"])
                cv2.rectangle(out, (fx1, fy1), (fx2, fy2), c, 1, cv2.LINE_4)
            cv2.putText(out, f"{o['id']} {o['vis']:.2f}", (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1, cv2.LINE_AA)
        elif o["in_fov"] and o["center_px"]:
            cx, cy = map(int, o["center_px"])
            cv2.drawMarker(out, (cx, cy), c, cv2.MARKER_TILTED_CROSS, 14, 2)
            cv2.putText(out, f"{o['id']} hidden ({o['occluded_by']})", (cx + 8, cy - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1, cv2.LINE_AA)
    for b in gz_boxes or []:
        x1, y1, x2, y2 = map(int, b["box"])
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 0, 255), 1)
    txt = f"f{frame_truth['frame']} t={frame_truth['t']:.2f}s {header}"
    cv2.rectangle(out, (0, 0), (len(txt) * 9 + 10, 22), (0, 0, 0), -1)
    cv2.putText(out, txt, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def contact_sheet(images, cols: int = 3, width: int = 640):
    tiles = []
    for im in images:
        h = int(im.shape[0] * width / im.shape[1])
        tiles.append(cv2.resize(im, (width, h), interpolation=cv2.INTER_AREA))
    h = max(t.shape[0] for t in tiles)
    rows = []
    for i in range(0, len(tiles), cols):
        row = tiles[i:i + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[i:i + cols]))
        rows.append(np.hstack([cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in row]))
    return np.vstack(rows)
