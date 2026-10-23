"""Run the frozen detector over whole clips and cache its outputs (plan section 17).

    python scripts/cache_detections.py --weights runs/detector/det_v1/weights/best.pt --splits train val
    python scripts/cache_detections.py --weights ... --splits test      # only after the freeze

One file per clip (flight x blur): outputs/detections/<weights_sha>/<clip_id>.npz
  frame (1-based), x1, y1, x2, y2 (ORIGINAL image pixels), score, cls, kind (0 raw, 1 final)
plus <clip_id>.json with the settings, weights hash, image size and per-frame
timestamps. Trackers read the cache; cached runtimes are NOT live pipeline runtimes.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from _runinfo import run_record, sha256_file
from tracking_detector.boxes import classwise_nms
from tracking_detector.cache_io import save_cache
from tracking_sim.design import check_design, load_design
from tracking_sim.frames import blur_angles, load_frame
from tracking_sim.scenario import Scenario

ap = argparse.ArgumentParser()
ap.add_argument("--weights", required=True)
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--config", default=ROOT / "configs/detector.yaml")
ap.add_argument("--scenario-config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--splits", nargs="+", default=["train", "val"])
ap.add_argument("--flights", nargs="*")
ap.add_argument("--imgsz", type=int)
ap.add_argument("--device", default=None)
ap.add_argument("--out", default=ROOT / "outputs/detections")
ap.add_argument("--every", type=int, default=1, help="cache every Nth frame (testing only)")
args = ap.parse_args()

from ultralytics import YOLO  # noqa: E402

cfg = load_yaml(args.config)
C = cfg["cache"]
blur_px = load_yaml(args.scenario_config)["factors"]["blur"]
design = load_design(args.manifests)
sealed = (Path(args.manifests) / "test_manifest.sha256").read_text().split()[0]
problems = check_design(design, sealed)
if problems:
    raise SystemExit("design check failed:\n" + "\n".join(problems))
w_sha = sha256_file(args.weights)
model = YOLO(args.weights)
names = model.names
classes = cfg["classes"]
if [names[i] for i in sorted(names)] != classes:
    raise SystemExit(f"checkpoint classes {names} != project classes {classes}")
imgsz = args.imgsz or cfg["train"]["imgsz"]
out = Path(args.out) / w_sha
out.mkdir(parents=True, exist_ok=True)

clips = [c for c in design["clips"] if c["split"] in set(args.splits)]
if args.flights:
    clips = [c for c in clips if c["flight_id"] in set(args.flights)]
for clip in clips:
    d = Path(args.data) / clip["flight_id"]
    if not (d / "frames").exists():
        continue
    sc = Scenario.load(d / "scenario")
    angles = blur_angles(sc)
    rows, t0 = [], time.time()
    frames = sorted(int(p.stem) for p in (d / "frames").glob("*.png"))[::args.every]
    for f in frames:
        img = load_frame(d, f, blur_px[clip["blur"]], angles)
        r = model.predict(img, imgsz=imgsz, conf=C["raw_conf"], iou=C["raw_iou"], max_det=C["raw_max_det"],
                          device=args.device, verbose=False)[0]
        assert tuple(r.orig_shape) == img.shape[:2], "detector returned boxes for a different image size"
        b = r.boxes.xyxy.cpu().numpy()
        s = r.boxes.conf.cpu().numpy()
        c = r.boxes.cls.cpu().numpy().astype(int)
        for i in range(len(b)):
            rows.append((f, *b[i], s[i], c[i], 0))
        ok = s >= C["final_conf"]
        idx = np.flatnonzero(ok)
        for i in idx[classwise_nms(b[ok], s[ok], c[ok], C["final_iou"])] if len(idx) else []:
            rows.append((f, *b[i], s[i], c[i], 1))
    arr = np.array(rows, float).reshape(-1, 8)   # frame, x1, y1, x2, y2, score, cls, kind
    save_cache(out / f"{clip['clip_id']}.npz", arr)
    (out / f"{clip['clip_id']}.json").write_text(json.dumps(run_record(
        task="detection_cache", clip=clip, weights=str(args.weights), weights_sha=w_sha, imgsz=imgsz,
        cache_settings=C, classes=classes, image_size=[sc.cam.width, sc.cam.height],
        frames=frames, timestamps_s=[round(float(sc.times[f - 1]), 4) for f in frames],
        coordinates="original image pixels, xyxy", wall_s=round(time.time() - t0, 1)), indent=1, default=str))
    print(f"{clip['clip_id']}: {int((arr[:, 7] == 1).sum())} final / {len(arr)} total boxes "
          f"({time.time() - t0:.0f}s)")

