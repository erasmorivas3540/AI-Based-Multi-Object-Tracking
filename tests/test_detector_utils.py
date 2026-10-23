"""Resize inversion, NMS, matching, cache format and label rules."""
import numpy as np
import pytest

from tracking_detector.boxes import classwise_nms, from_letterbox, greedy_match, nms, to_letterbox
from tracking_detector.cache_io import load_cache, save_cache
from tracking_detector.labels import classify_object, yolo_line


@pytest.mark.parametrize("imgsz", [640, 960, 1280])
def test_letterbox_roundtrip(imgsz):
    boxes = np.array([[0, 0, 10, 10], [640, 360, 700, 380], [1200, 700, 1280, 720]], float)
    back = from_letterbox(to_letterbox(boxes, 720, 1280, imgsz), 720, 1280, imgsz)
    assert np.allclose(back, boxes, atol=1e-6)


def test_letterbox_pads_vertically_for_wide_images():
    b = to_letterbox([[0, 0, 1280, 720]], 720, 1280, 1280)[0]
    assert b[0] == 0 and b[2] == 1280 and b[1] == pytest.approx(280) and b[3] == pytest.approx(1000)


def test_nms_keeps_best_and_separate():
    boxes = [[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]]
    keep = nms(boxes, [0.9, 0.8, 0.7], 0.5)
    assert keep.tolist() == [0, 2]


def test_classwise_nms_does_not_suppress_across_classes():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11]], float)
    keep = classwise_nms(boxes, np.array([0.9, 0.8]), np.array([0, 1]), 0.5)
    assert sorted(keep.tolist()) == [0, 1]


def test_greedy_match_prefers_high_score_and_is_one_to_one():
    gt = [[0, 0, 10, 10]]
    dets = [[0, 0, 10, 10], [0, 0, 10, 9]]
    d2g, best = greedy_match(dets, [0.5, 0.9], gt, 0.5)
    assert d2g.tolist() == [-1, 0] and best[0] == pytest.approx(1.0)


def test_cache_roundtrip(tmp_path):
    arr = np.array([[1, 0, 0, 10, 10, 0.9, 0, 1], [1, 5, 5, 9, 9, 0.02, 1, 0], [3, 1, 2, 3, 4, 0.5, 1, 1]])
    save_cache(tmp_path / "c.npz", arr)
    final = load_cache(tmp_path / "c.npz", "final")
    raw = load_cache(tmp_path / "c.npz", "raw")
    assert sorted(final) == [1, 3] and final[3][0] == (1.0, 2.0, 3.0, 4.0, 0.5, 1)
    assert list(raw) == [1] and raw[1][0][5] == 1


def test_label_rules():
    o = {"visible_box": [10, 10, 40, 30], "vis": 0.8, "in_fov": True}
    assert classify_object(o, 0.5, 6) == "target"
    assert classify_object(o | {"vis": 0.3}, 0.5, 6) == "ignore"
    assert classify_object(o | {"visible_box": None}, 0.5, 6) == "absent"
    assert classify_object(o | {"visible_box": [10, 10, 14, 30]}, 0.5, 6) == "ignore"
    assert yolo_line(o, 1, 100, 100) == "1 0.250000 0.200000 0.300000 0.200000"
