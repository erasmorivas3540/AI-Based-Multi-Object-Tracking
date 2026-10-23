"""Truth-derived reference trackers for checking the evaluation pipeline.

    python scripts/reference_trackers.py --splits val

  oracle_keep    publishes every observable target with its true id: every
                 eligible event is recovered (recall 1, precision 1, IDSW 0).
  oracle_newid   same boxes, but a target gets a NEW id after every disappearance:
                 recall 0, no recovery actions, one identity switch per return.

These are known-answer checks on realistic pilot data, not baselines. They read
ground truth, so they must never appear in a results table.
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_detector.labels import classify_object
from tracking_evaluation.mot_io import write_tracks
from tracking_sim.design import load_design
from tracking_sim.truth import read_truth

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--protocol", default=ROOT / "configs/event_protocol.yaml")
ap.add_argument("--splits", nargs="+", default=["train", "val"])
ap.add_argument("--out", default=ROOT / "outputs/tracks")
args = ap.parse_args()

O = load_yaml(args.protocol)["observability"]
design = load_design(args.manifests)
n = 0
for clip in design["clips"]:
    if clip["split"] not in args.splits or clip["blur"] != "none":
        continue
    tp = Path(args.data) / clip["flight_id"] / "truth.jsonl"
    if not tp.exists():
        continue
    _, truth = read_truth(tp)
    keep, newid = [], []
    next_id, current, was_visible = 1000, {}, {}
    for fr in truth:
        for o in fr["objects"]:
            ok = classify_object(o, O["vis_threshold"], O["min_box_side_px"]) == "target"
            if ok:
                row = dict(zip(["x1", "y1", "x2", "y2"], o["visible_box"]), frame=fr["frame"], score=1.0,
                           status="observed")
                keep.append(row | {"id": o["id"]})
                if not was_visible.get(o["id"], False) and o["id"] in current:
                    next_id += 1
                    current[o["id"]] = next_id      # came back: give it a new identity
                current.setdefault(o["id"], o["id"])
                newid.append(row | {"id": current[o["id"]]})
            was_visible[o["id"]] = ok
    for name, rows in (("oracle_keep", keep), ("oracle_newid", newid)):
        write_tracks(Path(args.out) / name / f"{clip['clip_id']}.csv", rows)
    n += 1
print(f"wrote reference tracks for {n} clips -> {args.out}")
