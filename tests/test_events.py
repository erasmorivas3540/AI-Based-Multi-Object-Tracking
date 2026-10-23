"""Known-answer tests for the recovery-event protocol (plan section 16)."""
import numpy as np
import pytest
import yaml

from tracking_evaluation.events import (debounce, extract_events, infer_recovery_actions, match_frames,
                                        score_actions, score_events, summarize)
from conftest import ROOT

FPS = 20
PROTO = yaml.safe_load((ROOT / "configs/event_protocol.yaml").read_text())


def make_truth(F, objects):
    """objects: {id: (visible_mask(F,), x_offset)}. Boxes are 30x30 px, spaced apart."""
    ids = sorted(objects)
    vis = np.zeros((len(ids), F))
    fov = np.ones((len(ids), F), bool)
    side = np.zeros((len(ids), F))
    boxes = np.full((len(ids), F, 4), np.nan)
    occ = [[None] * F for _ in ids]
    truth = [{"frame": f + 1, "objects": []} for f in range(F)]
    for k, tid in enumerate(ids):
        mask, x = objects[tid]
        for f in range(F):
            b = [x, 100.0, x + 30.0, 130.0]
            if mask[f]:
                vis[k, f], side[k, f], boxes[k, f] = 1.0, 30.0, b
            else:
                occ[k][f] = "occluder_0"
            truth[f]["objects"].append({"id": tid, "visible_box": b if mask[f] else None})
    return truth, (ids, vis, fov, side, boxes, occ)


def mask(F, hidden):
    m = np.ones(F, bool)
    for a, b in hidden:
        m[a:b] = False
    return m


def tracks(F, spec):
    """spec: {truth_x: [(f_from, f_to, track_id)]} -> tracks_by_frame (1-based)."""
    out = {}
    for x, segs in spec.items():
        for a, b, tid in segs:
            for f in range(a, b):
                out.setdefault(f + 1, []).append((tid, (x, 100.0, x + 30.0, 130.0)))
    return out


def test_debounce_absorbs_flicker_and_backdates():
    raw = np.array([1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1], bool)
    out = debounce(raw, 3)
    assert out.tolist() == [1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1]


def test_single_eligible_event():
    F = 100
    _, arrays = make_truth(F, {1: (mask(F, [(40, 60)]), 0)})
    ev = extract_events(arrays, PROTO, FPS, "c")
    assert len(ev) == 1 and ev[0]["eligible"]
    assert ev[0]["gap_frames"] == 20 and ev[0]["last_visible_frame"] == 40 and ev[0]["reappear_frame"] == 61


@pytest.mark.parametrize("hidden,idx,reason", [
    ([(10, 30)], 0, "boundary_pre"),            # only 10 frames visible from clip start
    ([(40, 90)], 0, "gap_too_long"),            # 2.5 s gap
    ([(40, 60)], 0, None),
    ([(80, 95)], 0, "boundary_post"),           # 5 frames visible before the clip ends
    ([(30, 50), (60, 70)], 0, "post_too_short"),  # second gap cuts the 20-frame window to 10
    ([(30, 50), (60, 70)], 1, "pre_too_short"),   # ...and the second event lacks 1 s before
    ([(30, 32), (60, 80)], 0, None),            # 2-frame flicker absorbed: only one event
])
def test_exclusion_reasons(hidden, idx, reason):
    F = 100
    _, arrays = make_truth(F, {1: (mask(F, hidden), 0)})
    evs = extract_events(arrays, PROTO, FPS, "c")
    assert evs[idx]["exclusion_reason"] == reason
    if hidden == [(30, 32), (60, 80)]:
        assert len(evs) == 1 and evs[0]["last_visible_frame"] == 60


def test_left_fov_is_not_primary():
    F = 100
    _, arrays = make_truth(F, {1: (mask(F, [(40, 60)]), 0)})
    arrays[2][0, 45:50] = False  # centre leaves the image during the gap
    assert extract_events(arrays, PROTO, FPS, "c")[0]["exclusion_reason"] == "left_fov"


def _score(F, hidden, trk_spec, other=None):
    objs = {1: (mask(F, hidden), 0)}
    if other is not None:
        objs[2] = (np.ones(F, bool), other)
    truth, arrays = make_truth(F, objs)
    evs = [e for e in extract_events(arrays, PROTO, FPS, "c") if e["target_id"] == 1]
    tbf = tracks(F, trk_spec)
    assign, inv = match_frames(truth, tbf, PROTO["scoring"]["match_iou"])
    return score_events(evs, assign, inv, PROTO, FPS), tbf, inv


def test_perfect_recovery_succeeds():
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7), (60, 100, 7)]})
    assert res[0]["success"] and res[0]["restored_frame"] == 61


def test_new_identity_fails():
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7), (60, 100, 9)]})
    assert res[0]["failure"] == "wrong_id_after_reappear"


def test_late_restore_fails():
    # unmatched for 12 frames (0.6 s) after reappearing, then the old id returns
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7), (72, 100, 7)]})
    assert res[0]["failure"] == "not_restored_in_time"


def test_restore_within_window_with_missed_frames_succeeds():
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7), (65, 100, 7)]})
    assert res[0]["success"]


def test_switch_during_hold_fails():
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7), (60, 65, 7), (65, 100, 9)]})
    assert res[0]["failure"] == "switched_during_hold"


def test_old_id_on_other_target_fails():
    res, _, _ = _score(100, [(40, 60)], {0: [(0, 40, 7)], 300: [(60, 100, 7)]}, other=300)
    assert res[0]["failure"] == "old_id_on_other_target"


def test_never_tracked_counts_as_failure():
    res, _, _ = _score(100, [(40, 60)], {0: [(60, 100, 7)]})
    assert res[0]["failure"] == "no_pre_track"


def test_action_precision():
    F = 100
    # target 1 hidden 40-60 and recovered correctly by id 7; id 8 on target 2 is
    # dropped and then "recovered" onto target 1's position -> wrong action
    res, tbf, inv = _score(F, [(40, 60)], {0: [(0, 40, 7), (60, 100, 7)],
                                             300: [(0, 50, 8), (55, 60, 8)]}, other=300)
    acts = score_actions(infer_recovery_actions(tbf, F), inv)
    assert [a["track_id"] for a in acts] == [8, 7]
    assert [a["correct"] for a in acts] == [True, True]
    s = summarize(res, acts)
    assert s["recovery_recall"] == 1.0 and s["recovery_precision"] == 1.0


def test_wrong_target_action_is_incorrect():
    F = 100
    truth, arrays = make_truth(F, {1: (np.ones(F, bool), 0), 2: (np.ones(F, bool), 300)})
    tbf = tracks(F, {0: [(0, 40, 5)], 300: [(45, 100, 5)]})  # id 5 jumps targets after a gap
    _, inv = match_frames(truth, tbf, 0.5)
    acts = score_actions(infer_recovery_actions(tbf, F), inv)
    assert len(acts) == 1 and not acts[0]["correct"]


def test_hidden_until_clip_end_is_boundary_post():
    F = 100
    _, arrays = make_truth(F, {1: (mask(F, [(60, 100)]), 0)})
    ev = extract_events(arrays, PROTO, FPS, "c")[0]
    assert ev["exclusion_reason"] == "boundary_post" and ev["reappear_frame"] is None
