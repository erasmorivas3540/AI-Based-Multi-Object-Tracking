# Decisions log

Every protocol, design or threshold decision, with the reason and date. Changes
after the Week 3 freeze must also say what was rerun.

Status key: **adopted** (in the code now), **advisor** (adopted provisionally;
confirm with advisor), **open** (not yet decided).

| ID | Date | Decision | Why | Status |
|---|---|---|---|---|
| D1 | 2026-10-20 | Six-week schedule; scope cuts per `scope_6week.md` | time budget | adopted |
| D2 | 2026-10-23 | **Paired blur:** blur is applied after rendering to the same flight, so each rendered flight gives a blur and a no-blur clip | halves rendering; turns blur into a within-flight comparison (more statistical power); both clips share a split and a bootstrap unit | advisor |
| D3 | 2026-10-23 | **Dev seeds 6 per cell** (72 dev flights); test stays 3 per cell (36) | with 3 dev seeds, validation had ~24 occlusion events, too few to set a 95%-precision threshold; generation is automated, so the cost is rendering time | advisor |
| D4 | 2026-10-23 | **Validation gets its own layout** (train L0–L2, val L3, test L4–L5) | test layouts are unseen; validation must be too, or the threshold is tuned on an easier distribution | adopted |
| D5 | 2026-10-23 | **Scripted occluder panels on the line of sight**, slide-in/out 0.3 s, 3 slots per flight; 0 s level = **near-miss** panel | exact control of occlusion duration with a moving camera; near-miss keeps scenes comparable across levels. Synthetic look acknowledged as a limitation | advisor |
| D6 | 2026-10-23 | **Occlusion duration calibrated to achieved hidden time** (vis < 0.5), within 1 frame | pilot: nominal 2.0 s windows hid targets for ~2.3 s (slide-in/out), so every 2 s event exceeded the 2 s limit and was excluded | adopted |
| D7 | 2026-10-23 | **Composite primitive target shapes** (quadrotor, car built from boxes), shared by Gazebo, toy renderer and labels | analytic labels become pixel-tight and checkable against Gazebo's own boxes; cuboid labels would be loose for quadrotors. Realism lower than Fuel meshes; can upgrade later with Gazebo boxes as labels | advisor |
| D8 | 2026-10-23 | **UAV observer closer** (stand-off 20 m, area ±10 m) | pilot: UAVs were 6–9 px; now median √area ≈ 14 px | adopted |
| D9 | 2026-10-23 | **Strict event scoring:** any wrong id in the restore + hold windows fails the event | matches plan §16 wording ("a wrong association during this interval fails the event") | advisor |
| D10 | 2026-10-23 | Crossing-caused events stay in the primary set, tagged by cause | they are genuine disappearances inside the field of view; tag allows a stratified report | open |
| D11 | 2026-10-23 | Detector imgsz chosen from {960, 1280} on val; init `yolo11s.pt` | UAVs halve in size at 640 | open (Week 3) |
| D12 | 2026-10-23 | "Raw" cache = conf ≥ 0.01 with NMS IoU 0.95 (approximate pre-NMS) | Ultralytics doesn't expose head outputs before NMS | adopted |
| D13 | 2026-10-23 | Dataset generation talks to Gazebo directly (gz-transport), lockstep one physics step per frame; ROS 2 only for the live pipeline | deterministic frames regardless of render speed; fewer moving parts | adopted |
| D14 | — | License for the repository | Ultralytics is AGPL-3.0 | open |

## Test-manifest reseals

| Date | New hash (prefix) | Reason |
|---|---|---|
| 2026-10-23 | `8e4fd017` | first seal after D4 |
| 2026-10-23 | `7eed7939` | D6 added `occlusion.calibrate_vis_threshold` to the config (pilot phase, before freeze) |

## Freeze record (fill in at the end of Week 3)

| File | SHA-256 | Date |
|---|---|---|
| configs/scenario_design.yaml | | |
| configs/event_protocol.yaml | | |
| configs/detector.yaml | | |
| manifests/test_manifest.sha256 | | |
| manifests/test_data_seal.json | | |
| detector weights (best.pt) | | |
