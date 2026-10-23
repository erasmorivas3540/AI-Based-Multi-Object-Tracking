"""Export train/val flights to an Ultralytics YOLO dataset. Refuses test flights.

    python scripts/export_yolo.py --out outputs/yolo_v1
    python scripts/export_yolo.py --out outputs/yolo_pilot --flights dev_uav_low_occ10_s0 ...

Both blur variants of a flight go to the flight's split. Writes dataset.yaml,
images/{train,val}, labels/{train,val} and export_manifest.json (with a checksum
of the exact file list, recorded by train_detector.py).
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_detector.labels import classify_object, yolo_line
from tracking_sim.design import assert_not_test, check_design, load_design
from tracking_sim.frames import blur_angles, frame_path, load_frame
from tracking_sim.scenario import Scenario
from tracking_sim.truth import read_truth

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--config", default=ROOT / "configs/detector.yaml")
ap.add_argument("--scenario-config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--out", required=True)
ap.add_argument("--flights", nargs="*", help="subset of train/val flight ids (default: all built)")
args = ap.parse_args()

cfg = load_yaml(args.config)
scfg = load_yaml(args.scenario_config)
design = load_design(args.manifests)
sealed = (Path(args.manifests) / "test_manifest.sha256").read_text().split()[0]
problems = check_design(design, sealed)
if problems:
    raise SystemExit("design check failed:\n" + "\n".join(problems))

flights = [f for f in design["flights"] if f["split"] in ("train", "val")]
if args.flights:
    want = set(args.flights)
    flights = [f for f in design["flights"] if f["flight_id"] in want]
assert_not_test(flights, "YOLO export")
flights = [f for f in flights if (Path(args.data) / f["flight_id"] / "truth.jsonl").exists()]

classes = cfg["classes"]
blur_px = scfg["factors"]["blur"]
L = cfg["labels"]
out = Path(args.out)
counts, files = Counter(), []
for fl in flights:
    d = Path(args.data) / fl["flight_id"]
    _, truth = read_truth(d / "truth.jsonl")
    sc = Scenario.load(d / "scenario")
    angles = blur_angles(sc)
    split = fl["split"]
    for f in range(1, len(truth) + 1, L["frame_stride"]):
        if not frame_path(d, f).exists():
            continue
        lines = []
        for o in truth[f - 1]["objects"]:
            if classify_object(o, L["min_vis"], L["min_box_side_px"], need_in_fov=False) == "target":
                lines.append(yolo_line(o, classes.index(o["cls"]), sc.cam.width, sc.cam.height))
                counts[(split, o["cls"])] += 1
        for b in L["blur_variants"]:
            stem = f"{fl['flight_id']}_blur{b}_{f:06d}"
            img_p = out / "images" / split / f"{stem}.png"
            img_p.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(img_p), load_frame(d, f, blur_px[b], angles))
            lab_p = out / "labels" / split / f"{stem}.txt"
            lab_p.parent.mkdir(parents=True, exist_ok=True)
            lab_p.write_text("\n".join(lines) + ("\n" if lines else ""))
            files.append(f"{split}/{stem}")
            counts[(split, "images")] += 1

(out / "dataset.yaml").write_text(
    f"path: {out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n" +
    "".join(f"  {i}: {c}\n" for i, c in enumerate(classes)))
listing = "\n".join(sorted(files))
manifest = {"flights": [f["flight_id"] for f in flights], "splits": {f["flight_id"]: f["split"] for f in flights},
            "classes": classes, "labels": L, "sealed_test_hash": sealed,
            "file_list_sha256": hashlib.sha256(listing.encode()).hexdigest(),
            "counts": {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())}}
(out / "export_manifest.json").write_text(json.dumps(manifest, indent=1))
print(json.dumps(manifest["counts"], indent=1))
