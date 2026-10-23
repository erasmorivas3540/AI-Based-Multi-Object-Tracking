# Week 1 smoke test

Prove each link on its own before chaining them. Commit a one-line note to
`docs/versions.md` after each step passes.

| Step | Script | Proves | Needs ROS? |
|---|---|---|---|
| 1 | `01_check_ros.sh` | Ubuntu 24.04 + ROS 2 Jazzy pass a message | yes |
| 2 | `02_check_gazebo.sh` | Gazebo Harmonic runs, a camera publishes | no (Gazebo only) |
| 3 | `03_check_bridge.sh` | Camera images reach a ROS 2 topic | yes |
| 4 | `04_check_gpu_detector.py` | GPU visible, YOLO runs on an image | no |
| 5 | *(you write)* | rclpy node: image → detector → ByteTrack → publish | yes |
| 6 | `ros2 bag record` / `play` | Record and replay a short bag | yes |
| 7 | `tests/known_answer/` | TrackEval counts a planted ID switch | no |

**Week 1 exit gate:** steps 1–7 pass individually, then once end to end.

Steps 4 and 7 have no ROS dependency, so do them first if installation is slow.

### Step 5 hint

Keep it tiny: one rclpy node that subscribes to the bridged image, converts it
with `cv_bridge`, runs the detector, feeds boxes to a ByteTrack implementation,
and publishes something (even a `std_msgs/String` of track IDs) with the source
image timestamp. Proper message types come in Week 2.

Ultralytics ships a ByteTrack config (`model.track(..., tracker="bytetrack.yaml")`),
which is fine for the smoke test. For the experiments you'll want a pinned
ByteTrack implementation whose lost-track logic you can read and modify — note
which one you pick in `docs/versions.md`.

### Common failure points

- **WSL2:** Gazebo GUI and GPU rendering need WSLg and recent drivers; expect friction.
- **Headless cameras:** camera sensors need a renderer even with `-s`.
- **Bridge topic names:** check `gz topic -l` vs `ros2 topic list`; they must match the mapping.
- **Image encoding:** confirm RGB vs BGR before feeding the detector.
