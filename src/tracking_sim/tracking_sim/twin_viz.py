"""Digital-twin visualisation of a simulated flight.

Shows the 3D world state from the scenario (targets, observer, camera field of
view, occluder panels, clutter) next to what the observer camera sees, with the
truth labels drawn on. Used by notebooks/digital_twin.ipynb.

Everything here reads ground truth: it is a visualisation of the simulation,
never an input to the tracker.
"""
from __future__ import annotations

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation

from .geometry import rot_zyx
from .render_toy import render_frame
from .scenario import Scenario

TRAIL_S = 2.0


def target_color(obj_id: int):
    """Same colour per target id as the label overlays (tracking_evaluation.audit.id_color)."""
    from tracking_evaluation.audit import id_color
    b, g, r = id_color(obj_id)
    return (r / 255, g / 255, b / 255)


def frustum_corners(sc: Scenario, f: int, depth: float) -> np.ndarray:
    """World coordinates of the four image corners projected to `depth` metres."""
    cam = sc.cam
    R = rot_zyx(*sc.cam_ypr[f])
    pts = []
    for u, v in ((0, 0), (cam.width, 0), (cam.width, cam.height), (0, cam.height)):
        ray_c = np.array([1.0, -(u - cam.cx) / cam.fx, -(v - cam.cy) / cam.fy])   # camera-link frame
        pts.append(sc.cam_pos[f] + R @ (ray_c * depth))
    return np.array(pts)


def _box_edges(center, size, yaw, pitch=0.0):
    from .geometry import box_corners
    c = box_corners(center, size, yaw, pitch)
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    return [(c[i], c[j]) for i, j in edges]


def world_limits(sc: Scenario, margin: float = 3.0):
    pts = [sc.cam_pos] + [o.pos if o.pos.ndim == 2 else o.pos[None] for o in sc.objects if o.kind != "occluder"]
    pts = np.vstack(pts)
    lo, hi = pts.min(axis=0) - margin, pts.max(axis=0) + margin
    lo[2] = 0.0
    span = (hi - lo).max()
    centre = (hi + lo) / 2
    lims = np.stack([centre - span / 2, centre + span / 2], axis=1)
    lims[2] = [0, max(hi[2], 1.0) * 1.15]
    return lims


def draw_world(ax, sc: Scenario, f: int, frame_truth: dict, lims, frustum_depth: float = 18.0,
               azim: float | None = None):
    """Draw the 3D world at frame f on a mplot3d axis."""
    ax.cla()
    fps = 1.0 / float(sc.times[1] - sc.times[0])
    trail = int(TRAIL_S * fps)
    status = {o["id"]: o for o in frame_truth["objects"]}

    for o in sc.objects:
        if o.kind == "clutter":
            pos, yaw, _ = o.pose_at(f)
            for a, b in _box_edges(pos, o.size, yaw):
                ax.plot(*zip(a, b), color="0.55", lw=0.6)
        elif o.kind == "occluder" and o.active[f]:
            pos, yaw, pitch = o.pose_at(f)
            for a, b in _box_edges(pos, o.size, yaw, pitch):
                ax.plot(*zip(a, b), color="0.35", lw=1.2)
        elif o.kind == "target":
            col = target_color(o.obj_id)
            p = o.pos[max(0, f - trail):f + 1]
            ax.plot(p[:, 0], p[:, 1], p[:, 2], color=col, lw=1.2, alpha=0.8)
            ax.plot(p[:, 0], p[:, 1], 0 * p[:, 2], color=col, lw=0.6, alpha=0.25)    # ground shadow
            x, y, z = o.pos[f]
            st = status.get(o.obj_id, {})
            seen = st.get("vis", 0) >= 0.5 and st.get("in_fov", False)
            ax.scatter([x], [y], [z], s=55, color=col if seen else "white", edgecolors=[col], linewidths=1.8,
                       depthshade=False)
            ax.text(x, y, z + 0.6, str(o.obj_id), color=col, fontsize=8)

    # observer, its recent path and the camera frustum
    cp = sc.cam_pos
    ax.plot(cp[max(0, f - trail):f + 1, 0], cp[max(0, f - trail):f + 1, 1], cp[max(0, f - trail):f + 1, 2],
            color="k", lw=1.2)
    ax.scatter(*cp[f], s=70, marker="^", color="k", depthshade=False)
    corners = frustum_corners(sc, f, frustum_depth)
    for c in corners:
        ax.plot(*zip(cp[f], c), color="k", lw=0.6, alpha=0.6)
    ax.plot(*np.vstack([corners, corners[:1]]).T, color="k", lw=0.6, alpha=0.6)

    ax.set_xlim(*lims[0]); ax.set_ylim(*lims[1]); ax.set_zlim(*lims[2])
    ax.set_box_aspect((1, 1, max(0.25, (lims[2][1] - lims[2][0]) / (lims[0][1] - lims[0][0]))))
    ax.set_xlabel("x (m)", fontsize=8); ax.set_ylabel("y (m)", fontsize=8); ax.set_zlabel("z (m)", fontsize=8)
    ax.tick_params(labelsize=7)
    if azim is not None:
        ax.view_init(elev=28, azim=azim)
    ax.set_title(f"digital twin   t = {sc.times[f]:5.2f} s   (filled = camera sees it, hollow = hidden/out of view)",
                 fontsize=9)


def camera_view(sc: Scenario, f: int, frame_truth: dict, ground_bgr, width: int = 640):
    from tracking_evaluation.audit import draw_truth
    img, _ = render_frame(sc, f, ground_bgr)
    img = draw_truth(img, frame_truth)
    h = int(img.shape[0] * width / img.shape[1])
    return cv2.cvtColor(cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)


def make_animation(sc: Scenario, truth: list, ground_bgr, every: int = 2, start: int = 0, stop: int | None = None,
                   rotate: bool = True, dpi: int = 80):
    """Matplotlib animation: 3D twin (left) and camera view with labels (right)."""
    frames = list(range(start, stop or sc.n_frames, every))
    lims = world_limits(sc)
    fig = plt.figure(figsize=(13, 5), dpi=dpi)
    ax3 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2)
    fig.subplots_adjust(left=0.0, right=0.99, top=0.93, bottom=0.03, wspace=0.02)
    yaw0 = np.degrees(np.mean(sc.cam_ypr[:, 0]))

    def update(k):
        f = frames[k]
        azim = (yaw0 - 150 + 40 * k / max(1, len(frames) - 1)) if rotate else yaw0 - 150
        draw_world(ax3, sc, f, truth[f], lims, azim=azim)
        ax2.cla()
        ax2.imshow(camera_view(sc, f, truth[f], ground_bgr))
        ax2.set_title("observer camera (toy render) with truth labels", fontsize=9)
        ax2.axis("off")
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(frames), interval=1000 * every / 20, blit=False)
    return fig, anim
