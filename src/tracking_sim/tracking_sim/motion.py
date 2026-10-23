"""Target paths and observer motion, sampled on the clip's frame times."""
from __future__ import annotations

import numpy as np


def _catmull_rom(points: np.ndarray, samples_per_seg: int = 40) -> np.ndarray:
    """Dense centripetal-free (uniform) Catmull-Rom curve through points."""
    p = np.vstack([points[0], points, points[-1]])
    out = []
    t = np.linspace(0, 1, samples_per_seg, endpoint=False)[:, None]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(points[-1][None])
    return np.vstack(out)


def _random_waypoints(rng, start, n, area_half, z_range, step_range):
    pts = [np.asarray(start, float)]
    for _ in range(n):
        for _attempt in range(50):
            ang = rng.uniform(-np.pi, np.pi)
            step = rng.uniform(*step_range)
            nxt = pts[-1][:2] + step * np.array([np.cos(ang), np.sin(ang)])
            if np.all(np.abs(nxt) <= area_half):
                break
        else:
            nxt = np.clip(nxt, -area_half, area_half)
        pts.append(np.array([nxt[0], nxt[1], rng.uniform(*z_range)]))
    return np.array(pts)


def target_path(rng, times, speed, area_half, z_range, cross_point=None, cross_time=None):
    """Constant-speed path along a smooth random curve.

    If cross_point/cross_time are given, the target passes cross_point at cross_time
    (used to script crossings between pairs of targets).
    Returns positions (F,3) and heading yaw (F,).
    """
    duration = times[-1] - times[0]
    need = speed * duration * 1.2 + 10.0
    step = (0.35 * area_half, 0.9 * area_half)
    if cross_point is None:
        start = np.array([*rng.uniform(-area_half, area_half, 2), rng.uniform(*z_range)])
        wps = _random_waypoints(rng, start, int(need / step[0]) + 3, area_half, z_range, step)
        curve = _catmull_rom(wps)
        s0 = 0.0
    else:
        cp = np.asarray(cross_point, float)
        back = _random_waypoints(rng, cp, int(need / step[0]) + 3, area_half, z_range, step)[::-1]
        fwd = _random_waypoints(rng, cp, int(need / step[0]) + 3, area_half, z_range, step)
        curve = _catmull_rom(np.vstack([back, fwd[1:]]))
    seg = np.linalg.norm(np.diff(curve, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if cross_point is not None:
        k = int(np.argmin(np.linalg.norm(curve - cross_point, axis=1)))
        s0 = s[k] - speed * (cross_time - times[0])
    query = np.clip(s0 + speed * (times - times[0]), 0, s[-1])
    pos = np.stack([np.interp(query, s, curve[:, i]) for i in range(3)], axis=1)
    vel = np.gradient(pos, times, axis=0)
    yaw = np.arctan2(vel[:, 1], vel[:, 0])
    return pos, np.unwrap(yaw)


def lowpass(x: np.ndarray, times: np.ndarray, tau_s: float) -> np.ndarray:
    """Zero-phase first-order low-pass (forward + backward) along axis 0.

    Used only to generate the scripted camera path, never at inference time.
    """
    if tau_s <= 0:
        return x.copy()
    dt = float(np.median(np.diff(times)))
    a = dt / (tau_s + dt)
    y = x.astype(float).copy()
    for i in range(1, len(y)):
        y[i] = y[i - 1] + a * (y[i] - y[i - 1])
    for i in range(len(y) - 2, -1, -1):
        y[i] = y[i + 1] + a * (y[i] - y[i + 1])
    return y


def observer_path(rng, times, profile: dict, standoff: float, height: float,
                  look_target: np.ndarray, smoothing_s: float):
    """Observer position (F,3) and yaw/pitch/roll (F,3).

    The observer orbits the scene centre at the stand-off distance, speed set by
    the camera-motion profile, and aims at the smoothed target centroid plus a
    yaw/pitch oscillation.
    """
    t = times - times[0]
    base_speed = rng.uniform(*profile["speed_mps"])
    osc = profile.get("speed_osc_frac", 0.0)
    speed = base_speed * (1 + osc * np.sin(2 * np.pi * t / rng.uniform(4.0, 7.0) + rng.uniform(0, 2 * np.pi)))
    direction = rng.choice([-1.0, 1.0])
    ang = rng.uniform(-np.pi, np.pi) + direction * np.concatenate([[0.0], np.cumsum(speed[1:] * np.diff(t))]) / standoff
    pos = np.stack([standoff * np.cos(ang), standoff * np.sin(ang), np.full_like(t, height)], axis=1)

    aim = lowpass(look_target, times, smoothing_s)
    d = aim - pos
    yaw = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    pitch = np.arctan2(-d[:, 2], np.hypot(d[:, 0], d[:, 1]))

    yaw_period = rng.uniform(*profile["yaw_osc_period_s"])
    yaw += np.deg2rad(profile["yaw_osc_amp_deg"]) * np.sin(2 * np.pi * t / yaw_period + rng.uniform(0, 2 * np.pi))
    pitch += np.deg2rad(profile["pitch_osc_amp_deg"]) * np.sin(2 * np.pi * t / (yaw_period * 1.37) + rng.uniform(0, 2 * np.pi))
    ypr = np.stack([yaw, pitch, np.zeros_like(t)], axis=1)
    return pos, ypr


def motion_stats(times, pos, ypr) -> dict:
    """Achieved camera-motion statistics, stored per clip for the factor check."""
    dt = np.diff(times)
    ang_rate = np.degrees(np.hypot(np.diff(ypr[:, 0]), np.diff(ypr[:, 1])) / dt)
    lin = np.linalg.norm(np.diff(pos, axis=0), axis=1) / dt
    return {
        "ang_rate_deg_s_median": float(np.median(ang_rate)),
        "ang_rate_deg_s_p95": float(np.percentile(ang_rate, 95)),
        "speed_mps_median": float(np.median(lin)),
        "speed_mps_max": float(np.max(lin)),
        "accel_mps2_p95": float(np.percentile(np.abs(np.diff(lin) / dt[1:]), 95)),
    }
