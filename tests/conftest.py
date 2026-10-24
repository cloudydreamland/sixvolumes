import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src")] + [str(p / "src") for p in (root / "vendor").iterdir() if p.is_dir()]
