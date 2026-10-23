"""Geometry conventions, scenario determinism and split integrity."""
import copy

import numpy as np
import pytest
import yaml

from conftest import ROOT
from tracking_sim.design import assert_not_test, check_design, config_checksum, make_design, seal_hash
from tracking_sim.geometry import Camera, look_at_angles, project_box, project_cam, rot_zyx, world_to_cam
from tracking_sim.scenario import Scenario, build_scenario
from tracking_sim.truth import compute_truth

CFG_TEXT = (ROOT / "configs/scenario_design.yaml").read_text()
CFG = yaml.safe_load(CFG_TEXT)
CAM = Camera(1280, 720, np.deg2rad(80))


def test_point_on_axis_projects_to_principal_point():
    pos = np.array([0.0, 0.0, 10.0])
    yaw, pitch = look_at_angles(pos, [30.0, 5.0, 0.0])
    uv = project_cam(world_to_cam(np.array([[30.0, 5.0, 0.0]]), pos, rot_zyx(yaw, pitch, 0)), CAM)
    assert np.allclose(uv[0], [640, 360], atol=1e-6)


def test_image_axes_follow_gazebo_convention():
    R = rot_zyx(0, 0, 0)
    pts = np.array([[10.0, -1.0, 0.0], [10.0, 0.0, 1.0]])  # right of camera, above camera
    uv = project_cam(world_to_cam(pts, np.zeros(3), R), CAM)
    assert uv[0, 0] > 640 and abs(uv[0, 1] - 360) < 1e-9   # right in world -> right in image
    assert uv[1, 1] < 360                                   # up in world -> up in image


def test_positive_pitch_looks_down():
    R = rot_zyx(0, np.deg2rad(30), 0)
    uv = project_cam(world_to_cam(np.array([[10.0, 0.0, -10 * np.tan(np.deg2rad(30))]]), np.zeros(3), R), CAM)
    assert np.allclose(uv[0], [640, 360])


def test_box_size_scales_inversely_with_distance():
    R = rot_zyx(0, 0, 0)
    a = project_box([10, 0, 0], [1, 1, 1], 0, np.zeros(3), R, CAM).full_box
    b = project_box([20, 0, 0], [1, 1, 1], 0, np.zeros(3), R, CAM).full_box
    # nearest face sets the extent: (x-0.5) depth
    assert (a[2] - a[0]) / (b[2] - b[0]) == pytest.approx(19.5 / 9.5, rel=1e-6)


def test_box_behind_camera_is_none():
    assert project_box([-10, 0, 0], [1, 1, 1], 0, np.zeros(3), rot_zyx(0, 0, 0), CAM) is None


def _clip(**kw):
    c = dict(flight_id="t", seed=11, camera_motion="turning", occlusion_s=1.0,
             target_group="uav", layout="L0", split="train")
    c.update(kw)
    return c


def test_scenario_is_deterministic(tmp_path):
    a = compute_truth(build_scenario(CFG, _clip()))
    sc = build_scenario(CFG, _clip())
    sc.save(tmp_path / "s")
    b = compute_truth(Scenario.load(tmp_path / "s"))
    assert a == b


def test_scheduled_occlusion_is_achieved():
    sc = build_scenario(CFG, _clip(occlusion_s=2.0))
    truth = compute_truth(sc)
    for s in sc.schedule:
        assert s["status"] == "scheduled"
        mid = int((s["t_start"] + 1.0) * 20)
        obj = next(o for o in truth[mid]["objects"] if o["id"] == s["target_id"])
        assert obj["vis"] == 0.0 and obj["occluded_by"].startswith("occluder")


def test_near_miss_control_does_not_occlude():
    sc = build_scenario(CFG, _clip(occlusion_s=0.0))
    truth = compute_truth(sc)
    for s in sc.schedule:
        f0, f1 = int(s["t_start"] * 20), int(s["t_end"] * 20)
        occl = [o["occluded_by"] for fr in truth[f0:f1] for o in fr["objects"] if o["id"] == s["target_id"]]
        assert not any(x and x.startswith(f"occluder_{s['slot']}") for x in occl)


def test_design_has_no_leakage_and_seal_detects_changes():
    d = make_design(CFG, config_checksum(CFG_TEXT))
    assert check_design(d, seal_hash(d)) == []
    d2 = copy.deepcopy(d)
    next(f for f in d2["flights"] if f["split"] == "test")["seed"] += 1
    assert "TEST MANIFEST CHANGED since it was sealed" in check_design(d2, seal_hash(d))
    d3 = copy.deepcopy(d)
    next(f for f in d3["flights"] if f["split"] == "val")["layout"] = "L4"
    assert any("layouts shared" in p for p in check_design(d3))


def test_committed_seal_matches_config():
    d = make_design(CFG, config_checksum(CFG_TEXT))
    sealed = (ROOT / "manifests/test_manifest.sha256").read_text().split()[0]
    assert seal_hash(d) == sealed, "config changed after sealing: rerun make_design.py --reseal and log it"


def test_training_guard_refuses_test():
    d = make_design(CFG, config_checksum(CFG_TEXT))
    with pytest.raises(PermissionError):
        assert_not_test(d["flights"], "detector training")


def test_occlusion_calibration_threshold_matches_protocol():
    proto = yaml.safe_load((ROOT / "configs/event_protocol.yaml").read_text())
    assert CFG["occlusion"]["calibrate_vis_threshold"] == proto["observability"]["vis_threshold"]


@pytest.mark.parametrize("dur", [1.0, 2.0])
def test_achieved_hidden_time_matches_nominal(dur):
    for seed in (3, 4):
        sc = build_scenario(CFG, _clip(occlusion_s=dur, seed=seed))
        for s in sc.schedule:
            assert abs(s["achieved_hidden_s"] - dur) <= 1 / 20 + 1e-9, s
