# AI-Based Multi-Object Tracking for Autonomous Multi-Drone Operations

**Status: Weeks 2–3 tooling built and tested on a toy-rendered pilot; Gazebo rendering not yet verified. No experimental results yet.**

AQFS Labs, California State University, San Bernardino.

## Research question

Can a small, calibrated, learned recovery score restore the correct identity of a
temporarily lost target more often than a matched hand-designed rule — at ≥95%
recovery precision — when the camera is moving and visibility is degraded
(occlusion, motion blur)?

## What the system does

A simulated camera drone (Gazebo + ROS 2) watches 3–8 drones and ground vehicles.
A YOLO-family detector draws boxes; ByteTrack links boxes into tracks; a learned
recovery model decides whether a reappearing object is a recently lost track; a
Kalman filter forecasts image positions 0.5 s and 1.0 s ahead.

Outputs are **camera-local** and in **image coordinates**. The system does not
estimate metric distance, match identities across cameras, or control flight.

## Six-week plan

| Week | Focus | Exit gate |
|---|---|---|
| 1 | Setup, literature audit, smoke test, minimal Gazebo world | One simulated image flows through detect → track → publish → evaluate |
| 2 | Simulation scenarios, ground-truth labels, pilot data, protocol freeze | Labels verified visually; event definitions and splits frozen |
| 3 | Full dataset, detector fine-tune and freeze, cached detections | Detector recall known by size/class; test set sealed |
| 4 | Baselines, matched heuristic control, learned recovery, calibration | Validation precision–recall curve; operating point chosen |
| 5 | ROS 2 integration, forecasts, freeze, held-out test and runtime | Complete test outputs, untouched by tuning |
| 6 | Statistics, failure analysis, report, presentation | Every claim traceable to retained outputs |

Full scope, cuts and Week 1 checklist: [`docs/scope_6week.md`](docs/scope_6week.md).

## Repository layout

```
configs/              scenario design, event protocol, detector settings (frozen in Week 3)
manifests/            flight design, splits, sealed test manifest (tracked)
docs/                 plans, scope, dataset spec, evaluation protocol, decisions log, runbooks
scripts/              command-line steps (see docs/runbook_weeks2-3.md)
  smoke_test/           Week 1 environment checks
src/                  ROS 2 workspace (ament_python), importable without ROS
  tracking_sim/         scenarios, geometry, part shapes, analytic truth, Gazebo world, toy renderer
  tracking_evaluation/  recovery events + scoring, TrackEval adapter, label audit
  tracking_detector/    label rules, letterbox/NMS/matching, detection cache format
  tracking_core/        track state, association, recovery interface      (Week 4)
  tracking_interfaces/  ROS message definitions                          (Week 5)
notebooks/            demo_weeks1-3.ipynb: quick tour of everything built so far
tests/                pytest suite (44 tests), incl. known-answer evaluation checks
data/                 NOT tracked: frames, truth, scenarios (see data/README.md)
outputs/, runs/       NOT tracked: audits, exports, caches, evaluations, detector runs
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-eval.txt
pytest -q                                                    # 44 tests

# offline pilot without Gazebo: 12 flights, toy-rendered
python scripts/make_design.py --check
python scripts/build_flights.py --pilot --render toy
python scripts/audit_labels.py --flights $(ls data | grep ^dev_)
python scripts/reference_trackers.py
python scripts/evaluate_tracks.py --trackers oracle_keep oracle_newid --splits train val
```

Then follow [`docs/gazebo_verification.md`](docs/gazebo_verification.md) and
[`docs/runbook_weeks2-3.md`](docs/runbook_weeks2-3.md). Week 1 environment checks
are in `scripts/smoke_test/`; record versions in [`docs/versions.md`](docs/versions.md).

Key documents: [original plan](docs/plans/AI_Object_Tracking_Detailed_Plan.md) · [dataset spec](docs/dataset_spec.md) ·
[evaluation protocol](docs/evaluation_protocol.md) ·
[decisions log](docs/decisions_log.md)

## Licensing note

Undecided. Ultralytics YOLO is distributed under AGPL-3.0; importing it may
constrain this repository's license. Resolve with the lab before the first
public release.
