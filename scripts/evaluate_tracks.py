"""Score tracker outputs: TrackEval identity metrics + the recovery-event protocol.

    python scripts/evaluate_tracks.py --trackers oracle_keep oracle_newid --splits val

Inputs: outputs/tracks/<tracker>/<clip_id>.csv (project track format: frame, id,
x1, y1, x2, y2, score, status) and optionally <clip_id>.actions.csv with logged
recovery actions (frame, track_id). Without a log, actions are inferred from ids
that reappear after a gap.

Outputs (outputs/eval/<name>/):
  summary.csv / summary.md   per tracker: HOTA, AssA, IDF1, IDSW, recovery recall/precision
  by_factor.csv              recovery recall by camera motion, occlusion, blur, target group
  events_<tracker>.csv       every eligible event with outcome and failure reason
  actions_<tracker>.csv      every recovery action with correctness
  run_record.json
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import _bootstrap  # noqa: F401
from _bootstrap import ROOT, load_yaml
from _runinfo import sha256_file, write_record
from tracking_evaluation.events import (extract_events, infer_recovery_actions, match_frames, score_actions,
                                        score_events, summarize)
from tracking_evaluation.mot_io import gt_rows, read_tracks, run_trackeval, tracks_to_mot
from tracking_sim.design import check_design, load_design
from tracking_sim.scenario import Scenario
from tracking_sim.truth import read_truth, truth_arrays

ap = argparse.ArgumentParser()
ap.add_argument("--trackers", nargs="+", required=True)
ap.add_argument("--tracks", default=ROOT / "outputs/tracks")
ap.add_argument("--data", default=ROOT / "data")
ap.add_argument("--manifests", default=ROOT / "manifests")
ap.add_argument("--protocol", default=ROOT / "configs/event_protocol.yaml")
ap.add_argument("--splits", nargs="+", default=["val"])
ap.add_argument("--name", default="dev")
args = ap.parse_args()

proto = load_yaml(args.protocol)
design = load_design(args.manifests)
sealed = (Path(args.manifests) / "test_manifest.sha256").read_text().split()[0]
if check_design(design, sealed):
    raise SystemExit("design check failed")
flights = {f["flight_id"]: f for f in design["flights"]}
out = Path(args.name) if Path(args.name).is_absolute() else ROOT / "outputs/eval" / args.name
out.mkdir(parents=True, exist_ok=True)

clips = [c for c in design["clips"] if c["split"] in set(args.splits)
         and all((Path(args.tracks) / t / f"{c['clip_id']}.csv").exists() for t in args.trackers)]
if not clips:
    raise SystemExit("no clips with outputs from every tracker")

gt_seqs, trk_mot = {}, defaultdict(dict)
all_events, all_actions = defaultdict(list), defaultdict(list)
truth_cache = {}
for c in clips:
    fid = c["flight_id"]
    if fid not in truth_cache:
        _, truth = read_truth(Path(args.data) / fid / "truth.jsonl")
        sc = Scenario.load(Path(args.data) / fid / "scenario")
        fps = round(1 / (sc.times[1] - sc.times[0]))
        events = extract_events(truth_arrays(truth), proto, fps, fid, sc.schedule)
        truth_cache[fid] = (truth, fps, events)
    truth, fps, events = truth_cache[fid]
    gt_seqs[c["clip_id"]] = (gt_rows(truth, proto), len(truth))
    for t in args.trackers:
        tbf = read_tracks(Path(args.tracks) / t / f"{c['clip_id']}.csv")
        trk_mot[t][c["clip_id"]] = tracks_to_mot(tbf)
        assign, inv = match_frames(truth, tbf, proto["scoring"]["match_iou"])
        log = Path(args.tracks) / t / f"{c['clip_id']}.actions.csv"
        actions = ([{"frame": int(r["frame"]), "track_id": int(r["track_id"])} for r in csv.DictReader(log.open())]
                   if log.exists() else infer_recovery_actions(tbf, len(truth)))
        tags = {k: flights[fid][k] for k in ("camera_motion", "occlusion_s", "target_group")} | {"blur": c["blur"]}
        for e in score_events(events, assign, inv, proto, fps):
            all_events[t].append(e | tags | {"clip_id": c["clip_id"]})
        for a in score_actions(actions, inv):
            all_actions[t].append(a | {"clip_id": c["clip_id"]})

te = run_trackeval(gt_seqs, dict(trk_mot))
summary = []
for t in args.trackers:
    s = summarize(all_events[t], all_actions[t])
    summary.append({"tracker": t, **{k: round(v, 4) if isinstance(v, float) else v for k, v in te[t].items()},
                    **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items() if k != "failures"},
                    "failures": json.dumps(s["failures"])})
    with open(out / f"events_{t}.csv", "w", newline="") as fh:
        if all_events[t]:
            w = csv.DictWriter(fh, list(all_events[t][0]))
            w.writeheader()
            w.writerows(all_events[t])
    with open(out / f"actions_{t}.csv", "w", newline="") as fh:
        if all_actions[t]:
            w = csv.DictWriter(fh, list(all_actions[t][0]))
            w.writeheader()
            w.writerows(all_actions[t])

by_factor = []
for t in args.trackers:
    for factor in ("camera_motion", "occlusion_s", "blur", "target_group"):
        groups = defaultdict(list)
        for e in all_events[t]:
            groups[e[factor]].append(e["success"])
        for level, v in sorted(groups.items(), key=lambda kv: str(kv[0])):
            by_factor.append({"tracker": t, "factor": factor, "level": level, "events": len(v),
                              "recovered": sum(v), "recall": round(sum(v) / len(v), 4)})

with open(out / "summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, list(summary[0]))
    w.writeheader()
    w.writerows(summary)
with open(out / "by_factor.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, list(by_factor[0]) if by_factor else ["tracker"])
    w.writeheader()
    w.writerows(by_factor)
cols = ["tracker", "HOTA", "AssA", "IDF1", "IDSW", "eligible_events", "recovered", "recovery_recall",
        "recovery_actions", "correct_actions", "recovery_precision"]
md = [f"# Tracking evaluation: {args.name}", "", f"Splits {args.splits}, {len(clips)} clips.", "",
      "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
md += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in summary]
(out / "summary.md").write_text("\n".join(md) + "\n")
write_record(out / "run_record.json", task="track_eval", trackers=args.trackers, splits=args.splits,
             clips=len(clips), protocol_sha=sha256_file(args.protocol), sealed_test_hash=sealed)
print("\n".join(md))
