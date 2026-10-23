# Runbook: Weeks 2–3

Commands in order. Each step lists its exit check. Everything runs from the repo root.

## Environments

```bash
# analysis / evaluation (no GPU needed)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-eval.txt
pytest -q                          # 42 tests + run tests/known_answer/test_identity_swap.py

# detector (GPU machine)
pip install -r requirements-detector.txt
```
Gazebo rendering uses the system Python with the gz bindings
(see `gazebo_verification.md`).

---

## Week 2: simulation, labels, pilot, protocol

| # | Step | Command | Exit check |
|---|---|---|---|
| 1 | Design + provisional seal | `python scripts/make_design.py --check` | "design OK" |
| 2 | Toy pilot (no Gazebo) | `python scripts/build_flights.py --pilot --render toy` | 12 flights, every schedule slot `sched` |
| 3 | Toy audit + event yield | `python scripts/audit_labels.py --flights $(ls data \| grep ^dev_)` | toy-mask vs analytic max diff < 0.15; eligible events > 0 in every occluded cell |
| 4 | Evaluation known answers | `python scripts/reference_trackers.py && python scripts/evaluate_tracks.py --trackers oracle_keep oracle_newid --splits train val --name pilot_reference` | keep: recall 1, precision 1, IDSW 0; newid: recall 0 |
| 5 | **Gazebo path** | follow `docs/gazebo_verification.md` steps 1–5 | Gazebo vs analytic median IoU ≥ 0.85 |
| 6 | **Manual label audit** | fill `outputs/audit_gz/audit_log.csv`; open the contact sheets | every row Y, or a logged fix |
| 7 | Tune PILOT values | edit `configs/*.yaml`, rerun 2–5 | event yield per cell; UAV sizes; motion stats as intended |
| 8 | Reseal if the config changed | `python scripts/make_design.py --reseal`; log in `decisions_log.md` | `pytest -q` green |

**Week 2 gate:** boxes, identities and visibility correct on the manually checked
frames; the event protocol returns known answers; motion profiles and occlusion
durations achieved as specified.

Week 2 advisor check-in: show 2–3 contact sheets, the event-yield table and
decisions D2, D3, D5, D7, D9.

---

## Week 3: generate, freeze, detector

| # | Step | Command | Exit check |
|---|---|---|---|
| 1 | Freeze configs | record SHA-256 of the three configs in `decisions_log.md` | no more edits without logging |
| 2 | Dev flights | `python scripts/build_flights.py --splits train val`, then `gz_render_flight.py` per flight (loop as in the verification guide) | 72 flights with 400 frames each |
| 3 | Test flights (once) | `python scripts/build_flights.py --splits test` + render | 36 flights |
| 4 | Seal test data | `python scripts/seal_test_data.py` | `manifests/test_data_seal.json` written; commit it |
| 5 | Export YOLO data | `python scripts/export_yolo.py --out outputs/yolo_v1` | counts printed; no test flights (guarded) |
| 6 | Pre-trained baseline | `python scripts/eval_detector.py --weights yolo11s.pt --splits val --name coco_pretrained` | confirms COCO has no UAV class (expect UAV recall ≈ 0) |
| 7 | Fine-tune (search) | `python scripts/train_detector.py --dataset outputs/yolo_v1 --name det_1280 --imgsz 1280` and `--name det_960 --imgsz 960` | `run_record.json` in each run |
| 8 | Choose on val | `python scripts/eval_detector.py --weights runs/detector/<run>/weights/best.pt --splits val` | recall by class × size; box bias ≈ 0 |
| 9 | Freeze detector | record `best.pt` SHA in `decisions_log.md` | |
| 10 | Cache detections | `python scripts/cache_detections.py --weights <best.pt> --splits train val` (test only in Week 5) | one `.npz` + `.json` per clip |
| 11 | Event yield, full dev | `python scripts/audit_labels.py --flights $(ls data \| grep ^dev_) --random 0 --out outputs/audit_full` | enough eligible val events per cell (≥ 40 total occlusion events) |

**Week 3 gate:** detector recall known by class and size; test set generated and
sealed; no flight crosses partitions (`make_design.py --check`, guards).

## Rough time (*measure* on the pilot)

Toy scenario + truth: about 20 s per flight here. Gazebo render: unknown; if about
1 min per flight, all 108 flights take under 2 h. Detector training at 1280 px on
one 8–16 GB GPU: a few hours per run.
