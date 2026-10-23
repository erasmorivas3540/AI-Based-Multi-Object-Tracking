"""Known-answer test for the evaluation pipeline.

Builds tiny hand-made sequences where the correct identity metrics are known in
advance, runs TrackEval on them, and checks TrackEval reports what we planted.
If this fails, every later tracking number is suspect.

Two ground-truth objects, 20 frames, crossing paths. Object 1 is hidden in
frames 9-11 (no ground-truth box while hidden).

  recovered      object 1 returns with its ORIGINAL id  -> IDSW 0, IDF1 1.0, FP 0
                 (a perfect tracker)
  lost_new_id    object 1 returns with a NEW id         -> IDSW 1
                 (failed recovery)
  swap           IDs swap after the objects cross       -> IDSW 2 (one per object)
  hidden_boxes   correct ids, but the tracker keeps     -> IDSW 0, FP 3
                 publishing predicted boxes for object 1
                 while it is hidden

Lessons this test locks in (both found when the test was first run):
  1. Recovery success shows up as an identity switch that did NOT happen.
     TrackEval's Frag counts 1 for BOTH recovered and lost_new_id, because it
     counts the ground-truth visibility gap itself. Frag cannot measure recovery;
     use IDSW/IDF1/AssA plus the project's own recovery-event protocol.
  2. Publishing predicted-only boxes during occlusion is scored as false
     positives against visible-only ground truth. Predicted-only states must be
     labelled and evaluated separately (plan section 16).

Run:  python tests/known_answer/test_identity_swap.py
Needs: pip install -r requirements-eval.txt
"""
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

# TrackEval's main branch still uses np.float / np.int / np.bool, which NumPy
# removed in 1.24. Restore them as the builtin types (identical behavior) so
# TrackEval runs on current NumPy. Record this in docs/versions.md.
for _name, _typ in (("float", float), ("int", int), ("bool", bool)):
    if _name not in np.__dict__:
        setattr(np, _name, _typ)

import trackeval  # noqa: E402

N_FRAMES = 20
BENCH, SPLIT = "KNOWN", "test"
W, H = 30, 30  # box size, pixels


def obj_box(obj_id: int, frame: int):
    """Object 1 moves left->right, object 2 right->left; they cross mid-sequence."""
    if obj_id == 1:
        x = 10 + frame * 20
    else:
        x = 410 - frame * 20
    return x, 100, W, H


OCCLUDED_FRAMES = {9, 10, 11}  # object 1 hidden (no GT box, no detection)


def gt_rows():
    rows = []
    for f in range(1, N_FRAMES + 1):
        for oid in (1, 2):
            if oid == 1 and f in OCCLUDED_FRAMES:
                continue  # hidden objects are not scored as visible targets
            x, y, w, h = obj_box(oid, f)
            # MOTChallenge GT: frame,id,x,y,w,h,consider,class(1=pedestrian),visibility
            rows.append(f"{f},{oid},{x},{y},{w},{h},1,1,1.0")
    return rows


def tracker_rows(mode: str):
    rows = []
    for f in range(1, N_FRAMES + 1):
        for oid in (1, 2):
            if mode != "hidden_boxes" and oid == 1 and f in OCCLUDED_FRAMES:
                continue
            tid = oid
            if mode == "swap" and f >= 11:
                tid = 2 if oid == 1 else 1
            if mode == "lost_new_id" and oid == 1 and f > max(OCCLUDED_FRAMES):
                tid = 3  # tracker spawned a new identity instead of recovering
            x, y, w, h = obj_box(oid, f)
            rows.append(f"{f},{tid},{x},{y},{w},{h},1.0,-1,-1,-1")
    return rows


EXPECTED = {
    #               IDSW  FP    IDF1 (None = don't check)
    "recovered":    (0,   0,    1.0),
    "lost_new_id":  (1,   0,    None),
    "swap":         (2,   0,    None),
    "hidden_boxes": (0,   3,    None),
}


def build_dirs(root: Path):
    gt_seq = root / "gt" / f"{BENCH}-{SPLIT}" / "seq01"
    (gt_seq / "gt").mkdir(parents=True)
    (gt_seq / "gt" / "gt.txt").write_text("\n".join(gt_rows()) + "\n")
    (gt_seq / "seqinfo.ini").write_text(
        "[Sequence]\nname=seq01\nimDir=img1\nframeRate=20\n"
        f"seqLength={N_FRAMES}\nimWidth=640\nimHeight=480\nimExt=.jpg\n"
    )
    for mode in EXPECTED:
        d = root / "trackers" / f"{BENCH}-{SPLIT}" / mode / "data"
        d.mkdir(parents=True)
        (d / "seq01.txt").write_text("\n".join(tracker_rows(mode)) + "\n")


def run(root: Path):
    eval_cfg = trackeval.Evaluator.get_default_eval_config()
    eval_cfg.update({"USE_PARALLEL": False, "PRINT_RESULTS": False, "PRINT_CONFIG": False,
                     "TIME_PROGRESS": False, "OUTPUT_SUMMARY": False, "OUTPUT_DETAILED": False,
                     "PLOT_CURVES": False})
    ds_cfg = trackeval.datasets.MotChallenge2DBox.get_default_dataset_config()
    ds_cfg.update({"GT_FOLDER": str(root / "gt"), "TRACKERS_FOLDER": str(root / "trackers"),
                   "BENCHMARK": BENCH, "SPLIT_TO_EVAL": SPLIT,
                   "SEQ_INFO": {"seq01": N_FRAMES}, "TRACKERS_TO_EVAL": list(EXPECTED),
                   "PRINT_CONFIG": False})
    evaluator = trackeval.Evaluator(eval_cfg)
    metrics = [trackeval.metrics.HOTA(), trackeval.metrics.CLEAR({"PRINT_CONFIG": False}),
               trackeval.metrics.Identity({"PRINT_CONFIG": False})]
    res, _ = evaluator.evaluate([trackeval.datasets.MotChallenge2DBox(ds_cfg)], metrics)
    return res["MotChallenge2DBox"]


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="known_answer_"))
    try:
        build_dirs(root)
        results = run(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    ok = True
    print(f"{'tracker':<13} {'IDSW':>5} {'FP':>4} {'Frag':>5} {'IDF1':>6} {'HOTA':>6} {'AssA':>6}  check")
    for mode, (idsw_exp, fp_exp, idf1_exp) in EXPECTED.items():
        r = results[mode]["COMBINED_SEQ"]["pedestrian"]
        idsw, frag = int(r["CLEAR"]["IDSW"]), int(r["CLEAR"]["Frag"])
        fp = int(r["CLEAR"]["CLR_FP"])
        idf1 = float(r["Identity"]["IDF1"])
        hota = float(r["HOTA"]["HOTA"].mean())
        assa = float(r["HOTA"]["AssA"].mean())
        good = idsw == idsw_exp
        good &= fp == fp_exp
        good &= idf1_exp is None or abs(idf1 - idf1_exp) < 1e-6
        ok &= good
        print(f"{mode:<13} {idsw:>5} {fp:>4} {frag:>5} {idf1:>6.3f} {hota:>6.3f} {assa:>6.3f}  "
              f"{'PASS' if good else 'FAIL (expected IDSW=%d, FP=%d)' % (idsw_exp, fp_exp)}")
    print("\nAll known-answer checks passed." if ok else "\nKnown-answer test FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
