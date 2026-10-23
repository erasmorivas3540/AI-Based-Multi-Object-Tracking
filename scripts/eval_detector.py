"""Detector precision/recall by class, size, visibility and blur (plan section 17).

    python scripts/eval_detector.py --weights runs/detector/det_v1/weights/best.pt --splits val
    python scripts/eval_detector.py --cache outputs/detections/<sha> --splits val       # from a cache

Writes outputs/detector_eval/<name>/{summary.md, by_group.csv, run_record.json}.
Truth targets: visible >= protocol vis threshold, size >= min, centre in view.
Partly visible objects are "ignore": a detection on them is neither a TP nor an FP.
Also reports box bias (centre offset, scale) of matched detections, which exposes
coordinate/resize bugs, and localisation failures separately from misses.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from _runinfo import sha256_file, write_record
from tracking_detector.boxes import greedy_match
from tracking_detector.cache_io import load_cache
from tracking_detector.labels import classify_object
from tracking_sim.design import check_design, load_design
from tracking_sim.frames import blur_angles, load_frame
from tracking_sim.geometry import iou_matrix
from tracking_sim.scenario import Scenario
from tracking_sim.truth import read_truth

ap = argparse.ArgumentParser()
src = ap.add_mutually_exclusive_group(required=True)
src.add_argument("--weights")
src.add_argument("--cache", help="folder of cached detections")
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--config", default=ROOT / "configs/detector.yaml")
ap.add_argument("--protocol", default=ROOT / "configs/event_protocol.yaml")
ap.add_argument("--scenario-config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--splits", nargs="+", default=["val"])
ap.add_argument("--flights", nargs="*")
ap.add_argument("--stride", type=int, default=4)
ap.add_argument("--imgsz", type=int)
ap.add_argument("--device", default=None)
ap.add_argument("--name", default=None)
args = ap.parse_args()

cfg = load_yaml(args.config)
E = cfg["evaluation"]
proto = load_yaml(args.protocol)
O = proto["observability"]
blur_px = load_yaml(args.scenario_config)["factors"]["blur"]
classes = cfg["classes"]
design = load_design(args.manifests)
sealed = (Path(args.manifests) / "test_manifest.sha256").read_text().split()[0]
if check_design(design, sealed):
    raise SystemExit("design check failed")
if "test" in args.splits:
    print("WARNING: evaluating on the sealed test split. Only do this in the final, frozen run.")

model = None
if args.weights:
    from ultralytics import YOLO
    model = YOLO(args.weights)
    imgsz = args.imgsz or cfg["train"]["imgsz"]

bins = E["size_bins_px"]
size_label = [f"{bins[i]}-{bins[i + 1] if bins[i + 1] < 1e4 else 'inf'}px" for i in range(len(bins) - 1)]
stats = defaultdict(lambda: defaultdict(float))   # group -> counters
bias = defaultdict(list)                          # class -> [(dx_rel, dy_rel, log_w, log_h)]


def add(keys, field, v=1):
    for k in keys:
        stats[k][field] += v


clips = [c for c in design["clips"] if c["split"] in set(args.splits)]
if args.flights:
    clips = [c for c in clips if c["flight_id"] in set(args.flights)]
n_frames = 0
for clip in clips:
    d = Path(args.data) / clip["flight_id"]
    if not (d / "frames").exists():
        continue
    _, truth = read_truth(d / "truth.jsonl")
    cache = load_cache(Path(args.cache) / f"{clip['clip_id']}.npz") if args.cache else None
    sc = Scenario.load(d / "scenario")
    angles = blur_angles(sc)
    fl = next(f for f in design["flights"] if f["flight_id"] == clip["flight_id"])
    for f in range(1, len(truth) + 1, args.stride):
        if not (d / "frames" / f"{f:06d}.png").exists():
            continue
        n_frames += 1
        if cache is not None:
            dets = [x for x in cache.get(f, []) if x[4] >= E["conf"]]
        else:
            img = load_frame(d, f, blur_px[clip["blur"]], angles)
            r = model.predict(img, imgsz=imgsz, conf=E["conf"], device=args.device, verbose=False)[0]
            dets = [(*b, s, int(c)) for b, s, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(),
                                                        r.boxes.cls.cpu().numpy())]
        objs = truth[f - 1]["objects"]
        for ci, cname in enumerate(classes):
            tg = [o for o in objs if o["cls"] == cname and classify_object(o, O["vis_threshold"], O["min_box_side_px"]) == "target"]
            ig = [o for o in objs if o["cls"] == cname and classify_object(o, O["vis_threshold"], O["min_box_side_px"]) == "ignore"]
            dd = [x for x in dets if x[5] == ci]
            db = np.array([x[:4] for x in dd]).reshape(-1, 4)
            ds = np.array([x[4] for x in dd])
            gb = np.array([o["visible_box"] for o in tg]).reshape(-1, 4)
            d2g, best = greedy_match(db, ds, gb, E["match_iou"])
            # unmatched detections overlapping an ignored object are not false positives
            unmatched = np.flatnonzero(d2g < 0)
            if len(unmatched) and ig:
                ov = iou_matrix(db[unmatched], np.array([o["visible_box"] for o in ig]))
                fp = int((ov.max(axis=1) < E["match_iou"]).sum())
            else:
                fp = len(unmatched)
            groups_all = ["all", f"class={cname}", f"blur={clip['blur']}",
                          f"motion={fl['camera_motion']}", f"class={cname}|blur={clip['blur']}"]
            add(groups_all, "fp", fp)
            add(groups_all, "det", len(dd))
            for j, o in enumerate(tg):
                b = o["visible_box"]
                sz = float(np.sqrt((b[2] - b[0]) * (b[3] - b[1])))
                sbin = size_label[int(np.searchsorted(bins, sz, side="right") - 1)]
                vbin = "vis=1.0" if o["vis"] >= 0.999 else "vis<1.0"
                keys = groups_all + [f"class={cname}|size={sbin}", f"size={sbin}", f"class={cname}|{vbin}"]
                add(keys, "gt")
                hit = j in d2g
                add(keys, "tp", int(hit))
                if not hit and best[j] >= E["loc_failure_iou"]:
                    add(keys, "loc_fail")
                if hit:
                    i = int(np.flatnonzero(d2g == j)[0])
                    w, h = b[2] - b[0], b[3] - b[1]
                    bias[cname].append(((db[i, 0] + db[i, 2] - b[0] - b[2]) / 2 / w,
                                        (db[i, 1] + db[i, 3] - b[1] - b[3]) / 2 / h,
                                        np.log((db[i, 2] - db[i, 0]) / w), np.log((db[i, 3] - db[i, 1]) / h)))

rows = []
for g in sorted(stats, key=lambda k: (k != "all", k)):
    s = stats[g]
    gt, tp = s["gt"], s["tp"]
    row = {"group": g, "gt": int(gt), "tp": int(tp), "recall": round(tp / gt, 4) if gt else ""}
    if "size=" not in g and "vis" not in g:
        row.update({"fp": int(s["fp"]), "precision": round(tp / (tp + s["fp"]), 4) if tp + s["fp"] else ""})
    row["loc_fail"] = int(s["loc_fail"])
    row["miss_no_box"] = int(gt - tp - s["loc_fail"])
    rows.append(row)

name = args.name or (Path(args.weights).parents[1].name if args.weights else Path(args.cache).name)
out = ROOT / "outputs/detector_eval" / name
out.mkdir(parents=True, exist_ok=True)
with open(out / "by_group.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, ["group", "gt", "tp", "recall", "fp", "precision", "loc_fail", "miss_no_box"])
    w.writeheader()
    w.writerows(rows)
bias_summary = {c: {k: round(float(np.median(np.array(v)[:, i])), 4) for i, k in
                    enumerate(["centre_dx_rel", "centre_dy_rel", "log_w_ratio", "log_h_ratio"])}
                for c, v in bias.items() if v}
md = [f"# Detector evaluation: {name}", "", f"Splits: {args.splits}; frames: {n_frames}; conf >= {E['conf']}; "
      f"match IoU {E['match_iou']}", "", "| group | GT | recall | precision | loc. fail | no box |", "|---|---|---|---|---|---|"]
md += [f"| {r['group']} | {r['gt']} | {r['recall']} | {r.get('precision', '')} | {r['loc_fail']} | {r['miss_no_box']} |" for r in rows]
md += ["", "Median box bias of matched detections (should be ~0; a consistent offset suggests a",
       "coordinate or resize bug):", "", "```", json.dumps(bias_summary, indent=1), "```"]
(out / "summary.md").write_text("\n".join(md) + "\n")
write_record(out / "run_record.json", task="detector_eval", splits=args.splits, weights=args.weights,
             weights_sha=sha256_file(args.weights) if args.weights else None, cache=args.cache,
             config_sha=sha256_file(args.config), protocol_sha=sha256_file(args.protocol), frames=n_frames)
print("\n".join(md[:12 + len(rows)]))
