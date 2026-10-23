"""Create the flight/clip design and seal the test manifest.

    python scripts/make_design.py                      # writes manifests/design.json + seal
    python scripts/make_design.py --check              # verify only

Run once when the scenario config is frozen (end of Week 2). Re-running with a
changed config refuses to overwrite a sealed test manifest unless --reseal is
given, and resealing must be logged in docs/decisions_log.md.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from tracking_sim.design import canonical_json, check_design, config_checksum, make_design, seal_hash

ap = argparse.ArgumentParser()
ap.add_argument("--config", default=ROOT / "configs/scenario_design.yaml")
ap.add_argument("--out", default=ROOT / "manifests")
ap.add_argument("--check", action="store_true")
ap.add_argument("--reseal", action="store_true")
args = ap.parse_args()

out = Path(args.out)
seal_file = out / "test_manifest.sha256"
cfg_text = Path(args.config).read_text()
cfg = load_yaml(args.config)
design = make_design(cfg, config_checksum(cfg_text))
sealed = seal_file.read_text().split()[0] if seal_file.exists() else None

if args.check:
    existing = json.loads((out / "design.json").read_text())
    problems = check_design(existing, sealed)
    if canonical_json(existing) != canonical_json(design):
        problems.append("design.json does not match what the current config generates")
    print("\n".join(problems) if problems else "design OK; test manifest matches its seal")
    raise SystemExit(1 if problems else 0)

new_hash = seal_hash(design)
if sealed and sealed != new_hash and not args.reseal:
    raise SystemExit("Test manifest is sealed and would change. Use --reseal and log why "
                     "in docs/decisions_log.md.")

problems = check_design(design)
if problems:
    raise SystemExit("design problems:\n" + "\n".join(problems))
out.mkdir(parents=True, exist_ok=True)
(out / "design.json").write_text(json.dumps(design, indent=1))
(out / "test_manifest.json").write_text(json.dumps(
    {k: v for k, v in design.items() if k in ("config_checksum",)} |
    {"flights": [f for f in design["flights"] if f["split"] == "test"]}, indent=1))
seal_file.write_text(f"{new_hash}  test subset of design.json (config {design['config_checksum']})\n")

c = Counter(f["split"] for f in design["flights"])
cc = Counter(cl["split"] for cl in design["clips"])
print(f"flights: {dict(c)}   clips: {dict(cc)}")
print(f"test manifest sealed: {new_hash[:16]}...  -> {seal_file}")
