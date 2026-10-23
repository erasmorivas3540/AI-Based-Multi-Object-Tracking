"""Render one flight in Gazebo Harmonic, frame-locked to the scenario.

    python scripts/gz_render_flight.py --flight dev_uav_low_occ10_s0 --max-frames 40   # first check
    python scripts/gz_render_flight.py --flight dev_uav_low_occ10_s0                    # full flight

Needs the scenario from scripts/build_flights.py. ROS 2 is NOT needed: this talks
to Gazebo directly through gz-transport's Python bindings (python3-gz-transport13
and python3-gz-msgs10, installed with Gazebo Harmonic).

For each frame f:  set_pose_vector(all poses at f) -> step the world once ->
wait for the rgb image and both box messages stamped with the expected sim time
-> save frames/<f>.png and a line of gz_boxes.jsonl.

UNVERIFIED here: written against the Harmonic APIs but not run in this repo's
CI. Follow docs/gazebo_verification.md the first time.
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_sim.frames import frame_path
from tracking_sim.scenario import Scenario
from tracking_sim.world_sdf import WORLD_NAME, frame_poses, write_world

try:
    from gz.msgs10.annotated_axis_aligned_2d_box_v_pb2 import AnnotatedAxisAligned2DBox_V
    from gz.msgs10.boolean_pb2 import Boolean
    from gz.msgs10.image_pb2 import Image
    from gz.msgs10.pose_v_pb2 import Pose_V
    from gz.msgs10.world_control_pb2 import WorldControl
    from gz.transport13 import Node
except ImportError as e:  # pragma: no cover
    sys.exit(f"gz Python bindings not found ({e}). Install python3-gz-transport13 python3-gz-msgs10.")

ap = argparse.ArgumentParser()
ap.add_argument("--flight", required=True)
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--max-frames", type=int, default=0)
ap.add_argument("--timeout", type=float, default=10.0, help="seconds to wait per frame")
ap.add_argument("--gui", action="store_true", help="also open the Gazebo GUI (debugging)")
args = ap.parse_args()

cfg = load_yaml(args.config)
d = Path(args.data) / args.flight
sc = Scenario.load(d / "scenario")
fps = cfg["clip"]["fps"]
step_ns = int(round(1e9 / fps))
world = write_world(sc, cfg, d / "world.sdf", step_s=1.0 / fps)
(d / "frames").mkdir(exist_ok=True)

cmd = ["gz", "sim", str(world)] + ([] if args.gui else ["-s", "--headless-rendering"])
server = subprocess.Popen(cmd, stdout=open(d / "gz_server.log", "w"), stderr=subprocess.STDOUT)
node = Node()

latest = {}
cond = threading.Condition()


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nsec


def make_cb(key):
    def cb(msg):
        with cond:
            latest[key] = msg
            cond.notify_all()
    return cb


node.subscribe(Image, "/observer/rgb", make_cb("rgb"))
node.subscribe(AnnotatedAxisAligned2DBox_V, "/observer/boxes_visible", make_cb("vis"))
node.subscribe(AnnotatedAxisAligned2DBox_V, "/observer/boxes_full", make_cb("full"))


def call(service, req, req_t, rep_t, timeout_ms=5000):
    ok, rep = node.request(service, req, req_t, rep_t, timeout_ms)
    if not ok:
        raise RuntimeError(f"service {service} failed or timed out")
    return rep


def wait_for(key, min_stamp, timeout):
    deadline = time.time() + timeout
    with cond:
        while True:
            m = latest.get(key)
            if m is not None and stamp_ns(m) >= min_stamp:
                return m
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(f"no {key} message stamped >= {min_stamp} ns")
            cond.wait(left)


def boxes(msg):
    return [{"label": int(b.label), "box": [b.box.min_corner.x, b.box.min_corner.y,
                                            b.box.max_corner.x, b.box.max_corner.y]}
            for b in msg.annotated_box]


# wait for the world to come up
for _ in range(60):
    try:
        call(f"/world/{WORLD_NAME}/control", WorldControl(pause=True), WorldControl, Boolean, 1000)
        break
    except RuntimeError:
        time.sleep(1)
else:
    server.terminate()
    sys.exit("Gazebo world did not start; see gz_server.log")

n = sc.n_frames if args.max_frames <= 0 else min(args.max_frames, sc.n_frames)
log = open(d / "gz_boxes.jsonl", "w")
t_start, sim_ns = time.time(), None
try:
    for f in range(n):
        pv = Pose_V()
        for name, pos, q in frame_poses(sc, f):
            p = pv.pose.add()
            p.name = name
            p.position.x, p.position.y, p.position.z = map(float, pos)
            p.orientation.w, p.orientation.x, p.orientation.y, p.orientation.z = map(float, q)
        call(f"/world/{WORLD_NAME}/set_pose_vector", pv, Pose_V, Boolean)
        call(f"/world/{WORLD_NAME}/control", WorldControl(pause=True, multi_step=1), WorldControl, Boolean)
        # The first image after the step carries the stamp we must wait for.
        rgb = wait_for("rgb", (sim_ns or 0) + 1, args.timeout)
        sim_ns = stamp_ns(rgb)
        vis = wait_for("vis", sim_ns, args.timeout)
        full = wait_for("full", sim_ns, args.timeout)
        img = np.frombuffer(rgb.data, np.uint8).reshape(rgb.height, rgb.width, 3)
        cv2.imwrite(str(frame_path(d, f + 1)), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        log.write(json.dumps({"frame": f + 1, "sim_ns": sim_ns, "boxes": boxes(vis),
                              "full_boxes": boxes(full)}) + "\n")
        if f % 50 == 0:
            print(f"frame {f + 1}/{n}  sim {sim_ns / 1e9:.2f}s  wall {time.time() - t_start:.0f}s", flush=True)
finally:
    log.close()
    server.terminate()
    server.wait(timeout=20)

(d / "render.json").write_text(json.dumps({
    "renderer": "gazebo", "frames": n, "step_ns": step_ns, "wall_s": round(time.time() - t_start, 1),
    "gz_version": subprocess.run(["gz", "sim", "--versions"], capture_output=True, text=True).stdout.strip()}))
print(f"done: {n} frames in {time.time() - t_start:.0f}s -> {d}")
