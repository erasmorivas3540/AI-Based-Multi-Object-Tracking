# data/ (not tracked by git)

Rendered images, rosbags, detection caches and model weights live here locally
or on lab storage. Git tracks only manifests and this file.

Every dataset version needs a manifest (in `docs/` or `configs/`) recording:
scenario seed, world/layout, target assets, camera settings, occlusion schedule,
blur setting, split (train / val / test), and annotation version.

Rule: whole flights are assigned to one split. Never split adjacent frames.
