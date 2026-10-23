"""Recovery-event extraction (truth only) and scoring (truth + tracker output).

Implements plan section 16. Events are defined from ground truth alone, before any
tracker is run, so every method faces the same denominator.

Frame indices in this module are 0-based internally; every table it returns uses
1-based `frame` numbers to match truth.jsonl and MOT files.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.optimize import linear_sum_assignment

# ------------------------------------------------------------------ observability


def debounce(raw: np.ndarray, k: int) -> np.ndarray:
    """Hysteresis: the state flips only after the new value persists k frames.

    The flip is back-dated to the first frame of the persisting run, so a real
    disappearance starts when it actually started.
    """
    raw = np.asarray(raw, bool)
    if k <= 1 or len(raw) == 0:
        return raw.copy()
    out = np.empty_like(raw)
    state, run = raw[0], 0
    for f, v in enumerate(raw):
        if v != state:
            run += 1
            if run >= k:
                state = v
                out[f - k + 1:f + 1] = state
                run = 0
                continue
        else:
            run = 0
        out[f] = state
    return out


def observable(vis, in_fov, min_side, proto) -> np.ndarray:
    o = proto["observability"]
    raw = (vis >= o["vis_threshold"]) & (min_side >= o["min_box_side_px"]) & in_fov
    return np.stack([debounce(r, o["persistence_frames"]) for r in raw])


def _runs(x: np.ndarray):
    """[(value, start, end_inclusive), ...]"""
    out, start = [], 0
    for f in range(1, len(x) + 1):
        if f == len(x) or x[f] != x[start]:
            out.append((bool(x[start]), start, f - 1))
            start = f
    return out


# ------------------------------------------------------------------ extraction


def extract_events(truth_arrays, proto: dict, fps: float, clip_id: str, schedule=None) -> list[dict]:
    """All candidate disappearance events, each marked eligible or with an exclusion reason."""
    ids, vis, in_fov, min_side, _boxes, occ_by = truth_arrays
    ev_cfg = proto["events"]
    obs = observable(vis, in_fov, min_side, proto)
    F = obs.shape[1]
    pre_n = int(round(ev_cfg["pre_visible_s"] * fps))
    gap_max = int(round(ev_cfg["max_gap_s"] * fps))
    post_n = int(round((ev_cfg["restore_within_s"] + ev_cfg["hold_s"]) * fps))
    sched = {s.get("target_id"): s for s in (schedule or []) if s.get("status") == "scheduled"}
    events = []
    for k, tid in enumerate(ids):
        runs = _runs(obs[k])
        for i, (val, a, b) in enumerate(runs):
            if val or i == 0:
                continue  # only hidden runs that follow a visible run
            pre = runs[i - 1]
            post = runs[i + 1] if i + 1 < len(runs) else None
            gap = b - a + 1
            hidden_frames = [f for f in range(a, b + 1) if occ_by[k][f]]
            cause = Counter(occ_by[k][f] for f in hidden_frames).most_common(1)
            cause = cause[0][0] if cause else "size_or_out_of_view"
            reason = None
            if post is None:
                reason = "boundary_post"   # still hidden when the clip ends
            elif gap > gap_max:
                reason = "gap_too_long"
            elif ev_cfg["require_in_fov_during_gap"] and not in_fov[k, a:b + 1].all():
                reason = "left_fov"
            elif pre[2] - pre[1] + 1 < pre_n:
                reason = "boundary_pre" if pre[1] == 0 else "pre_too_short"
            elif post[2] - post[1] + 1 < post_n:
                reason = "boundary_post" if post[2] == F - 1 else "post_too_short"
            s = sched.get(tid)
            scheduled = bool(s and cause.startswith("occluder") and
                             abs(a / fps - s["t_start"]) < 0.5)
            events.append({
                "event_id": f"{clip_id}:{tid}:{a + 1}", "clip_id": clip_id, "target_id": int(tid),
                "last_visible_frame": a,                          # 1-based
                "reappear_frame": b + 2 if post is not None else None,
                "gap_frames": gap, "gap_s": round(gap / fps, 3), "cause": cause,
                "scheduled": scheduled, "eligible": reason is None, "exclusion_reason": reason,
            })
    return events


# ------------------------------------------------------------------ per-frame matching


def match_frames(truth: list[dict], tracks_by_frame: dict, iou_thr: float):
    """One-to-one truth<->track matching per frame on visible boxes.

    tracks_by_frame: {frame(1-based): [(track_id, (x1,y1,x2,y2)), ...]} observed states only.
    Returns assign[f]: {truth_id: track_id}, inv[f]: {track_id: truth_id}, 0-based f.
    """
    from tracking_sim.geometry import iou_matrix

    assign, inv = [], []
    for fr in truth:
        objs = [o for o in fr["objects"] if o["visible_box"]]
        trks = tracks_by_frame.get(fr["frame"], [])
        a, b = {}, {}
        if objs and trks:
            iou = iou_matrix([o["visible_box"] for o in objs], [t[1] for t in trks])
            rows, cols = linear_sum_assignment(-iou)
            for r, c in zip(rows, cols):
                if iou[r, c] >= iou_thr:
                    a[objs[r]["id"]] = trks[c][0]
                    b[trks[c][0]] = objs[r]["id"]
        assign.append(a)
        inv.append(b)
    return assign, inv


# ------------------------------------------------------------------ scoring


def score_events(events: list[dict], assign, inv, proto: dict, fps: float) -> list[dict]:
    ev_cfg, sc = proto["events"], proto["scoring"]
    pre_n = int(round(ev_cfg["pre_visible_s"] * fps))
    restore_n = int(round(ev_cfg["restore_within_s"] * fps))
    hold_n = int(round(ev_cfg["hold_s"] * fps))
    out = []
    for ev in events:
        if not ev["eligible"]:
            continue
        tid = ev["target_id"]
        a = int(ev["last_visible_frame"])      # 1-based last visible == 0-based first hidden
        r0 = int(ev["reappear_frame"]) - 1     # 0-based first frame visible again
        res = dict(ev, success=False, failure=None, pre_id=None, restored_frame=None)
        pre_id = None
        for f in range(a - 1, a - 1 - pre_n, -1):
            if f >= 0 and tid in assign[f]:
                pre_id = assign[f][tid]
                break
        res["pre_id"] = pre_id
        if pre_id is None:
            res["failure"] = "no_pre_track"
            out.append(res)
            continue

        def old_id_elsewhere(f):
            other = inv[f].get(pre_id)
            return other is not None and other != tid

        t_r, failure = None, None
        for f in range(r0, min(r0 + restore_n, len(assign))):
            cur = assign[f].get(tid)
            if old_id_elsewhere(f):
                failure = "old_id_on_other_target"
                break
            if cur == pre_id:
                t_r = f
                break
            if cur is not None and sc["strict_wrong_id"]:
                failure = "wrong_id_after_reappear"
                break
            if cur is None and not sc["allow_unmatched_frames"]:
                failure = "unmatched_after_reappear"
                break
        if failure is None and t_r is None:
            failure = "not_restored_in_time"
        if failure is None:
            for f in range(t_r + 1, min(t_r + 1 + hold_n, len(assign))):
                cur = assign[f].get(tid)
                if old_id_elsewhere(f):
                    failure = "old_id_on_other_target"
                    break
                if cur is not None and cur != pre_id:
                    failure = "switched_during_hold"
                    break
                if cur is None and not sc["allow_unmatched_frames"]:
                    failure = "unmatched_during_hold"
                    break
        res["success"] = failure is None
        res["failure"] = failure
        res["restored_frame"] = t_r + 1 if t_r is not None else None
        out.append(res)
    return out


def infer_recovery_actions(tracks_by_frame: dict, n_frames: int) -> list[dict]:
    """Recovery actions for trackers that don't log them: an id that was published,
    went unpublished for >= 1 frame, and is published again."""
    last_seen, actions = {}, []
    for f in range(1, n_frames + 1):
        for tid, _box in tracks_by_frame.get(f, []):
            if tid in last_seen and last_seen[tid] < f - 1:
                actions.append({"frame": f, "track_id": tid})
            last_seen[tid] = f
    return actions


def score_actions(actions: list[dict], inv) -> list[dict]:
    """A recovery action is correct if the restored track lands on the same true
    object it was on before it was lost."""
    out = []
    for act in actions:
        f, tid = act["frame"] - 1, act["track_id"]
        now = inv[f].get(tid) if 0 <= f < len(inv) else None
        prev = None
        for g in range(f - 1, -1, -1):
            if tid in inv[g]:
                prev = inv[g][tid]
                break
        out.append(dict(act, truth_now=now, truth_before=prev,
                        correct=prev is not None and now == prev))
    return out


def summarize(scored_events: list[dict], scored_actions: list[dict]) -> dict:
    n_ev = len(scored_events)
    n_ok = sum(e["success"] for e in scored_events)
    n_act = len(scored_actions)
    n_cor = sum(a["correct"] for a in scored_actions)
    return {"eligible_events": n_ev, "recovered": n_ok,
            "recovery_recall": n_ok / n_ev if n_ev else float("nan"),
            "recovery_actions": n_act, "correct_actions": n_cor,
            "recovery_precision": n_cor / n_act if n_act else float("nan"),
            "failures": dict(Counter(e["failure"] for e in scored_events if not e["success"]))}
