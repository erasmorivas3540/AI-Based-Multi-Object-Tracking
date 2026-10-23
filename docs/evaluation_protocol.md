# Evaluation protocol (Week 2–3 deliverable)

**Status: DRAFT until the Week 3 freeze.** At freeze, record the SHA-256 of
`configs/event_protocol.yaml`, `configs/detector.yaml` and
`configs/scenario_design.yaml` in `docs/decisions_log.md`. After that, any change
reruns every method and is disclosed.

Implements plan §16 (events), §17 (detector) and §23 (metrics). Code:
`tracking_evaluation/events.py`, `mot_io.py`; scripts `evaluate_tracks.py`,
`eval_detector.py`. Known-answer tests: `tests/test_events.py`,
`tests/known_answer/`, `scripts/reference_trackers.py`.

## 1. Observability

A target is **observable** in a frame when all three hold:
- visible fraction `vis ≥ 0.5`
- visible-box short side `≥ 6 px`
- `in_fov` (centre in front of the camera and inside the image, ≥ 50% in image)

A change of state counts only if it lasts **≥ 3 frames** (0.15 s). Shorter flicker
is absorbed, and the change is back-dated to the frame where it began.

## 2. Primary recovery events (truth only, before any tracker runs)

An event is a run of unobservable frames between two observable runs. It is
**eligible** when:

| Rule | Value | Exclusion reason if violated |
|---|---|---|
| observable before the gap | ≥ 1.0 s | `pre_too_short`, or `boundary_pre` at clip start |
| gap length | ≤ 2.0 s | `gap_too_long` (secondary analysis only) |
| target stays in view during the gap | required | `left_fov` (a different event type) |
| observable after reappearing | ≥ 1.0 s (restore + hold) | `post_too_short`, or `boundary_post` at clip end |

Each event records its cause (the object that hid it most), whether it matches a
scheduled occluder slot, and its gap length. **The denominator is every eligible
event.** Gating, dropped frames or early track deletion never remove an event.

## 3. Scoring an event

Per frame, tracker boxes (observed status only) are matched one-to-one to truth
visible boxes by Hungarian assignment at IoU ≥ 0.5.

1. **Pre-loss identity:** the track id matched to the target at the latest frame
   within the 1.0 s before the gap. None means failure `no_pre_track`.
2. **Restore:** within 0.5 s of reappearance, the target must again be matched to
   that id.
3. **Hold:** for the following 0.5 s it must not carry any other id.
4. **Strict wrong-id rule:** inside the restore and hold windows, the event fails if
   the target carries a different id (`wrong_id_after_reappear`,
   `switched_during_hold`) or the old id sits on another target
   (`old_id_on_other_target`).
5. Frames where the target is simply unmatched (a missed detection) are allowed.

**Recovery recall** = recovered eligible events / all eligible events.

## 4. Recovery precision (action level)

A **recovery action** is a track id restored after at least one frame without an
observed output. Trackers should log actions (`<clip>.actions.csv`: frame,
track_id); otherwise they are inferred from the output. An action is **correct**
if the restored track lands on the same true object it was on when last matched.
A track that never matched a true object makes every one of its actions incorrect.

**Recovery precision** = correct actions / all actions, over every action, not only
those tied to eligible events. Always report raw counts with the ratios.

## 5. Identity benchmark (TrackEval)

- GT export: observable targets are class 1. Partly visible or too-small objects
  are class 8 (distractor): a tracker box on them is removed, neither TP nor FP.
  Fully hidden targets are omitted.
- Tracker export: observed states only. Predicted-only states are evaluated separately.
- Metrics: HOTA, AssA, DetA, IDF1, IDSW, MOTA via TrackEval commit `12c8791` with
  the NumPy shim in `mot_io.py`.
- Do **not** use `Frag` to judge recovery: it counts the truth visibility gap even
  when the identity is recovered perfectly (Week 1 finding).

## 6. Detector evaluation and caching

- Truth targets use the observability rule of §1. Partly visible objects are ignored.
- Matching: greedy by score, class-aware, IoU ≥ 0.5. A miss whose best IoU is in
  [0.1, 0.5) is a **localisation failure**; otherwise it is a **no-box miss**.
- Reported by class, size bin (√area: 0–16, 16–32, 32–64, 64+ px), visibility,
  blur and camera motion, plus median box bias as a coordinate-bug check.
- The detector is chosen on **val**, then frozen. The cache stores per clip:
  - **raw:** conf ≥ 0.01, NMS IoU 0.95, ≤ 1000 boxes. This approximates pre-NMS
    candidates because Ultralytics does not expose head outputs before NMS. Label
    any method that uses them accordingly.
  - **final:** raw → class-wise NMS IoU 0.7, conf ≥ 0.05.
  Boxes are in original image pixels, with weights hash and settings in the sidecar JSON.
- Cached-detection runtimes are not live pipeline runtimes.

## 7. Verified known answers (pilot, 12 flights)

| Reference tracker | HOTA | IDSW | Eligible events | Recall | Actions | Precision |
|---|---|---|---|---|---|---|
| `oracle_keep` (true ids) | 1.000 | 0 | 84 | 1.000 | 163 | 1.000 |
| `oracle_newid` (new id after every gap) | 0.695 | 163 | 84 | 0.000 | 0 | n/a |

Re-run after any change to the protocol or labels:
`reference_trackers.py` → `evaluate_tracks.py --trackers oracle_keep oracle_newid`.

## 8. Decisions to confirm at the freeze

- `vis_threshold` 0.5, `min_box_side_px` 6, `persistence_frames` 3 (look at the
  pilot audit before changing).
- Strict wrong-id rule (§3.4). A lenient variant could allow a transient new id that
  is later replaced, but changing it after seeing results is not allowed.
- Whether events whose cause is another *target* (crossing) stay in the primary
  set, or are reported as a separate stratum. The current code keeps them in.
