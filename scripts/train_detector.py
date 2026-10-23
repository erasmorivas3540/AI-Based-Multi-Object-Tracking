"""Fine-tune the detector on an exported dataset with the frozen config.

    python scripts/train_detector.py --dataset outputs/yolo_v1 --name det_v1
    python scripts/train_detector.py --dataset outputs/yolo_v1 --name det_v1_960 --imgsz 960   # search run

Every run writes runs/detector/<name>/run_record.json (git commit, config and
dataset checksums, weights hash, versions, hardware). Keep ALL search runs and
report them; pick the final checkpoint on validation only.
"""
import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from _runinfo import sha256_file, write_record

ap = argparse.ArgumentParser()
ap.add_argument("--dataset", required=True)
ap.add_argument("--config", default=ROOT / "configs/detector.yaml")
ap.add_argument("--name", required=True)
ap.add_argument("--imgsz", type=int)
ap.add_argument("--init-weights")
ap.add_argument("--epochs", type=int)
ap.add_argument("--batch", type=int)
ap.add_argument("--device", default=None, help="e.g. 0 or cpu")
ap.add_argument("--project", default=ROOT / "runs/detector")
args = ap.parse_args()

from ultralytics import YOLO  # noqa: E402

cfg = load_yaml(args.config)
t = cfg["train"]
params = dict(imgsz=args.imgsz or t["imgsz"], epochs=args.epochs or t["epochs"], batch=args.batch or t["batch"],
              patience=t["patience"], seed=t["seed"], deterministic=t["deterministic"], workers=t["workers"],
              **t["augment"])
init = args.init_weights or t["init_weights"]
dataset = Path(args.dataset)
export_manifest = json.loads((dataset / "export_manifest.json").read_text())

model = YOLO(init)
model.train(data=str(dataset / "dataset.yaml"), project=str(args.project), name=args.name, exist_ok=False,
            device=args.device, plots=False, val=True, **params)

run_dir = Path(args.project) / args.name
best = run_dir / "weights" / "best.pt"
write_record(run_dir / "run_record.json", task="detector_train", init_weights=init, params=params,
             config_sha=sha256_file(args.config), dataset=str(dataset),
             dataset_file_list_sha256=export_manifest["file_list_sha256"],
             sealed_test_hash=export_manifest["sealed_test_hash"],
             best_weights=str(best), best_weights_sha=sha256_file(best) if best.exists() else None)
print(f"done -> {run_dir}")
