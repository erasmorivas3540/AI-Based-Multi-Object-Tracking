<!-- Text of AI_Object_Tracking_Concise_Plan.docx (16 October 2026), the original 12-week plan. The 6-week scope that supersedes its schedule is docs/scope_6week.md. -->

# AI-Augmented Object Tracking

Concise research plan • 12 weeks • Proposal, not results

## Objective

Build a real-time system that detects drones and vehicles, preserves their identities through temporary occlusion, and forecasts positions 0.5 and 1.0 seconds ahead in the camera image.

## Original research focus

Test whether a small, calibrated recovery model improves identity restoration using motion consistency, camera-motion quality, blur and confidence history. Build on ByteTrack and recent aerial-tracking research; confirm the specific novelty in week 1. Compare with native ByteTrack, BoT-SORT, TrackTrack and a matched hand-designed recovery rule.

## Method and scope

Use Robot Operating System 2 (ROS 2), Gazebo simulation, OpenCV, PyTorch and a YOLO-family detector. Freeze detector inputs for controlled comparisons. Generate approximately 320 clips, split by flight: 120 training, 40 validation and 160 held-out test. Vary camera motion, occlusion duration, blur and target type. Start with one observer and 3–8 targets; demonstrate two independent observer streams.

| **Weeks** | **Main work** |
| --- | --- |
| 1–2 | Audit research; validate software, simulation and labels. |
| 3–4 | Freeze data protocol; train and freeze the detector. |
| 5–6 | Reproduce baselines; train and calibrate recovery. |
| 7–8 | Integrate ROS 2 outputs and short trajectory forecasts. |
| 9–10 | Freeze experiments; run held-out and runtime evaluation. |
| 11–12 | Analyze failures; deliver code, evidence and report. |

## Evaluation and deliverables

Primary outcome: higher recovery recall at an operating point targeting at least 95% precision, with paired flight-level confidence intervals. Also measure identity accuracy, forecast error and latency. Prospective runtime targets: 20 frames/second per observer and under 100 milliseconds at the 95th percentile on a declared workstation.

Deliver reproducible simulation data and manifests, baseline comparisons, learned recovery code, a ROS 2 prototype, evaluation plots and a research report. Assumes one researcher, 15–20 hours/week and an existing GPU workstation. Outputs are camera-local and image-plane; metric separation, shared cross-camera identities and flight control require further work.

Research basis: ByteTrack (2022), DroneMOT (2024), TrackTrack (2025), and recent 2025–2026 aerial-tracking work. Full sources, definitions, assumptions and acceptance gates are in the detailed companion plan.

Research proposal • 16 October 2026
