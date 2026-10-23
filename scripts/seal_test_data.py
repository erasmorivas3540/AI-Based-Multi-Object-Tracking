"""Seal the generated TEST data (Week 3 gate), or verify it later.

    python scripts/seal_test_data.py            # after building + rendering every test flight
    python scripts/seal_test_data.py --verify   # before the final held-out run (Week 5)

Fingerprints each test flight: scenario + truth file hashes and a hash over the
sorted frame list with sizes (hashing every PNG is slow; add --deep to hash pixels).
Also checks that no test frame is byte-identical to a dev frame (sampled).
"""
import argparse
import hashlib
import json
from pathlib import Path

import _bootstrap  # noqa: F401
from _bootstrap import ROOT
from _runinfo import sha256_file
from tracking_sim.design import check_design, load_design

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--verify", action="store_true")
ap.add_argument("--deep", action="store_true")
args = ap.parse_args()

design = load_design(args.manifests)
sealed = (Path(args.manifests) / "test_manifest.sha256").read_text().split()[0]
problems = check_design(design, sealed)
if problems:
    raise SystemExit("\n".join(problems))


def fingerprint(fid):
    d = Path(args.data) / fid
    frames = sorted((d / "frames").glob("*.png"))
    listing = "\n".join(f"{p.name}:{p.stat().st_size}" + (f":{sha256_file(p)}" if args.deep else "") for p in frames)
    return {"scenario_json": sha256_file(d / "scenario.json"), "scenario_npz": sha256_file(d / "scenario.npz"),
            "truth": sha256_file(d / "truth.jsonl"), "n_frames": len(frames),
            "frames": hashlib.sha256(listing.encode()).hexdigest()[:16], "deep": args.deep}


test_ids = [f["flight_id"] for f in design["flights"] if f["split"] == "test"]
missing = [f for f in test_ids if not (Path(args.data) / f / "truth.jsonl").exists()]
if missing:
    raise SystemExit(f"{len(missing)} test flights not built, e.g. {missing[:3]}")
seal_path = Path(args.manifests) / "test_data_seal.json"
fps = {fid: fingerprint(fid) for fid in test_ids}

if args.verify:
    ref = json.loads(seal_path.read_text())
    bad = [fid for fid in test_ids if {k: v for k, v in fps[fid].items() if k != "deep"} !=
           {k: v for k, v in ref["flights"][fid].items() if k != "deep"}]
    print("test data matches its seal" if not bad else f"CHANGED test flights: {bad}")
    raise SystemExit(1 if bad else 0)

# duplicate-content check: sample frames from dev and test
dev_ids = [f["flight_id"] for f in design["flights"] if f["split"] != "test"]
seen = {}
for fid in dev_ids:
    for p in sorted((Path(args.data) / fid / "frames").glob("*.png"))[::50]:
        seen[sha256_file(p)] = fid
dups = [(fid, p.name, seen[h]) for fid in test_ids for p in sorted((Path(args.data) / fid / "frames").glob("*.png"))[::50]
        if (h := sha256_file(p)) in seen]
if dups:
    raise SystemExit(f"test frames identical to dev frames: {dups[:3]}")
seal_path.write_text(json.dumps({"design_test_hash": sealed, "flights": fps}, indent=1))
print(f"sealed {len(test_ids)} test flights -> {seal_path}")
