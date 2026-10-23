"""Deterministic clip scenarios: every pose of every object at every frame.

A scenario is the single source of truth for one rendered flight. Gazebo (via
the director) and the toy renderer both draw from it, and the analytic labels
are computed from it, so all three can be cross-checked.
"""
from __future__ import annotations

import json
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .geometry import Camera, project_box, rot_zyx
from .motion import motion_stats, observer_path, target_path

PARK_Z = -100.0  # inactive occluders are parked far below the ground plane


@dataclass
class SceneObject:
    name: str
    kind: str                 # "target" | "occluder" | "clutter"
    size: list                # (length, width, height) metres
    pos: np.ndarray           # (F,3) or (3,) for static
    yaw: np.ndarray           # (F,) or scalar
    pitch: np.ndarray | float = 0.0
    obj_id: int = 0           # persistent target identity (1..N); 0 for non-targets
    cls: str = ""
    active: np.ndarray | None = None  # occluders: (F,) bool

    def pose_at(self, f: int):
        pos = self.pos if self.pos.ndim == 1 else self.pos[f]
        yaw = float(self.yaw) if np.ndim(self.yaw) == 0 else float(self.yaw[f])
        pitch = float(self.pitch) if np.ndim(self.pitch) == 0 else float(self.pitch[f])
        return pos, yaw, pitch


@dataclass
class Scenario:
    clip: dict                # flight id, seed, factors, layout
    times: np.ndarray         # (F,) seconds, simulation time
    cam: Camera
    cam_pos: np.ndarray       # (F,3)
    cam_ypr: np.ndarray       # (F,3)
    objects: list = field(default_factory=list)
    schedule: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def n_frames(self) -> int:
        return len(self.times)

    def targets(self):
        return [o for o in self.objects if o.kind == "target"]

    # ---------------------------------------------------------------- io
    def save(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {"times": self.times, "cam_pos": self.cam_pos, "cam_ypr": self.cam_ypr}
        meta_objs = []
        for i, o in enumerate(self.objects):
            arrays[f"o{i}_pos"] = np.asarray(o.pos)
            arrays[f"o{i}_yaw"] = np.asarray(o.yaw)
            arrays[f"o{i}_pitch"] = np.asarray(o.pitch)
            if o.active is not None:
                arrays[f"o{i}_active"] = o.active
            meta_objs.append({"name": o.name, "kind": o.kind, "size": list(map(float, o.size)),
                              "obj_id": o.obj_id, "cls": o.cls, "has_active": o.active is not None})
        np.savez_compressed(path.with_suffix(".npz"), **arrays)
        meta = {"clip": self.clip, "camera": asdict(self.cam) | {"hfov_rad": float(self.cam.hfov_rad)},
                "objects": meta_objs, "schedule": self.schedule, "stats": self.stats}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=1, default=_json_default))

    @classmethod
    def load(cls, path: Path) -> "Scenario":
        path = Path(path)
        meta = json.loads(path.with_suffix(".json").read_text())
        a = np.load(path.with_suffix(".npz"))
        objs = []
        for i, m in enumerate(meta["objects"]):
            objs.append(SceneObject(m["name"], m["kind"], m["size"], a[f"o{i}_pos"], a[f"o{i}_yaw"],
                                    a[f"o{i}_pitch"], m["obj_id"], m["cls"],
                                    a[f"o{i}_active"] if m["has_active"] else None))
        cam = Camera(**meta["camera"])
        return cls(meta["clip"], a["times"], cam, a["cam_pos"], a["cam_ypr"], objs,
                   meta["schedule"], meta["stats"])


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _target_eligible(cam, cam_pos, cam_ypr, tgt: SceneObject, frames, min_side_px=6.0, margin_px=8.0):
    """Target fully in the image and large enough over all frames (no occluders considered)."""
    for f in frames:
        pos, yaw, pitch = tgt.pose_at(f)
        p = project_box(pos, tgt.size, yaw, cam_pos[f], rot_zyx(*cam_ypr[f]), cam, pitch)
        if p is None or not p.in_front:
            return False
        x1, y1, x2, y2 = p.full_box
        if x1 < margin_px or y1 < margin_px or x2 > cam.width - margin_px or y2 > cam.height - margin_px:
            return False
        if min(x2 - x1, y2 - y1) < min_side_px:
            return False
    return True


