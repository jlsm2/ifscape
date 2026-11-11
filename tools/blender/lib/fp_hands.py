"""First-person hand + forearm + sleeve cuff, positionable in the WORLD (resting on a tabletop, grabbing, digging).

SOURCE: procedural (geometry from tools/blender/cell_models.py, bacteria-disappeared, 2026-10-21: palm in sections,
4 fingers with 3 phalanges following the relaxed-hand curve, thumb, forearm and hollow sleeve cuff). No external asset.
Measurements: palm ~9 cm wide, fingers ~8 cm (docs/blender/model-references.md).
Only these change here: sleeve color (plain, no plaid, by parameter) and placement by vectors (wrist, fingers, palm).

Mesh axes: wrist at the origin, fingers along +y, palm facing +z, thumb along +x (right hand; side=-1 mirrors).
"""

from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

import cell_models as cm
import kit

SKIN = "#C8916A"          # = skin of the people in the square (plants-extinct COLORS[0]) and of the bacteria hand
PALM = "#DB9C7A"


def _mat(name, color):
    return bpy.data.materials.get(name) or kit.flat(name, color, rough=0.95)


def hand(name, side=1, skin=SKIN, palm=PALM, sleeve="#3E6A8C", sleeve_dark=None):
    """Hand object (side +1 right, -1 left). Plain sleeve in the 'sleeve' color (the plaid becomes 2 close tones)."""
    m = SimpleNamespace(skin=_mat(f"FPSkin{skin}", skin), palm=_mat(f"FPPalm{palm}", palm),
                        flannel=_mat(f"FPSleeve{sleeve}", sleeve),
                        flannel_dark=_mat(f"FPSleeveD{sleeve_dark or sleeve}", sleeve_dark or sleeve))
    for mat in (m.skin, m.palm, m.flannel, m.flannel_dark):
        p = kit.principled(mat)
        p.inputs["Specular IOR Level"].default_value = 0.1
    o = cm._hand_object(name, side, m)
    o.rotation_mode = "QUATERNION"
    return o


def frame_quat(fingers, palm, side=1):
    """Rotation taking the mesh axes to the world: +y -> 'fingers', +z -> 'palm' (palm normal).
    The palm is orthogonalized against the fingers. For the left (mirrored) hand the thumb stays at -x, the same."""
    y = Vector(fingers).normalized()
    z = Vector(palm)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_quaternion()


def place(obj, wrist, fingers, palm, frame=None):
    obj.location = Vector(wrist)
    obj.rotation_quaternion = frame_quat(fingers, palm)
    if frame is not None:
        obj.keyframe_insert("location", frame=frame)
        obj.keyframe_insert("rotation_quaternion", frame=frame)
