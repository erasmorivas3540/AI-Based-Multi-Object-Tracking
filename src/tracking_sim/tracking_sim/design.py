"""Experimental design: which flights exist, their seeds, layouts and splits.

Rules enforced here (plan section 15):
  * Whole flights are assigned to one partition; both blur variants of a flight
    share that partition.
  * Dev and test use disjoint layouts and independent seeds.
  * The test manifest is hashed ("sealed"); later steps refuse to run if the
    hash changes, and detector/recovery training refuses test flights.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

PARTS = {"dev": 0, "test": 1}


def config_checksum(cfg_text: str) -> str:
    return hashlib.sha256(cfg_text.encode()).hexdigest()[:16]


def _seed(master: int, part: str, cell: tuple, k: int) -> int:
    ss = np.random.SeedSequence([master, PARTS[part], *cell, k])
    return int(ss.generate_state(1)[0])


def make_design(cfg: dict, cfg_checksum: str) -> dict:
    fac = cfg["factors"]
    d = cfg["design"]
    motions = list(fac["camera_motion"])
    occs = list(fac["occlusion_s"])
    groups = list(fac["target_group"])
    blurs = list(fac["blur"].items())
    flights, clips = [], []
    split_rng = np.random.default_rng(d["master_seed"])
    for part, n_seeds in (("dev", d["dev_seeds"]), ("test", d["test_seeds"])):
        for ci, (mi, oi, gi) in enumerate(itertools.product(range(len(motions)), range(len(occs)),
                                                            range(len(groups)))):
            val_k = set(split_rng.choice(n_seeds, d["val_seeds_per_cell"], replace=False).tolist()) \
                if part == "dev" else set()
            for k in range(n_seeds):
                split = "test" if part == "test" else ("val" if k in val_k else "train")
                layouts = d[f"{split}_layouts"]
                fid = f"{part}_{groups[gi]}_{motions[mi]}_occ{int(round(occs[oi] * 10)):02d}_s{k}"
                flights.append({
                    "flight_id": fid, "partition": part, "split": split,
                    "seed": _seed(d["master_seed"], part, (mi, oi, gi), k),
                    "camera_motion": motions[mi], "occlusion_s": occs[oi],
                    "target_group": groups[gi], "layout": layouts[(k + ci) % len(layouts)],
                })
                for bname, blen in blurs:
                    clips.append({"clip_id": f"{fid}_blur{bname}", "flight_id": fid, "split": split,
                                  "blur": bname, "blur_kernel_px": blen})
    return {"design_version": cfg["version"], "config_checksum": cfg_checksum,
            "flights": flights, "clips": clips}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def test_subset(design: dict) -> dict:
    return {"config_checksum": design["config_checksum"],
            "flights": [f for f in design["flights"] if f["split"] == "test"],
            "clips": [c for c in design["clips"] if c["split"] == "test"]}


def seal_hash(design: dict) -> str:
    return hashlib.sha256(canonical_json(test_subset(design)).encode()).hexdigest()


def check_design(design: dict, sealed_hash: str | None = None) -> list[str]:
    """Return a list of problems (empty = OK)."""
    problems = []
    fl = design["flights"]
    ids = [f["flight_id"] for f in fl]
    if len(ids) != len(set(ids)):
        problems.append("duplicate flight_id")
    seeds = [f["seed"] for f in fl]
    if len(seeds) != len(set(seeds)):
        problems.append("duplicate seed across flights")
    split_of = {f["flight_id"]: f["split"] for f in fl}
    for c in design["clips"]:
        if split_of.get(c["flight_id"]) != c["split"]:
            problems.append(f"clip {c['clip_id']} split differs from its flight")
    by_split = {s: {f["layout"] for f in fl if f["split"] == s} for s in ("train", "val", "test")}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        shared = by_split[a] & by_split[b]
        if shared:
            problems.append(f"layouts shared between {a} and {b}: {sorted(shared)}")
    for f in fl:
        if (f["partition"] == "test") != (f["split"] == "test"):
            problems.append(f"{f['flight_id']}: partition/split mismatch")
    if sealed_hash is not None and seal_hash(design) != sealed_hash:
        problems.append("TEST MANIFEST CHANGED since it was sealed")
    return problems


def load_design(manifest_dir: Path) -> dict:
    return json.loads((Path(manifest_dir) / "design.json").read_text())


def flights_for(design: dict, splits: set[str]) -> list[dict]:
    return [f for f in design["flights"] if f["split"] in splits]


def assert_not_test(flights: list[dict], context: str):
    bad = [f["flight_id"] for f in flights if f["split"] == "test" or f["partition"] == "test"]
    if bad:
        raise PermissionError(f"{context}: refusing to use sealed test flights {bad[:3]}...")
