"""Ground-truth export, tracker-output files and the TrackEval adapter."""
from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

import numpy as np

# TrackEval (commit 12c8791) uses aliases NumPy removed in 1.24.
for _name, _typ in (("float", float), ("int", int), ("bool", bool)):
    if _name not in np.__dict__:
        setattr(np, _name, _typ)

TRACK_FIELDS = ["frame", "id", "x1", "y1", "x2", "y2", "score", "status"]


def gt_rows(truth: list[dict], proto: dict) -> list[str]:
    """MOTChallenge gt rows: observable targets as class 1, partly visible as distractors."""
    o = proto["observability"]
    distractor = proto["benchmark_export"]["distractor_class"]
    rows = []
    for fr in truth:
        for ob in fr["objects"]:
            vb = ob["visible_box"]
            if not vb:
                continue
            w, h = vb[2] - vb[0], vb[3] - vb[1]
            ok = ob["vis"] >= o["vis_threshold"] and min(w, h) >= o["min_box_side_px"] and ob["in_fov"]
            cls = 1 if ok else distractor
            rows.append(f"{fr['frame']},{ob['id']},{vb[0]:.2f},{vb[1]:.2f},{w:.2f},{h:.2f},1,{cls},{ob['vis']:.3f}")
    return rows


def write_gt_sequence(root: Path, seq: str, truth: list[dict], proto: dict, fps: int, width: int, height: int):
    d = Path(root) / seq
    (d / "gt").mkdir(parents=True, exist_ok=True)
    (d / "gt" / "gt.txt").write_text("\n".join(gt_rows(truth, proto)) + "\n")
    (d / "seqinfo.ini").write_text(
        f"[Sequence]\nname={seq}\nimDir=img1\nframeRate={fps}\nseqLength={len(truth)}\n"
        f"imWidth={width}\nimHeight={height}\nimExt=.png\n")


def write_tracks(path: Path, rows: list[dict]):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, TRACK_FIELDS)
        w.writeheader()
        w.writerows(rows)


def read_tracks(path: Path, observed_only: bool = True) -> dict:
    """{frame: [(id, (x1,y1,x2,y2)), ...]} from a project track CSV."""
    out = {}
    with Path(path).open() as fh:
        for r in csv.DictReader(fh):
            if observed_only and r["status"] != "observed":
                continue
            out.setdefault(int(r["frame"]), []).append(
                (int(r["id"]), tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))))
    return out


def tracks_to_mot(tracks_by_frame: dict) -> list[str]:
    rows = []
    for f in sorted(tracks_by_frame):
        for tid, (x1, y1, x2, y2) in tracks_by_frame[f]:
            rows.append(f"{f},{tid},{x1:.2f},{y1:.2f},{x2 - x1:.2f},{y2 - y1:.2f},1,-1,-1,-1")
    return rows


def run_trackeval(gt_seqs: dict, tracker_outputs: dict) -> dict:
    """Evaluate in a temp folder.

    gt_seqs: {seq: (gt_rows, n_frames)}; tracker_outputs: {tracker: {seq: mot_rows}}.
    Returns {tracker: {"HOTA","AssA","DetA","IDF1","IDSW","MOTA","FP","FN"}} over all sequences.
    """
    import trackeval

    bench, split = "SIM", "eval"
    root = Path(tempfile.mkdtemp(prefix="trackeval_"))
    try:
        for seq, (rows, n) in gt_seqs.items():
            d = root / "gt" / f"{bench}-{split}" / seq / "gt"
            d.mkdir(parents=True)
            (d / "gt.txt").write_text("\n".join(rows) + "\n")
            (d.parent / "seqinfo.ini").write_text(f"[Sequence]\nname={seq}\nseqLength={n}\n")
        for trk, seqs in tracker_outputs.items():
            d = root / "trackers" / f"{bench}-{split}" / trk / "data"
            d.mkdir(parents=True)
            for seq, rows in seqs.items():
                (d / f"{seq}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
        ecfg = trackeval.Evaluator.get_default_eval_config()
        ecfg.update({"USE_PARALLEL": False, "PRINT_RESULTS": False, "PRINT_CONFIG": False,
                     "TIME_PROGRESS": False, "OUTPUT_SUMMARY": False, "OUTPUT_DETAILED": False,
                     "PLOT_CURVES": False, "DISPLAY_LESS_PROGRESS": True})
        dcfg = trackeval.datasets.MotChallenge2DBox.get_default_dataset_config()
        dcfg.update({"GT_FOLDER": str(root / "gt"), "TRACKERS_FOLDER": str(root / "trackers"),
                     "BENCHMARK": bench, "SPLIT_TO_EVAL": split, "PRINT_CONFIG": False,
                     "SEQ_INFO": {s: n for s, (_, n) in gt_seqs.items()},
                     "TRACKERS_TO_EVAL": list(tracker_outputs)})
        metrics = [trackeval.metrics.HOTA(), trackeval.metrics.CLEAR({"PRINT_CONFIG": False}),
                   trackeval.metrics.Identity({"PRINT_CONFIG": False})]
        res, _ = trackeval.Evaluator(ecfg).evaluate([trackeval.datasets.MotChallenge2DBox(dcfg)], metrics)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    out = {}
    for trk in tracker_outputs:
        r = res["MotChallenge2DBox"][trk]["COMBINED_SEQ"]["pedestrian"]
        out[trk] = {"HOTA": float(r["HOTA"]["HOTA"].mean()), "AssA": float(r["HOTA"]["AssA"].mean()),
                    "DetA": float(r["HOTA"]["DetA"].mean()), "IDF1": float(r["Identity"]["IDF1"]),
                    "IDSW": int(r["CLEAR"]["IDSW"]), "MOTA": float(r["CLEAR"]["MOTA"]),
                    "FP": int(r["CLEAR"]["CLR_FP"]), "FN": int(r["CLEAR"]["CLR_FN"])}
    return out
