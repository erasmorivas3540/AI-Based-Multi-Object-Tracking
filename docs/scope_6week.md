# Six-week scope

Compressed from the 12-week detailed plan (`AI_Object_Tracking_Detailed_Plan.docx`).
At 15–20 h/week this is roughly 90–120 hours. The research question is unchanged;
scope around it is reduced.

## Kept

- Primary hypothesis H1: learned recovery score vs. matched heuristic control at
  ≥95% validation recovery precision, paired flight-level bootstrap intervals.
- Frozen detector, sealed held-out test set, flight-level splits.
- Native ByteTrack and BoT-SORT baselines; matched heuristic control C0.
- ROS 2 live pipeline with one observer; runtime measured on a declared machine.
- Constant-velocity Kalman forecasts at 0.5 s and 1.0 s (image plane).

## Reduced

| Item | 12-week plan | 6-week plan |
|---|---|---|
| Clips | 320 (160 dev / 160 test) | 216 from 108 rendered flights: 144 dev / 72 test (see D2, D3) |
| Occlusion levels | 0, 0.5, 1.0, 2.0 s | 0 (near-miss control), 1.0, 2.0 s |
| Seeds per condition | 5 | test 3, dev 6 (4 train + 2 val) |
| Test design | 2 × 4 × 2 × 2 × 5 | 2 camera × 3 occlusion × 2 target × 3 seeds = 36 flights, each with paired blur → 72 clips |
| Learned models | Logistic regression + optional MLP | Logistic regression only |
| Ablations | Three feature groups | One: camera-motion features (H2) |
| Forecast evaluation | ADE/FDE + ellipse coverage | ADE/FDE only |

Fewer seeds means wider confidence intervals. State this as a limitation.

## Stretch (only if ahead of schedule)

- TrackTrack baseline; MMTracking environment (confirm priority with advisor)
- Two-observer demo
- Covariance-ellipse coverage analysis

## Dropped

- Real-video transfer check
- Adaptive track lifetimes
- MLP recovery model

## Storage estimate

108 rendered flights × 400 frames = 43,200 canonical PNGs (blur is applied on the
fly). At about 1.2 MB per Gazebo PNG that is roughly 52 GB, plus about 10 GB of
YOLO export. Plan for about 100 GB free. Measure on the first Gazebo flights
(`docs/dataset_spec.md` §6).

## Week 1 checklist

- [ ] Repo scaffold pushed; six GitHub milestones created
- [ ] Smoke test steps 1–7 pass individually (`scripts/smoke_test/`)
- [ ] Smoke test passes end to end once
- [ ] `docs/versions.md` filled for everything that worked
- [ ] Known-answer test passes on your machine (`tests/known_answer/`)
- [ ] Related-work matrix filled (`docs/related_work_matrix.csv`)
- [ ] Novelty note written (`docs/novelty_note.md`)
- [ ] Minimal Gazebo world: one observer camera, one moving target, truth box overlays correctly on a frame
- [ ] Scope confirmed with advisor (`docs/advisor_message_draft.md`)
- [ ] License decision raised with the lab

## Week 1 findings so far

- TrackEval's main branch (commit `12c8791`) uses `np.float`, removed in NumPy
  1.24. A three-line compatibility shim fixes it; see `tests/known_answer/`.
- TrackEval's `Frag` counts a fragmentation for a ground-truth visibility gap even
  when the tracker recovers the identity perfectly. Do not use Frag to measure
  recovery; use the event protocol.
- Publishing predicted-only boxes during occlusion is scored as false positives
  against visible-only ground truth. Evaluate predicted-only states separately.

## Week 2 checklist (simulation, labels, protocol)

Built and tested (toy renderer, 12-flight pilot):
- [x] Numeric factor definitions: `configs/scenario_design.yaml`
- [x] Scenario generator: observer motion profiles, target paths with scripted crossings, occluder schedule calibrated to achieved hidden time
- [x] Analytic labels (`truth.jsonl`): visible box, visibility, field of view, occluder attribution
- [x] Design + splits + provisional test seal: `manifests/`
- [x] Recovery-event protocol + scorer, with known-answer tests on pilot data
- [x] Label audit tool: overlays, contact sheets, event yield, visibility cross-check
- [x] Gazebo world generator + lockstep director (written, **not yet run**)

On your machine:
- [ ] `docs/gazebo_verification.md` steps 1–5 (Gazebo vs analytic boxes median IoU ≥ 0.85)
- [ ] Manual audit of `outputs/audit_gz/audit_log.csv`
- [ ] Tune PILOT values if needed, reseal, log in `docs/decisions_log.md`
- [ ] Advisor check-in: contact sheets, event yield, decisions D2, D3, D5, D7, D9

## Week 3 checklist (dataset, freeze, detector)

Built and tested:
- [x] YOLO export with the test guard; detector training wrapper with run records
- [x] Detector evaluation by class / size / visibility / blur, with box-bias check
- [x] Detection cache (raw + final) and reader; letterbox inversion tests
- [x] Test-data seal and verification
- [x] Dataset specification and evaluation protocol drafts
- [x] Demo notebook: `notebooks/demo_weeks1-3.ipynb`
- [x] Whole detector chain exercised on CPU (export → train → cache → eval); not a result

On your machine:
- [ ] Freeze configs (record hashes)
- [ ] Render all 72 dev + 36 test flights; `seal_test_data.py`
- [ ] Export, fine-tune (960 vs 1280), choose on val, freeze weights
- [ ] Cache detections for train/val
- [ ] Full-dev event yield check (≥ 40 val occlusion events)
