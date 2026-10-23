# Version inventory

Fill in only after the component actually works. This becomes the reproducibility
record for every runtime claim.

## Hardware

| Item | Value |
|---|---|
| Machine / owner | |
| CPU | |
| GPU + VRAM | |
| System RAM | |
| Free storage | |
| NVIDIA driver | |

## Software

| Component | Version | How installed | Verified (date) |
|---|---|---|---|
| Ubuntu | 24.04 | | |
| ROS 2 | Jazzy | | |
| RMW implementation | | | |
| Gazebo | Harmonic (gz-sim 8.x) | | |
| ros_gz / ros_gz_bridge | | | |
| Python | | | |
| PyTorch | | | |
| CUDA (torch build) | | | |
| Ultralytics | | | |
| Detector checkpoint | | | |
| ByteTrack implementation (repo + commit) | | | |
| BoT-SORT implementation (repo + commit) | | | |
| TrackEval (commit) | | | |
| OpenCV | | | |
| NumPy / SciPy / scikit-learn | | | |

## Smoke-test log

| Date | Step | Result | Notes |
|---|---|---|---|
| | 1 ROS | | |
| | 2 Gazebo | | |
| | 3 Bridge | | |
| | 4 GPU + detector | | |
| | 5 Node: detect → track → publish | | |
| | 6 Bag record/replay | | |
| | 7 Known-answer eval | | |
| | End to end | | |

## Development environment where Weeks 2–3 code was tested (not your machine)

Cloud Linux container, Ubuntu 24.04, Python 3.13, CPU only, **no ROS 2 / Gazebo**
(package servers unreachable there). Use this only to reproduce the offline tests.

| Component | Version |
|---|---|
| numpy / scipy / shapely | 2.5.4 / 1.18.1 / 2.2.0 |
| opencv-python-headless / PyYAML | 5.0.0 / 6.0.3 |
| torch / ultralytics | 2.14.1+cu130 (run on CPU) / 8.4.184 |
| TrackEval | commit 12c8791 (+ NumPy alias shim) |

Checks run there (2026-10-23): 43 pytest tests; 12-flight toy pilot built,
audited and scored with reference trackers; YOLO export → 3-epoch CPU fine-tune of
yolo11n → detection cache → evaluation from cache (pipeline check only, not results).
