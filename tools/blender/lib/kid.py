"""Child (6 to 8 years old) from the Quaternius Man: same mesh and rig, child proportions via bone scale.

SOURCE: Quaternius "Man" (Poly Pizza, https://poly.pizza/m/HMnuH5geEG), CC0 1.0; see tools/blender/rigs.py.
Proportions (~7-year-old child, ~1.2 m): head ~1/6 of the height (adult ~1/7.5), narrow shoulders, short torso.
The asset's actions only animate bone rotation and position: bone scale is free for this.
Legs do not change (the foot is IK in the rig: shortening the thigh would only bend the knee).
"""

HEAD = 1.38      # bigger head
TORSO = 0.9       # narrower torso/shoulders (arms and head inherit: the head compensates below)


def childlike(rig, head=HEAD, torso=TORSO):
    """Applies the child proportions to the copy (object pose, not the armature's shared data)."""
    pb = rig.arm.pose.bones
    pb["Torso"].scale = (torso, torso, torso)
    pb["Head"].scale = (head / torso,) * 3
    return rig
