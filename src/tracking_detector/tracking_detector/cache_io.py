"""Detection cache format (see scripts/cache_detections.py)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

KIND = {"raw": 0, "final": 1}


def save_cache(path: Path, arr: np.ndarray):
    """arr columns: frame (1-based), x1, y1, x2, y2 (original pixels), score, cls, kind."""
    arr = np.asarray(arr, float).reshape(-1, 8)
    np.savez_compressed(path, frame=arr[:, 0].astype(int), x1=arr[:, 1], y1=arr[:, 2], x2=arr[:, 3],
                        y2=arr[:, 4], score=arr[:, 5], cls=arr[:, 6].astype(int), kind=arr[:, 7].astype(int))


def load_cache(path: Path, kind: str = "final") -> dict:
    """{frame: [(x1, y1, x2, y2, score, cls), ...]}"""
    z = np.load(path)
    m = z["kind"] == KIND[kind]
    out = {}
    for row in zip(z["frame"][m], z["x1"][m], z["y1"][m], z["x2"][m], z["y2"][m], z["score"][m], z["cls"][m]):
        out.setdefault(int(row[0]), []).append((*map(float, row[1:6]), int(row[6])))
    return out
