"""Low-poly dairy cow with rig (ready-made asset, only color and scale adjusted).

SOURCE: Quaternius, "LowPoly Animated Farm Animal Pack" (Cow.fbx), CC0 1.0, commercial use without attribution.
https://opengameart.org/content/lowpoly-animated-farm-animal-pack (copy in assets/quaternius/farm-animals/, see
SOURCE.txt). 796 triangles, 3 materials (White, Black, Pink). Actions: Idle, Walk, WalkSlow, Run, Jump, Death
(none for eating: grazing is an added pose layer that lowers neck and head and chews).
Proportions: adult Holstein ~2.4 m long, ~1.4 m at the withers (docs/blender/model-references.md).

Usage: build(name, location, heading, length) -> rigs.py rig; graze(rig, f0, f1) turns on the Idle + head in the grass.
"""

import math

from mathutils import Quaternion

import rigs

rigs.SPECS.setdefault("cow", "quaternius/farm-animals/Farm Animals by @Quaternius/FBX/Cow.fbx")

# Holstein: off-white and almost black patches; muzzle and udder in a pink more muted than the asset's pink
COLORS = {"White": "#E8E4DA", "Black": "#2A2622", "Pink": "#C9958A"}


def build(name, location, heading=0.0, length=2.3, colors=None):
    """Cow of 'length' meters (muzzle to tail) at the given position; heading in radians (0 = facing +x)."""
    cow = rigs.spawn("cow", name, length=length, location=location, heading=heading)
    rigs.paint(cow, colors or COLORS)
    return cow


def _graze_pose(cow, down_deg, chew_deg):
    """Neck and head low (eating from the ground) + chewing (the head sways slightly)."""
    q = {}
    q["Neck"] = rigs.bone_delta(cow, "Neck", (1, 0, 0), down_deg)
    q["Head"] = rigs.bone_delta(cow, "Head", (1, 0, 0), 0.45 * down_deg + chew_deg)
    return q


def graze(cow, f0, f1, down_deg=50.0, rate=0.6):
    """Slow Idle of the asset (breathing, tail) and, on top, low neck with the head chewing (~1.1 chews/s).
    Keys on every 2nd frame, LINEAR."""
    rigs.loop(cow, "Idle", f0 - 40, f1 + 40, rate=rate)
    frames = list(range(f0 - 2, f1 + 3, 2))
    rigs.pose_layer(cow, frames, lambda f: _graze_pose(cow, down_deg, 4.0 * math.sin(2 * math.pi * 1.1 * f / 30)))
    return cow
