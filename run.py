"""Run from a source checkout, without installation or required dependencies."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path[:0] = [str(root / "src")] + [str(p / "src") for p in sorted((root / "vendor").iterdir()) if p.is_dir()]
from sixvolumes.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
