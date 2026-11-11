"""Blender entry point for videos made from data only ('stage' field of the script), without <slug>.py.

Run by 'python -m ifscape blender scripts/<slug>.json' when tools/blender/<slug>.py does not exist.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
import kit  # noqa: E402

kit.run(build.build)
