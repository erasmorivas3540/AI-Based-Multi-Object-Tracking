# src/ — ROS 2 workspace

Build from the repository root:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Packages are added only when the schedule needs them:

| Package | Purpose | Week |
|---|---|---|
| tracking_interfaces | TrackArray, ForecastArray, diagnostics messages | 1–2 |
| tracking_sim | Gazebo worlds, target paths, annotation export | 1–2 |
| tracking_detector | YOLO wrapper, class mapping, resize inversion | 3 |
| tracking_core | Track state, association, recovery interface | 4 |
| tracking_recovery | Features, logistic regression, calibration | 4 |
| tracking_prediction | Constant-velocity Kalman forecasts | 5 |
| tracking_evaluation | TrackEval adapter, recovery events, statistics | 2–6 |
| tracking_bringup | Launch files, namespaces, recording | 5 |

Keep algorithms importable without ROS so offline evaluation and live runs share
the same code.
