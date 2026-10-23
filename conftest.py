"""pytest: make src/ packages importable without a colcon build."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for pkg in sorted((ROOT / "src").glob("tracking_*")):
    sys.path.insert(0, str(pkg))
sys.path.insert(0, str(ROOT / "scripts"))
