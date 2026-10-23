"""Week 2 label audit: overlays, contact sheet, event yield and an audit checklist.

    python scripts/audit_labels.py --flights $(ls data | grep dev_) --out outputs/audit

For each flight it picks: the frame before each scheduled event, the middle of
the gap, the first frame after reappearance, the busiest crossing frame, and a
few random frames. Writes:
  outputs/audit/<flight>_f<frame>.png    full-size overlays
  outputs/audit/contact_sheet_*.png      one sheet per 12 tiles
  outputs/audit/audit_log.csv            checklist to fill in by hand (Y/N + notes)
  outputs/audit/event_yield.csv          primary events per flight and exclusions
  outputs/audit/visibility_check.csv     toy-render mask vs analytic visibility
  outputs/audit/gz_box_check.csv         Gazebo vs analytic boxes (when gz_boxes.jsonl exists)
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_evaluation.audit import contact_sheet, draw_truth
from tracking_evaluation.events import extract_events
from tracking_sim.frames import frame_path
from tracking_sim.geometry import box_iou
from tracking_sim.scenario import Scenario
from tracking_sim.truth import read_truth, truth_arrays

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--flights", nargs="+", required=True)
ap.add_argument("--protocol", default=ROOT / "configs/event_protocol.yaml")
ap.add_argument("--out", default=ROOT / "outputs/audit")
ap.add_argument("--random", type=int, default=2)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()

proto = load_yaml(args.protocol)
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(args.seed)
sheet_tiles, log_rows, yield_rows, vis_rows, gz_rows = [], [], [], [], []

for fid in args.flights:
    d = Path(args.data) / fid
    header, truth = read_truth(d / "truth.jsonl")
    sc = Scenario.load(d / "scenario")
    fps = round(1 / float(np.median(np.diff(sc.times))))
    arrays = truth_arrays(truth)
    events = extract_events(arrays, proto, fps, fid, sc.schedule)
    reasons = Counter(e["exclusion_reason"] or "eligible" for e in events)
    yield_rows.append({"flight_id": fid, **{k: header["clip"][k] for k in
                       ("camera_motion", "occlusion_s", "target_group")},
                       "eligible": reasons.pop("eligible", 0),
                       "eligible_scheduled": sum(e["eligible"] and e["scheduled"] for e in events),
                       **{f"excl_{k}": v for k, v in reasons.items()}})

    picks = {}
    for s in sc.schedule:
        if s.get("status") != "scheduled":
            continue
        f0, f1 = int(s["t_start"] * fps), int(s["t_end"] * fps)
        picks[max(1, f0 - 2)] = f"before slot {s['slot']} (target {s['target_id']})"
        picks[(f0 + f1) // 2 + 1] = f"middle slot {s['slot']}: target {s['target_id']} hidden?"
        picks[min(len(truth), f1 + 4)] = f"after slot {s['slot']}: target {s['target_id']} back?"
    crowd = int(np.argmax([sum(o["vis"] > 0 and o["vis"] < 0.9 for o in fr["objects"]) for fr in truth]))
    picks.setdefault(crowd + 1, "most mutual occlusion")
    for f in rng.choice(len(truth), args.random, replace=False):
        picks.setdefault(int(f) + 1, "random")

    gz = {}
    if (d / "gz_boxes.jsonl").exists():
        for line in (d / "gz_boxes.jsonl").read_text().splitlines():
            r = json.loads(line)
            gz[r["frame"]] = r["boxes"]

    for f, why in sorted(picks.items()):
        p = frame_path(d, f)
        if not p.exists():
            continue
        img = cv2.imread(str(p))
        ov = draw_truth(img, truth[f - 1], proto["observability"]["vis_threshold"], gz.get(f),
                        header=f"{fid} | {why}")
        name = f"{fid}_f{f:06d}.png"
        cv2.imwrite(str(out / name), ov)
        sheet_tiles.append(ov)
        log_rows.append({"flight_id": fid, "frame": f, "image": name, "check": why,
                         "boxes_tight_Y/N": "", "ids_persist_Y/N": "", "hidden_correct_Y/N": "", "notes": ""})

    # independent visibility check against the toy-render mask
    render = json.loads((d / "render.json").read_text()) if (d / "render.json").exists() else {}
    if render.get("renderer") == "toy":
        from tracking_sim.render_toy import mask_visibility, render_frame
        for f in sorted(picks)[:6]:
            _, mask = render_frame(sc, f - 1)
            mv = mask_visibility(mask, sc, f - 1)
            for o in truth[f - 1]["objects"]:
                if o["id"] in mv and o["in_fov"]:
                    vis_rows.append({"flight_id": fid, "frame": f, "id": o["id"], "analytic_vis": o["vis"],
                                     "mask_vis": round(mv[o["id"]], 4),
                                     "abs_diff": round(abs(o["vis"] - mv[o["id"]]), 4)})
    for f, boxes in gz.items():
        tb = {o["id"]: o["visible_box"] for o in truth[f - 1]["objects"] if o["visible_box"]}
        for b in boxes:
            if b["label"] in tb:
                gz_rows.append({"flight_id": fid, "frame": f, "id": b["label"],
                                "iou": round(box_iou(tb[b["label"]], b["box"]), 4)})


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, keys, restval=0)
        w.writeheader()
        w.writerows(rows)


for i in range(0, len(sheet_tiles), 12):
    cv2.imwrite(str(out / f"contact_sheet_{i // 12 + 1:02d}.png"), contact_sheet(sheet_tiles[i:i + 12]))
write_csv(out / "audit_log.csv", log_rows)
write_csv(out / "event_yield.csv", yield_rows)
write_csv(out / "visibility_check.csv", vis_rows)
write_csv(out / "gz_box_check.csv", gz_rows)

tot = sum(r["eligible"] for r in yield_rows)
print(f"{len(log_rows)} audit frames, {len(sheet_tiles) // 12 + 1} contact sheets -> {out}")
print(f"eligible primary events: {tot} across {len(yield_rows)} flights")
if vis_rows:
    diffs = np.array([r["abs_diff"] for r in vis_rows])
    print(f"toy-mask vs analytic visibility: median |diff| {np.median(diffs):.3f}, "
          f"max {diffs.max():.3f}, >0.1 in {np.mean(diffs > 0.1):.1%} of {len(diffs)} checks")
if gz_rows:
    ious = np.array([r["iou"] for r in gz_rows])
    print(f"Gazebo vs analytic visible boxes: median IoU {np.median(ious):.3f}, <0.8 in {np.mean(ious < 0.8):.1%}")
