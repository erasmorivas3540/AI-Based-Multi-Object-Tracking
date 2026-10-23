# Verifying the Gazebo path (do this first, on your machine)

`world_sdf.py` and `gz_render_flight.py` were written against the Gazebo Harmonic
APIs but could not be run where they were written. Gazebo isn't installable
there. Everything upstream (scenarios, truth, events) and downstream (audit,
export, evaluation) is tested. This is the one untested link. Budget about half
a day.

## Prerequisites

```bash
sudo apt install ros-jazzy-ros-gz        # pulls in Gazebo Harmonic
python3 -c "from gz.transport13 import Node; from gz.msgs10.pose_v_pb2 import Pose_V; print('ok')"
```
If the import fails, install `python3-gz-transport13 python3-gz-msgs10`. Use the
system Python (or a venv created with `--system-site-packages`) so these bindings
are visible.

## Step 1: build one pilot scenario (no Gazebo)

```bash
python scripts/build_flights.py --flights dev_uav_low_occ10_s0
```

## Step 2: open the world with the GUI and look

```bash
python -c "import sys; sys.path[:0]=['scripts','src/tracking_sim']; import _bootstrap, yaml
from tracking_sim.scenario import Scenario; from tracking_sim.world_sdf import write_world
cfg=yaml.safe_load(open('configs/scenario_design.yaml'))
write_world(Scenario.load('data/dev_uav_low_occ10_s0/scenario'), cfg, 'data/dev_uav_low_occ10_s0/world.sdf')"
gz sim data/dev_uav_low_occ10_s0/world.sdf
```
Check: the world loads without SDF errors in the terminal; quadrotors and panels
appear at frame-0 poses; the ground is coloured. In the GUI, *Image Display* on
`/observer/rgb` shows the camera view. `gz topic -l` lists `/observer/rgb`,
`/observer/boxes_visible`, `/observer/boxes_full`.

| If... | Likely cause / fix |
|---|---|
| bounding-box sensors rejected | check `<box_type>` spelling against `gz-sim/examples/worlds/boundingbox_camera.sdf` on your install |
| no box topics | the Label system needs the `gz-sim-label-system` plugin per target model (present); boxes report only labelled models |
| models fall | `<gravity>false</gravity>` must sit inside `<link>` |

## Step 3: render 40 frames headless

```bash
python scripts/gz_render_flight.py --flight dev_uav_low_occ10_s0 --max-frames 40
```
Check `data/dev_uav_low_occ10_s0/gz_server.log` if it times out.

| Symptom | Fix |
|---|---|
| `set_pose_vector failed` | confirm the service exists: `gz service -l \| grep set_pose`. If only `set_pose` exists, loop over poses with `/world/flight/set_pose` (msg Pose). |
| timeout waiting for `rgb` | rendering may need a GPU/EGL; try without `--headless-rendering` (add `--gui`), or check `nvidia-smi` |
| images lag poses by one frame | the audit (step 4) shows boxes offset along the motion direction; then pair image *k* with poses from frame *k−1* (adjust in the director loop) |
| stamps don't advance by 50 ms | physics `max_step_size` must equal 1/fps (the world sets it); check `render.json` and `gz_boxes.jsonl` `sim_ns` |

## Step 4: audit Gazebo against the analytic labels

```bash
python scripts/audit_labels.py --flights dev_uav_low_occ10_s0 --out outputs/audit_gz
```
- Open `outputs/audit_gz/*.png`: analytic boxes are coloured; Gazebo's boxes are magenta.
- The script prints *"Gazebo vs analytic visible boxes: median IoU …"*.
  **Gate:** median IoU ≥ 0.85 and fewer than 5% of boxes below 0.8 (on the first
  40 frames, then on a full flight).
- A constant offset suggests the principal point or image axis. A size mismatch
  suggests the field of view. An offset that grows with camera speed suggests
  pose/frame lag.

## Step 5: full pilot

```bash
for f in $(python -c "import json;print(' '.join(x['flight_id'] for x in json.load(open('manifests/design.json'))['flights'] if x['flight_id'].endswith('_s0') and x['partition']=='dev'))"); do
  python scripts/build_flights.py --flights $f && python scripts/gz_render_flight.py --flight $f
done
python scripts/audit_labels.py --flights $(ls data | grep '^dev_') --out outputs/audit_gz
```
Then do the manual audit: fill in `outputs/audit_gz/audit_log.csv` (about 140
frames, 30–45 minutes). Record the time per flight and the PNG size in
`docs/dataset_spec.md` §6.
