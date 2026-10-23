"""Reproducibility record attached to every experiment output (plan section 11)."""
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ROOT


def sha256_file(path, n=16):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def git_state():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
        return {"commit": commit or None, "dirty": dirty}
    except FileNotFoundError:
        return {"commit": None, "dirty": None}


def run_record(**extra):
    rec = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git": git_state(),
           "python": platform.python_version(), "host": platform.node(), "platform": platform.platform()}
    try:
        import torch
        rec["torch"] = torch.__version__
        rec["cuda"] = torch.version.cuda
        rec["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except ImportError:
        pass
    try:
        import ultralytics
        rec["ultralytics"] = ultralytics.__version__
    except ImportError:
        pass
    rec.update(extra)
    return rec


def write_record(path, **extra):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(run_record(**extra), indent=1, default=str))
