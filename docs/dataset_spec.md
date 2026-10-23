# Dataset specification (Week 3 deliverable)

**Status:** draft from the toy-rendered pilot (12 flights). Re-check every number
marked *measure* on Gazebo frames before the freeze.
**Source of truth:** `configs/scenario_design.yaml` (factors, targets, observer,
occluders, layouts) and `manifests/design.json` (every flight, seed, split).

## 1. Design

| Factor | Levels | Definition |
|---|---|---|
| Camera motion | `low`, `turning` | Observer orbits the scene centre and aims at the smoothed target centroid, plus a yaw/pitch oscillation. Numeric ranges in the config; achieved values below. |
| Occlusion | 0, 1.0, 2.0 s | Scheduled occluder panel covering one target, three slots per flight (≈4.5, 9.5, 14.5 s). **0 s is a near-miss control:** the panel slides in beside the target and out again without covering it, so scenes look alike across levels. |
| Blur | `none`, `motion` (9 px) | Post-render linear motion blur along the frame's camera-motion direction. **Paired:** both levels come from the same rendered flight. |
| Target group | `uav`, `ground` | 3–8 quadrotors, or 3–8 cars, per flight. One group per flight. |

**Cells:** 2 motion × 3 occlusion × 2 groups = 12. Blur is within-flight.

| Partition | Seeds per cell | Flights | Clips (× 2 blur) | Layouts |
|---|---|---|---|---|
| train | 4 | 48 | 96 | L0, L1, L2 |
| val | 2 | 24 | 48 | L3 |
| test (sealed) | 3 | 36 | 72 | L4, L5 |
| **total** | | **108** | **216** | |

Changes from the 6-week scope (144 clips, 3 seeds everywhere), with reasons, are
in `docs/decisions_log.md` (D2, D3, D4).

### Achieved camera motion (pilot means; *measure* again on Gazebo flights)

| Group / profile | Median ang. rate | 95th pct ang. rate | Median speed | 95th pct accel. |
|---|---|---|---|---|
| uav / low | 4.6 °/s | 7.3 °/s | 1.5 m/s | 0 |
| uav / turning | 17.3 °/s | 37.1 °/s | 3.2 m/s | 1.7 m/s² |
| ground / low | 1.9 °/s | 4.1 °/s | 1.0 m/s | 0 |
| ground / turning | 14.1 °/s | 30.0 °/s | 6.2 m/s | 3.2 m/s² |

Every flight stores its own achieved values in `scenario.json → stats`.

### Target apparent size (pilot, visible boxes with vis ≥ 0.5)

| Group | √area p10 / p50 / p90 |
|---|---|
| uav | 10 / 14 / 23 px |
| ground | 34 / 48 / 69 px |

UAVs are small by design. Most fall in the 0–16 and 16–32 px detector size bins.
The detector's recall there is the "detection ceiling" for UAV recovery.

## 2. What a flight contains

```
data/<flight_id>/
  scenario.json / .npz   every pose of every object at every frame; schedule; achieved stats
  truth.jsonl            analytic labels, schema v2 (below)
  frames/000001.png      canonical un-blurred frames, 1280x720, lossless
  render.json            renderer ("gazebo" or "toy"), versions, timing
  world.sdf              Gazebo world (Gazebo flights only)
  gz_boxes.jsonl         Gazebo bounding-box camera output (Gazebo flights only)
```

Blurred frames are produced on the fly by `tracking_sim.frames.load_frame`, so
both blur clips of a flight share identical content.

**Toy frames are for pipeline testing only.** `render.json` records the renderer;
no toy flight may enter a reported result.

## 3. Truth schema (`truth.jsonl`, v2)

Line 1: `{"schema_version": 2, "clip": {...flight entry...}}`. Then one line per frame:

| Field | Meaning |
|---|---|
| `frame`, `t` | 1-based frame number; simulation time in seconds |
| `camera.pos_m`, `camera.ypr_rad` | observer pose (truth only; never an inference input) |
| `occluders_active` | occluder panels in the scene this frame |
| `objects[].id`, `cls` | persistent target identity (1..N), `uav` or `ground` |
| `full_box` | projected silhouette extent, unclipped (pixels, x1 y1 x2 y2) |
| `box` | silhouette clipped to the image |
| `visible_box` | bounds of the un-occluded visible part; null if fully hidden |
| `vis` | visible fraction of the in-image silhouette (0–1) |
| `in_image_frac` | fraction of the silhouette inside the image |
| `in_fov` | centre in front of the camera and inside the image, ≥ 50% in image |
| `occluded_by` | name of the object covering the most of it (`occluder_k`, `target_k`, `clutter_k`) |
| `depth_m`, `center_px`, `pos_m`, `yaw` | geometry for event construction and forecast analysis |

Silhouettes come from composite part shapes (`tracking_sim/shapes.py`). The same
parts build the Gazebo models and the toy renderer, so analytic boxes are
pixel-tight. Occlusion is computed in painter's order by object-centre depth.

## 4. Splits and sealing

- Whole flights belong to one split; both blur clips go with their flight.
- Seeds come from `SeedSequence(master_seed, partition, cell, k)`; there are no duplicates.
- Layouts are disjoint across train / val / test.
- `manifests/test_manifest.sha256` seals the test subset of the design.
  `make_design.py` refuses to change it without `--reseal`, and every reseal is logged.
- After the test flights are rendered (Week 3), `seal_test_data.py` fingerprints
  their files. `--verify` must pass before the held-out run.
- Detector export and training call `assert_not_test`, which refuses test flights.

## 5. Detector labels and classes

Class map: `0 = uav`, `1 = ground`. A training box is the `visible_box` of an
object with vis ≥ 0.3 and short side ≥ 4 px. Hidden objects are never labelled.
Every 4th frame is used, both blur variants included. Evaluation uses the
protocol's stricter "observable" rule (vis ≥ 0.5, side ≥ 6 px, in view), and
partly visible objects are ignored rather than scored.

## 6. Storage (*measure*)

- Toy pilot PNGs average 251 KB. Gazebo PNGs with shading and texture will be
  larger. Estimate 1–1.5 MB each and measure on the first Gazebo flight.
- At 1.2 MB × 400 frames × 108 flights ≈ **52 GB** canonical frames.
- Add about 10 GB for the YOLO export (every 4th frame, both blur variants, train + val).
- Detection caches are small (≈ 1–5 MB per clip).
- Plan for about 100 GB free. Raw uncompressed frames would be about 120 GB.

## 7. Event yield (pilot, 12 flights, toy-rendered)

84 eligible primary events across 12 flights. 22 of the 24 scheduled occlusions
qualified (the 12 near-miss slots are not occlusions by design). The other 62
events are natural occlusions (crossings, clutter, other targets). Gazebo flights
must reproduce this order of magnitude; rerun `audit_labels.py` and compare
`event_yield.csv`.