def build_scenario(cfg: dict, clip: dict) -> Scenario:
    """Build every pose for one flight.

    clip: {flight_id, seed, camera_motion, occlusion_s, target_group, layout, split}
    """
    rng = np.random.default_rng(int(clip["seed"]))
    fps = cfg["clip"]["fps"]
    n = int(round(cfg["clip"]["duration_s"] * fps))
    times = np.arange(n) / fps
    cam = Camera(cfg["camera"]["width"], cfg["camera"]["height"], np.deg2rad(cfg["camera"]["hfov_deg"]))
    group = clip["target_group"]
    tcfg = cfg["targets"][group]

    # ------------------------------------------------------------ targets
    n_t = int(rng.integers(tcfg["count"][0], tcfg["count"][1] + 1))
    crossing_pairs = []
    order = rng.permutation(n_t)
    for c in range(min(cfg["targets"]["crossings_per_clip"], n_t // 2)):
        crossing_pairs.append((int(order[2 * c]), int(order[2 * c + 1])))
    cross_info = {}
    for a, b in crossing_pairs:
        cp = np.array([*rng.uniform(-0.5, 0.5, 2) * tcfg["area_half_m"], rng.uniform(*tcfg["altitude_m"])])
        tc = float(rng.uniform(6.0, 14.0))
        cross_info[a] = (cp, tc)
        if group == "uav":
            cross_info[b] = (cp + np.array([0, 0, 0.6]), tc)       # vertical separation
        else:
            cross_info[b] = (cp, tc + 0.6)                          # pass 0.6 s apart
    objects = []
    for i in range(n_t):
        speed = rng.uniform(*tcfg["speed_mps"])
        cp, tc = cross_info.get(i, (None, None))
        pos, yaw = target_path(rng, times, speed, tcfg["area_half_m"], tcfg["altitude_m"], cp, tc)
        objects.append(SceneObject(f"target_{i + 1}", "target", list(tcfg["size_m"]), pos, yaw,
                                   0.0, obj_id=i + 1, cls=group))

    # ------------------------------------------------------------ observer
    centroid = np.mean([o.pos for o in objects], axis=0)
    ocfg = cfg["observer"][group]
    profile = cfg["factors"]["camera_motion"][clip["camera_motion"]]
    cam_pos, cam_ypr = observer_path(rng, times, profile, ocfg["standoff_m"], ocfg["height_m"],
                                     centroid, cfg["observer"]["look_at_smoothing_s"])

    # ------------------------------------------------------------ clutter (layout)
    lay = cfg["layouts"][clip["layout"]]
    # Layout clutter depends only on the layout name, so a layout looks the same in
    # every flight that uses it (and layouts are never shared across dev/test).
    lay_rng = np.random.default_rng(zlib.crc32(clip["layout"].encode()))
    smin, smax = np.array(cfg["clutter"]["size_m"][0]), np.array(cfg["clutter"]["size_m"][1])
    for k in range(lay["clutter"]):
        r = tcfg["area_half_m"] * lay_rng.uniform(*cfg["clutter"]["ring_m"])
        a = lay_rng.uniform(-np.pi, np.pi)
        size = lay_rng.uniform(smin, smax)
        objects.append(SceneObject(f"clutter_{k}", "clutter", list(size),
                                   np.array([r * np.cos(a), r * np.sin(a), size[2] / 2]),
                                   np.array(lay_rng.uniform(-np.pi, np.pi)), 0.0))

    # ------------------------------------------------------------ occluders
    occ = cfg["occlusion"]
    duration = float(clip["occlusion_s"])
    mode = "occlude" if duration > 0 else "near_miss"
    hold = duration if duration > 0 else occ["near_miss_hold_s"]
    targets = [o for o in objects if o.kind == "target"]
    used, schedule = set(), []
    for slot, t_nom in enumerate(occ["nominal_starts_s"][: occ["events_per_clip"]]):
        t0 = t_nom + rng.uniform(-occ["start_jitter_s"], occ["start_jitter_s"])
        chosen = None
        for shift in [0.0, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75]:
            ts = t0 + shift
            lo = ts - occ["eligibility_margin_s"]
            hi = ts + hold + occ["eligibility_margin_s"]
            if lo < times[0] or hi > times[-1]:
                continue
            frames = range(int(np.floor(lo * fps)), int(np.ceil(hi * fps)) + 1)
            for tgt in rng.permutation(targets):
                if tgt.obj_id in used:
                    continue
                if _target_eligible(cam, cam_pos, cam_ypr, tgt, frames):
                    chosen = (tgt, ts)
                    break
            if chosen:
                break
        panel = SceneObject(f"occluder_{slot}", "occluder", [occ["thickness_m"], 1.0, 1.0],
                            np.tile([0.0, 0.0, PARK_Z], (n, 1)), np.zeros(n), np.zeros(n),
                            active=np.zeros(n, bool))
        if chosen is None:
            schedule.append({"slot": slot, "status": "skipped_no_eligible_target", "mode": mode})
            objects.append(panel)
            continue
        tgt, ts = chosen
        used.add(tgt.obj_id)
        cover_start, cover_len = ts, hold
        achieved = None
        if mode == "occlude":
            # Calibrate: the slide-in/out also hides the target, so shrink the
            # full-cover window until the span with vis < threshold equals the
            # nominal duration (to within one frame).
            want = int(round(duration * fps))
            for _ in range(6):
                _reset_panel(panel, n)
                _script_panel(panel, tgt, cam_pos, times, cover_start, cover_len, mode, occ)
                achieved = _hidden_frames(cam, cam_pos, cam_ypr, tgt, panel, occ["calibrate_vis_threshold"])
                excess = len(achieved) - want
                if abs(excess) <= 1:
                    break
                cover_len = max(0.0, cover_len - excess / fps)
                cover_start += excess / (2 * fps)
        else:
            _script_panel(panel, tgt, cam_pos, times, cover_start, cover_len, mode, occ)
        entry = {"slot": slot, "status": "scheduled", "mode": mode, "target_id": tgt.obj_id,
                 "t_start": round(ts, 4), "t_end": round(ts + hold, 4),
                 "cover_start": round(cover_start, 4), "cover_len": round(cover_len, 4),
                 "panel_side_m": panel.size[1]}
        if achieved is not None:
            entry["achieved_hidden_s"] = round(len(achieved) / fps, 3)
            entry["t_start"] = round(achieved[0] / fps, 4) if len(achieved) else entry["t_start"]
            entry["t_end"] = round((achieved[-1] + 1) / fps, 4) if len(achieved) else entry["t_end"]
        schedule.append(entry)
        objects.append(panel)

    stats = motion_stats(times, cam_pos, cam_ypr) | {"n_targets": n_t, "crossing_pairs":
                                                     [[a + 1, b + 1] for a, b in crossing_pairs]}
    return Scenario(dict(clip), times, cam, cam_pos, cam_ypr, objects, schedule, stats)


def _reset_panel(panel: SceneObject, n: int):
    panel.pos = np.tile([0.0, 0.0, PARK_Z], (n, 1))
    panel.yaw = np.zeros(n)
    panel.pitch = np.zeros(n)
    panel.active = np.zeros(n, bool)


def _hidden_frames(cam, cam_pos, cam_ypr, tgt, panel, vis_thr):
    """Frames where the panel alone hides the target below vis_thr."""
    from .shapes import silhouette

    out = []
    for f in np.flatnonzero(panel.active):
        R = rot_zyx(*cam_ypr[f])
        st = silhouette(tgt, int(f), cam_pos[f], R, cam)
        sp = silhouette(panel, int(f), cam_pos[f], R, cam)
        if st is None or sp is None or st[0].area == 0:
            continue
        if st[0].difference(sp[0]).area / st[0].area < vis_thr:
            out.append(int(f))
    return out


def _script_panel(panel: SceneObject, tgt: SceneObject, cam_pos, times, t0, hold, mode, occ):
    f = occ["depth_fraction"]
    side = max(occ["min_panel_m"], max(tgt.size) * f * occ["cover_margin"])
    panel.size = [occ["thickness_m"], side, side]
    r_t = 0.5 * max(tgt.size) * f
    s_off = side / 2 + r_t + 1.2 * side
    s_hold = 0.0 if mode == "occlude" else side / 2 + r_t + occ["near_miss_gap_frac"] * side
    tau = occ["ramp_s"]
    t1 = t0 + hold
    for i, t in enumerate(times):
        if t < t0 - tau or t > t1 + tau:
            continue
        if t < t0:
            off = s_hold + (s_off - s_hold) * (1 - _smoothstep((t - (t0 - tau)) / tau))
        elif t <= t1:
            off = s_hold
        else:
            off = s_hold + (s_off - s_hold) * _smoothstep((t - t1) / tau)
        los = tgt.pos[i] - cam_pos[i]
        u = los / np.linalg.norm(los)
        right = np.cross(u, [0.0, 0.0, 1.0])
        right /= max(np.linalg.norm(right), 1e-9)
        panel.pos[i] = cam_pos[i] + f * los + off * right
        panel.yaw[i] = np.arctan2(u[1], u[0])
        panel.pitch[i] = np.arctan2(-u[2], np.hypot(u[0], u[1]))
        panel.active[i] = True
