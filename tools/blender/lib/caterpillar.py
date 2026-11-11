"""Low-poly spongy moth (Lymantria dispar) caterpillar, with a wave crawl (peristalsis).

SOURCE: procedural (Ifscape, viruses-disappeared, 2026-10-24).
Proportions and colors (https://www.ontario.ca/page/lymantria-dispar-dispar-LDD-moth; direction.md §4; art.md §2):
mature at ~50 mm, dark gray body #4A4038, 5 pairs of BLUE dots (#3E5CB0) behind the head and then 6 pairs of
RED ones (#B83A2E), tufts of long hair on the sides, yellowish head. Low-poly reference: Quaternius "ring-segmented"
caterpillars (Ultimate Monsters/Animals): fat rings, cone tufts.

Crawl: contraction wave from the tail to the head (each ring stays PLANTED on the ground and only moves when the wave passes,
lifting a little). 8 shape keys = 8 phases of the wave; the root moves in a line at speed d / period, and the
key cancels the advance (x' = x + dx(phase) - d*phase), so no ring skates.

Usage:
    mats = materials()
    meshes = phase_meshes("Cat", mats, groups=4)        # 4 meshes = 4 out-of-sync phases
    o = instance("Cat1", meshes[k])                      # object; local: x = front (head), z = back
    crawl_keys(meshes, f0, f1)                            # animates the shape keys of all the meshes
    key_path(o, frames, frame_fn)                         # frame_fn(f) -> Matrix 4x4 (loc + orientation)
SPEED = meters per second of the root's advance (d / period).
"""

import math

import bpy
from mathutils import Matrix, Vector

import kit

LENGTH = 0.052          # 50-55 mm
RADIUS = 0.0046         # half width of the body
STEP = 0.010            # advance per wave (m)
PERIOD = 22             # frames per wave
SPEED = STEP * 30.0 / PERIOD       # ~1.4 cm/s
N_KEYS = 8

BODY, HEAD, BLUE, RED, HAIR, BELLY = range(6)
COLORS = {BODY: "#4A4038", HEAD: "#A88A4E", BLUE: "#3E5CB0", RED: "#B83A2E", HAIR: "#A8987E", BELLY: "#6A5E50"}


def materials():
    out = []
    for k in range(6):
        m = kit.flat(f"Cat_{k}", COLORS[k], rough=0.95)
        kit.principled(m).inputs["Specular IOR Level"].default_value = 0.0
        out.append(m)
    return out


def _ring(x, r, n=8, zc=None):
    """Body ring at x: flattened belly (resting at z ~ 0), round back."""
    zc = 0.62 * r if zc is None else zc
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n - math.pi / 2          # i = 0 at the bottom
        y, z = math.cos(a) * r * 1.08, zc + math.sin(a) * r
        pts.append((x, y, max(z, 0.05 * r)))
    return pts


def _pyramid(base, tip, w):
    """Tuft: 3-sided pyramid (triangular base of radius w around 'base', apex at 'tip')."""
    b, t = Vector(base), Vector(tip)
    d = (t - b).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(ref).normalized()
    v = d.cross(u)
    vs = [tuple(b + (u * math.cos(a) + v * math.sin(a)) * w) for a in (0.0, 2.094, 4.189)] + [tuple(t)]
    return vs, [(0, 1, 3), (1, 2, 3), (2, 0, 3), (2, 1, 0)]


def body_geo(length=LENGTH, r=RADIUS):
    """Caterpillar mesh (tail at x = 0, head at x = length). Returns verts, faces, mat per face and the 'station'
    (rest x of the ring the vertex belongs to) per vertex."""
    head_len = 0.11 * length
    n_seg = 12                                         # 11 with dots + 1 tail
    seg = (length - head_len) / n_seg
    rings, ring_x = [], []
    # rounded tail
    rings.append(_ring(0.0, 0.45 * r))
    ring_x.append(0.0)
    centers = []
    for i in range(n_seg):
        x0 = seg * i
        R = r * (0.75 if i == 0 else 0.9 if i >= n_seg - 2 else 1.0)
        rings.append(_ring(x0 + seg * 0.5, R))
        ring_x.append(x0 + seg * 0.5)
        centers.append((x0 + seg * 0.5, R))
        rings.append(_ring(x0 + seg, R * 0.84))
        ring_x.append(x0 + seg)
    verts, faces, fm, station = [], [], [], []
    n = 8
    for ring, x in zip(rings, ring_x):
        verts += ring
        station += [x] * n
    for i in range(len(rings) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
            fm.append(BELLY if j in (0, 1, 7) else BODY)
    faces.append(tuple(range(n - 1, -1, -1)))
    fm.append(BODY)
    # head: larger yellowish capsule, slightly low
    xb = length - head_len
    hr = r * 0.95
    hrings = [_ring(xb + 0.002, hr * 0.85, zc=0.6 * r), _ring(xb + head_len * 0.5, hr, zc=0.58 * r),
              _ring(length - 0.0015, hr * 0.62, zc=0.5 * r)]
    base = len(verts)
    for k, ring in enumerate(hrings):
        verts += ring
        station += [xb + head_len * 0.5] * n
    for i in range(2):
        for j in range(n):
            a, b = base + i * n + j, base + i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
            fm.append(HEAD)
    faces.append(tuple(range(base, base + n)))
    fm.append(HEAD)
    faces.append(tuple(range(base + n - 1, base - 1, -1)))
    fm.append(HEAD)
    # dots (tubercles) and tufts: segments 1..11 from the tail; from the head backward: 5 blue, 6 red
    def add(geo, mat, st):
        v, f = geo
        b0 = len(verts)
        verts.extend(v)
        station.extend([st] * len(v))
        for face in f:
            faces.append(tuple(b0 + i for i in face))
            fm.append(mat)

    dots = centers[1:12]                               # 11 segments (0 is the tail)
    for k, (x, R) in enumerate(dots):
        from_head = len(dots) - 1 - k                  # 0 = right behind the head
        mat = BLUE if from_head < 5 else RED
        top = 0.62 * r + R * 0.93
        for s in (-1, 1):
            c = Vector((x, s * 0.36 * R, top))
            w = 0.0015
            add(([tuple(c + Vector(d) * w) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1))],
                 [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4)]), mat, x)
            # long side tuft (outward and slightly up) and short back tuft
            side = Vector((x, s * R * 1.0, 0.62 * r + 0.15 * R))
            add(_pyramid(side, side + Vector((0.0015 * s * 0 + 0.0008 * (k % 2), s * 0.0085, 0.0035)), 0.0011), HAIR, x)
            add(_pyramid(c, c + Vector((-0.001, s * 0.0028, 0.0045)), 0.0009), HAIR, x)
    # two long tufts pointing forward, behind the head
    xh = xb - 0.001
    for s in (-1, 1):
        b = Vector((xh, s * 0.5 * r, 0.62 * r + 0.8 * r))
        add(_pyramid(b, b + Vector((0.009, s * 0.004, 0.003)), 0.001), HAIR, xh)
    return verts, faces, fm, station


