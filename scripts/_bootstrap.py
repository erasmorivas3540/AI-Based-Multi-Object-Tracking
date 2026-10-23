"""Make the src/ packages importable when running scripts without a colcon build."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for pkg in sorted((ROOT / "src").glob("tracking_*")):
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))


def load_yaml(path):
    import yaml
    return yaml.safe_load(Path(path).read_text())
