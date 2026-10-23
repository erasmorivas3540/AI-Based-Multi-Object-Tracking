"""Analytic per-frame ground truth from a scenario.

For every target and frame: full projected extent, box clipped to the image,
visible box and visible fraction after occlusion by nearer objects, whether the
centre is in the field of view, and which object occludes it most.

These labels never enter inference. They are written to truth.jsonl in the clip
folder and are cross-checked against Gazebo's own bounding-box camera.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import box as sbox
from shapely.ops import unary_union

from .geometry import rot_zyx
from .scenario import Scenario
from .shapes import silhouette

SCHEMA_VERSION = 2  # 2: silhouettes from composite part shapes


def frame_truth(sc: Scenario, f: int) -> dict:
    cam = sc.cam
    R = rot_zyx(*sc.cam_ypr[f])
    img = sbox(0, 0, cam.width, cam.height)
    projected = []
    for o in sc.objects:
        if o.kind == "occluder" and not o.active[f]:
            continue
        sil = silhouette(o, f, sc.cam_pos[f], R, cam)
        if sil is None:
            continue
        poly, _hulls, depth, center_px, in_front = sil
        projected.append((depth, o, poly, center_px, in_front))
    projected.sort(key=lambda x: x[0])  # near to far (painter's order by centre depth)

    records = []
    nearer = []  # (name, obj_id, polygon) of objects already processed
    for depth, o, poly, center_px, in_front in projected:
        if o.kind == "target":
            in_img = poly.intersection(img)
            in_img_area = in_img.area
            occluders = unary_union([q for _, _, q in nearer]) if nearer else None
            visible = in_img.difference(occluders) if occluders is not None and in_img_area > 0 else in_img
            vis = visible.area / in_img_area if in_img_area > 0 else 0.0
            occ_by = None
            if nearer and in_img_area > 0 and vis < 0.999:
                overlaps = [(q.intersection(in_img).area, name) for name, _, q in nearer]
                best = max(overlaps)
                occ_by = best[1] if best[0] > 0 else None
            cx, cy = center_px
            in_fov = bool(in_front and 0 <= cx < cam.width and 0 <= cy < cam.height
                          and in_img_area >= 0.5 * poly.area)
            clipped = in_img.bounds if in_img_area > 0 else None
            vbox = visible.bounds if (not visible.is_empty and visible.area > 0) else None
            pos, yaw, _ = o.pose_at(f)
            records.append({
                "id": o.obj_id, "cls": o.cls,
                "full_box": [round(v, 2) for v in poly.bounds],
                "box": [round(v, 2) for v in clipped] if clipped else None,
                "visible_box": [round(v, 2) for v in vbox] if vbox else None,
                "vis": round(float(vis), 4),
                "in_image_frac": round(float(in_img_area / poly.area), 4) if poly.area > 0 else 0.0,
                "in_fov": in_fov,
                "occluded_by": occ_by,
                "depth_m": round(depth, 3),
                "center_px": [round(float(cx), 2), round(float(cy), 2)] if in_front else None,
                "pos_m": [round(float(v), 3) for v in pos],
                "yaw": round(yaw, 4),
            })
        nearer.append((o.name, o.obj_id, poly))

    # Targets fully behind the camera never appear above; record them as unseen.
    seen = {r["id"] for r in records}
    for o in sc.targets():
        if o.obj_id not in seen:
            pos, yaw, _ = o.pose_at(f)
            records.append({"id": o.obj_id, "cls": o.cls, "full_box": None, "box": None,
                            "visible_box": None, "vis": 0.0, "in_image_frac": 0.0, "in_fov": False,
                            "occluded_by": None, "depth_m": None, "center_px": None,
                            "pos_m": [round(float(v), 3) for v in pos], "yaw": round(yaw, 4)})
    records.sort(key=lambda r: r["id"])
    return {"frame": f + 1, "t": round(float(sc.times[f]), 4),
            "camera": {"pos_m": [round(float(v), 3) for v in sc.cam_pos[f]],
                       "ypr_rad": [round(float(v), 5) for v in sc.cam_ypr[f]]},
            "occluders_active": [o.name for o in sc.objects if o.kind == "occluder" and o.active[f]],
            "objects": records}


def compute_truth(sc: Scenario) -> list[dict]:
    return [frame_truth(sc, f) for f in range(sc.n_frames)]


def write_truth(truth: list[dict], path: Path, clip: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        fh.write(json.dumps({"schema_version": SCHEMA_VERSION, "clip": clip}) + "\n")
        for rec in truth:
            fh.write(json.dumps(rec) + "\n")


def read_truth(path: Path) -> tuple[dict, list[dict]]:
    lines = Path(path).read_text().splitlines()
    header = json.loads(lines[0])
    if header.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"truth schema {header.get('schema_version')} != {SCHEMA_VERSION}")
    return header, [json.loads(x) for x in lines[1:]]


def truth_arrays(truth: list[dict]):
    """Per-target arrays over frames: vis, in_fov, visible-box min side, visible boxes."""
    ids = sorted({o["id"] for fr in truth for o in fr["objects"]})
    F = len(truth)
    vis = np.zeros((len(ids), F))
    in_fov = np.zeros((len(ids), F), bool)
    min_side = np.zeros((len(ids), F))
    boxes = np.full((len(ids), F, 4), np.nan)
    occ_by = [[None] * F for _ in ids]
    idx = {i: k for k, i in enumerate(ids)}
    for f, fr in enumerate(truth):
        for o in fr["objects"]:
            k = idx[o["id"]]
            vis[k, f] = o["vis"]
            in_fov[k, f] = o["in_fov"]
            occ_by[k][f] = o["occluded_by"]
            if o["visible_box"]:
                b = o["visible_box"]
                boxes[k, f] = b
                min_side[k, f] = min(b[2] - b[0], b[3] - b[1])
    return ids, vis, in_fov, min_side, boxes, occ_by
