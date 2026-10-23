"""Build scenario + analytic truth for flights in the design, and optionally
render them with the toy renderer.

    python scripts/build_flights.py --splits train val          # scenarios + truth
    python scripts/build_flights.py --pilot                      # 1 flight per cell (dev only)
    python scripts/build_flights.py --pilot --render toy         # + toy frames for the offline chain

Gazebo frames are produced separately by scripts/gz_render_flight.py, which reads
the scenario written here. Test flights are built only with --splits test, which
is meant to run once, after the protocol is frozen (Week 3).
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_sim.design import load_design
from tracking_sim.frames import frame_path
from tracking_sim.scenario import build_scenario
from tracking_sim.truth import compute_truth, write_truth

ap = argparse.ArgumentParser()
ap.add_argument("--config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--splits", nargs="+", default=["train", "val"])
ap.add_argument("--pilot", action="store_true", help="one dev flight per factor cell")
ap.add_argument("--flights", nargs="*", help="explicit flight ids")
ap.add_argument("--render", choices=["none", "toy"], default="none")
ap.add_argument("--every", type=int, default=1, help="render every Nth frame (toy only)")
ap.add_argument("--overwrite", action="store_true")
args = ap.parse_args()

cfg = load_yaml(args.config)
design = load_design(args.manifests)
flights = [f for f in design["flights"] if f["split"] in set(args.splits)]
if args.pilot:
    seen, pilot = set(), []
    for f in flights:
        cell = (f["camera_motion"], f["occlusion_s"], f["target_group"])
        if f["partition"] == "dev" and cell not in seen:
            seen.add(cell)
            pilot.append(f)
    flights = pilot
if args.flights:
    flights = [f for f in design["flights"] if f["flight_id"] in set(args.flights)]
if "test" in args.splits and not args.flights:
    print("NOTE: building sealed test flights. Do this once, after the protocol freeze.")

for fl in flights:
    out = Path(args.data) / fl["flight_id"]
    if (out / "truth.jsonl").exists() and not args.overwrite and args.render == "none":
        print(f"skip {fl['flight_id']} (exists)")
        continue
    t0 = time.time()
    sc = build_scenario(cfg, fl)
    sc.save(out / "scenario")
    truth = compute_truth(sc)
    write_truth(truth, out / "truth.jsonl", fl)
    msg = f"{fl['flight_id']}: {sc.stats['n_targets']} targets, schedule " + \
          ", ".join(s["status"][:5] + (f"@{s['t_start']:.1f}s" if "t_start" in s else "") for s in sc.schedule)
    if args.render == "toy":
        from tracking_sim.render_toy import render_frame
        ground = tuple(int(c) for c in cfg["layouts"][fl["layout"]]["ground_rgb"][::-1])
        (out / "frames").mkdir(exist_ok=True)
        for f in range(0, sc.n_frames, args.every):
            img, _ = render_frame(sc, f, ground)
            cv2.imwrite(str(frame_path(out, f + 1)), img)
        (out / "render.json").write_text(json.dumps(
            {"renderer": "toy", "every": args.every, "note": "toy frames: pipeline testing only"}))
    print(f"{msg}  ({time.time() - t0:.1f}s)")