def _wave(x, s, phase, length, step=STEP, lift=0.55 * RADIUS):
    """Displacement (dx, dz) of the vertex at station s at phase (0..1) of the wave running from tail to head."""
    w = 0.24 * length
    c = -w + phase * (length + 2 * w)
    t = max(0.0, min(1.0, (c - s) / (2 * w) + 0.5))
    sm = t * t * (3 - 2 * t)
    dz = lift * math.sin(math.pi * t) if 0.0 < t < 1.0 else 0.0
    return step * sm - step * phase, dz


def make_mesh(name, mats, length=LENGTH):
    v, f, fm, station = body_geo(length)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    for m in mats:
        me.materials.append(m)
    for p, mi in zip(me.polygons, fm):
        p.material_index = mi
        p.use_smooth = False
    me.update()
    tmp = bpy.data.objects.new(name + "Tmp", me)
    bpy.context.collection.objects.link(tmp)
    tmp.shape_key_add(name="Basis", from_mix=False)
    for k in range(N_KEYS):
        sk = tmp.shape_key_add(name=f"W{k}", from_mix=False)
        sk.value = 1.0 if k == 0 else 0.0           # the new key is born with 1.0: without animation, it stays at rest
        ph = k / N_KEYS
        for i, (co, s) in enumerate(zip(v, station)):
            dx, dz = _wave(co[0], s, ph, length)
            sk.data[i].co = (co[0] + dx, co[1], co[2] + dz)
    bpy.data.objects.remove(tmp)
    return me


def phase_meshes(name, mats, groups=4, length=LENGTH):
    """One mesh (with the 8 keys) per phase group: caterpillars of the same group walk in step."""
    return [make_mesh(f"{name}{g}", mats, length) for g in range(groups)]


def crawl_keys(meshes, f0, f1, period=PERIOD):
    """Shape keys of each mesh: phase = g/len + (f - f0)/period; linear blend between the 2 neighboring keys."""
    import anim_curves as ac
    frames = list(range(f0, f1 + 1))
    for g, me in enumerate(meshes):
        vals = {k: [] for k in range(N_KEYS)}
        for f in frames:
            ph = (g / len(meshes) + (f - f0) / period) % 1.0
            x = ph * N_KEYS
            i = int(x) % N_KEYS
            fr = x - int(x)
            for k in range(N_KEYS):
                vals[k].append((1 - fr) if k == i else fr if k == (i + 1) % N_KEYS else 0.0)
        for k in range(N_KEYS):
            ac.write(me.shape_keys, f'key_blocks["W{k}"].value', 0, frames, vals[k])


def instance(name, mesh, matrix=None):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    if matrix is not None:
        o.matrix_world = matrix
    o.rotation_mode = "XYZ"
    return o


def frame_matrix(pos, forward, normal):
    """Matrix with x = front, z = back (surface normal), origin at the belly (tail)."""
    x = Vector(forward).normalized()
    z = Vector(normal)
    z = (z - x * z.dot(x)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(pos)
    return m


def key_path(o, frames, frame_fn):
    """Position and orientation on every frame of 'frames' (LINEAR): frame_fn(f) -> Matrix. Quaternion rotation
    with continuous sign (caterpillar upright on the trunk = Euler in gimbal lock: it spun 355° between keys)."""
    import anim_curves as ac
    o.rotation_mode = "QUATERNION"
    locs, rots = [], []
    prev = None
    for f in frames:
        m = frame_fn(f)
        q = m.to_quaternion()
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q
        locs.append(m.translation.copy())
        rots.append(q)
    for i in range(3):
        ac.write(o, "location", i, frames, [p[i] for p in locs])
    for i in range(4):
        ac.write(o, "rotation_quaternion", i, frames, [r[i] for r in rots])
