"""Step 4: PyTorch sees the GPU and a YOLO checkpoint runs on one image.

Needs no ROS or Gazebo, so it can be done in parallel with steps 1-3.

    pip install torch ultralytics opencv-python
    python scripts/smoke_test/04_check_gpu_detector.py [path/to/image.jpg]
"""
import sys
import time


def main() -> int:
    failed = False
    print("== Step 4: GPU + detector ==")

    try:
        import torch
    except ImportError:
        print("  [FAIL] PyTorch not installed")
        return 1
    print(f"  torch {torch.__version__}, CUDA build {torch.version.cuda}")
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  [PASS] GPU: {name} ({vram:.1f} GB VRAM)")
        device = 0
    else:
        print("  [FAIL] No CUDA GPU visible — detector training will be impractical")
        failed = True
        device = "cpu"

    try:
        import ultralytics
        from ultralytics import YOLO
    except ImportError:
        print("  [FAIL] ultralytics not installed")
        return 1
    print(f"  ultralytics {ultralytics.__version__}")

    # Smallest checkpoint just to prove the pipeline. The real model choice is a
    # Week 3 decision; record whichever weights you end up using.
    model = YOLO("yolo11n.pt")
    source = sys.argv[1] if len(sys.argv) > 1 else "https://ultralytics.com/images/bus.jpg"

    model.predict(source, device=device, verbose=False)  # warm-up
    t0 = time.perf_counter()
    result = model.predict(source, device=device, verbose=False)[0]
    ms = (time.perf_counter() - t0) * 1000

    n = len(result.boxes)
    print(f"  [{'PASS' if n else 'FAIL'}] {n} detections in {ms:.1f} ms (after warm-up)")
    classes = sorted({model.names[int(c)] for c in result.boxes.cls})
    print(f"  classes seen: {classes}")

    # Important for this project: COCO checkpoints have 'airplane' but no drone
    # class. Fine-tuning on UAV images will be required.
    has_uav = any("drone" in v.lower() or "uav" in v.lower() for v in model.names.values())
    print(f"  checkpoint has a drone/UAV class: {has_uav}")
    return 1 if failed or n == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
