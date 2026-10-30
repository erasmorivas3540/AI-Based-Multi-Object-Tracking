"""Builds notebooks/digital_twin.ipynb (run from the repo root)."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Digital twin: watching the simulated drones fly

Every flight in the study is fully described by its **scenario**: the position and orientation of every drone, car, occluder panel, piece of clutter and the observer camera, at every one of the 400 frames (20 s at 20 fps). That synchronised world state is the *digital twin* of the flight.

This notebook shows the twin and the camera side by side:
- **Left:** the 3D world. Drones with 2-second trails, the observer (▲) with its camera field of view, occluder panels when active, ground clutter.
- **Right:** what the observer camera sees, with the truth labels drawn on.

A drone is drawn **filled** when the camera can see it (visible ≥ 50% and in view) and **hollow** when it's hidden or out of view. Colours match between the two panels.

Notes:
- The camera view here comes from the **toy renderer**. Gazebo will render real frames from exactly the same world state.
- It's a twin of the *simulation*, not of real drones, and it reads ground truth, so it's a visualisation, never a tracker input.
- Runtime: about 2 minutes. It works without Gazebo or a GPU. Run from the repo's `notebooks/` folder after `pip install -r requirements-eval.txt matplotlib`.
""")

code("""
import sys, shutil
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
for p in ["src/tracking_sim", "src/tracking_evaluation", "src/tracking_detector"]:
    sys.path.insert(0, str(ROOT / p))

import numpy as np, yaml
import matplotlib.pyplot as plt
from IPython.display import Image, Video, display
from tracking_sim.design import load_design
from tracking_sim.scenario import Scenario, build_scenario
from tracking_sim.truth import compute_truth, read_truth, write_truth
from tracking_sim.twin_viz import draw_world, camera_view, make_animation, world_limits, target_color

CFG = yaml.safe_load((ROOT / "configs/scenario_design.yaml").read_text())
DESIGN = load_design(ROOT / "manifests")
OUT = ROOT / "outputs/twin"; OUT.mkdir(parents=True, exist_ok=True)

def load_flight(flight_id):
    \"\"\"Load a built flight from data/, or build it now (~20 s) if it isn't there.\"\"\"
    d = ROOT / "data" / flight_id
    if (d / "truth.jsonl").exists():
        sc = Scenario.load(d / "scenario"); _, truth = read_truth(d / "truth.jsonl")
    else:
        fl = next(f for f in DESIGN["flights"] if f["flight_id"] == flight_id)
        sc = build_scenario(CFG, fl); truth = compute_truth(sc)
        sc.save(d / "scenario"); write_truth(truth, d / "truth.jsonl", fl)
    ground = tuple(int(c) for c in CFG["layouts"][sc.clip["layout"]]["ground_rgb"][::-1])
    return sc, truth, ground

FLIGHT = "dev_uav_turning_occ10_s0"     # try any flight id from manifests/design.json
sc, truth, ground = load_flight(FLIGHT)
print(f"{FLIGHT}: {sc.stats['n_targets']} UAVs, camera '{sc.clip['camera_motion']}', "
      f"{sc.clip['occlusion_s']} s occlusions, layout {sc.clip['layout']}")
for s in sc.schedule:
    print(f"  occluder slot {s['slot']}: hides target {s['target_id']} from {s['t_start']:.2f} s to {s['t_end']:.2f} s")
""")

md("""
## 1. The whole flight from above

Every drone's full 20-second path (colour = drone id), the observer's orbit (black) and where each scheduled occlusion happens (✕ at the hidden drone's position mid-occlusion).
""")

code("""
fig, ax = plt.subplots(figsize=(7.5, 7.5))
for o in sc.targets():
    ax.plot(o.pos[:, 0], o.pos[:, 1], color=target_color(o.obj_id), lw=1.5, label=f"drone {o.obj_id}")
    ax.scatter(*o.pos[0, :2], color=target_color(o.obj_id), s=25)
for o in sc.objects:
    if o.kind == "clutter":
        ax.scatter(*o.pos[:2], marker="s", color="0.6", s=12)
ax.plot(sc.cam_pos[:, 0], sc.cam_pos[:, 1], "k-", lw=2, label="observer path")
ax.scatter(*sc.cam_pos[0, :2], marker="^", color="k", s=80)
for s in sc.schedule:
    o = next(t for t in sc.targets() if t.obj_id == s["target_id"])
    f = int((s["t_start"] + s["t_end"]) / 2 * 20)
    ax.scatter(*o.pos[f, :2], marker="x", s=120, color=target_color(o.obj_id), linewidths=3)
ax.set_aspect("equal"); ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
ax.set_title("Top-down view: dots = start, ✕ = scheduled occlusion, squares = clutter")
ax.legend(fontsize=8, loc="upper right"); plt.tight_layout(); plt.show()
""")

md("""
## 2. One moment: an occlusion in progress

The middle of the second scheduled occlusion. The hidden drone appears **hollow** in the twin. In the camera view it is the ✕ behind the grey panel. The panel sits on the camera's line of sight to that drone.
""")

code("""
s = sc.schedule[1]
f = int((s["t_start"] + s["t_end"]) / 2 * 20)
fig = plt.figure(figsize=(14, 5.2))
ax3 = fig.add_subplot(1, 2, 1, projection="3d"); ax2 = fig.add_subplot(1, 2, 2)
draw_world(ax3, sc, f, truth[f], world_limits(sc), azim=np.degrees(np.mean(sc.cam_ypr[:, 0])) - 150)
ax2.imshow(camera_view(sc, f, truth[f], ground)); ax2.axis("off"); ax2.set_title("observer camera", fontsize=9)
plt.tight_layout(); plt.show()
""")

md("""
## 3. The animation

The full flight at 10 fps (every 2nd frame) with the 3D view slowly orbiting. It's saved to `outputs/twin/` as MP4 if `ffmpeg` is installed, otherwise as GIF. Rendering takes about 1–2 minutes.
""")

code("""
fig, anim = make_animation(sc, truth, ground, every=2)
plt.close(fig)
if shutil.which("ffmpeg"):
    path = OUT / f"{FLIGHT}.mp4"
    anim.save(path, writer="ffmpeg", fps=10, dpi=80, bitrate=1800)
    display(Video(str(path), embed=True, width=980))
else:
    path = OUT / f"{FLIGHT}.gif"
    anim.save(path, writer="pillow", fps=10, dpi=70)
    display(Image(filename=str(path), width=980))
print("saved", path.relative_to(ROOT), f"({path.stat().st_size / 1e6:.1f} MB)")
""")

md("""
## 4. Same twin, ground vehicles

A car flight with a 2-second occlusion and the low-motion camera, from 3 to 9 seconds.
""")

code("""
CAR = "dev_ground_low_occ20_s0"
sc2, truth2, ground2 = load_flight(CAR)
fig, anim = make_animation(sc2, truth2, ground2, every=2, start=60, stop=180)
plt.close(fig)
if shutil.which("ffmpeg"):
    path = OUT / f"{CAR}.mp4"; anim.save(path, writer="ffmpeg", fps=10, dpi=80, bitrate=1800)
    display(Video(str(path), embed=True, width=980))
else:
    path = OUT / f"{CAR}.gif"; anim.save(path, writer="pillow", fps=10, dpi=70)
    display(Image(filename=str(path), width=980))
""")

md("""
## 5. (Optional) Interactive 3D twin

Drag to rotate, scroll to zoom, and press ▶ or use the slider to scrub through time (every 0.5 s). Needs `pip install plotly`.
""")

code("""
try:
    import plotly.graph_objects as go
except ImportError:
    print("Optional: pip install plotly, then re-run this cell.")
else:
    step = 10
    fr_idx = list(range(0, sc.n_frames, step))
    tg = sc.targets()

    def traces(f):
        out = []
        for o in tg:
            seen = next((x for x in truth[f]["objects"] if x["id"] == o.obj_id), {})
            vis = seen.get("vis", 0) >= 0.5 and seen.get("in_fov", False)
            col = "rgb(%d,%d,%d)" % tuple(int(255 * c) for c in target_color(o.obj_id))
            p = o.pos[max(0, f - 40):f + 1]
            out.append(go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode="lines", line=dict(color=col, width=4),
                                    showlegend=False, hoverinfo="skip"))
            out.append(go.Scatter3d(x=[o.pos[f, 0]], y=[o.pos[f, 1]], z=[o.pos[f, 2]], mode="markers+text",
                                    text=[str(o.obj_id)], name=f"drone {o.obj_id}",
                                    marker=dict(size=7, color=col if vis else "white", line=dict(color=col, width=3))))
        cp = sc.cam_pos
        out.append(go.Scatter3d(x=cp[:f + 1, 0], y=cp[:f + 1, 1], z=cp[:f + 1, 2], mode="lines",
                                line=dict(color="black", width=3), name="observer"))
        occ = [o for o in sc.objects if o.kind == "occluder" and o.active[f]]
        out.append(go.Scatter3d(x=[o.pos[f, 0] for o in occ] or [None], y=[o.pos[f, 1] for o in occ] or [None],
                                z=[o.pos[f, 2] for o in occ] or [None], mode="markers", name="occluder panel",
                                marker=dict(size=12, symbol="square", color="grey")))
        return out

    lims = world_limits(sc)
    fig = go.Figure(data=traces(0), frames=[go.Frame(data=traces(f), name=f"{sc.times[f]:.1f}") for f in fr_idx])
    fig.update_layout(
        height=620, title=f"Interactive digital twin: {FLIGHT}",
        scene=dict(xaxis=dict(range=list(lims[0])), yaxis=dict(range=list(lims[1])), zaxis=dict(range=list(lims[2])),
                   aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.35)),
        updatemenus=[dict(type="buttons", x=0.05, y=0.05, buttons=[
            dict(label="▶", method="animate", args=[None, dict(frame=dict(duration=300), fromcurrent=True)]),
            dict(label="❚❚", method="animate", args=[[None], dict(mode="immediate")])])],
        sliders=[dict(steps=[dict(label=f"{sc.times[f]:.1f}s", method="animate",
                                  args=[[f"{sc.times[f]:.1f}"], dict(mode="immediate")]) for f in fr_idx])])
    fig.show()
""")

md("""
## What this shows, and what's next

- The world state, the occlusion schedule and the labels all come from one deterministic scenario. The camera view and the twin always agree, and any flight can be replayed exactly from its seed.
- Once Gazebo is verified (`docs/gazebo_verification.md`), the right-hand panel can show Gazebo frames instead: load `data/<flight>/frames/*.png` in place of `camera_view(...)`.
- Week 5 adds the tracker's outputs (track ids and forecasts) to the same view, so identity recoveries and failures can be watched directly.
""")

nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, "notebooks/digital_twin.ipynb")
print("written notebooks/digital_twin.ipynb")
