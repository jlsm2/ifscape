"""Simple 2D simulation of the cars when the drivers vanish (pure Python, testable outside Blender).

Each car is a rigid body approximated by 3 circles along its length. Before the vanishing,
the car follows the lane (and may be braking for the light). After, it rolls by inertia with a slight
steering drift; collisions exchange impulse, spin the car and leave it skidding to a stop.
Heading in radians in the Blender standard: z rotation, with the front of the car at local +y.
"""

import math
from dataclasses import dataclass, field

FPS = 30
SUBSTEPS = 6
CIRCLE_OFFSETS = (-1.7, -0.57, 0.57, 1.7)   # 4 circles cover the car rectangle (1.9 x 4.4 m)
CIRCLE_R = 0.97
CAR_HALF = (0.95, 2.2)
BOX_GAP = 0.15                            # minimum gap between bodies after collisions (m)
RESTITUTION = 0.25
SKID_FRICTION = 7.0        # m/s^2 skidding sideways
SPIN_DAMPING = 2.5
REFERENCE_VANISH = 2.6     # second of the vanishing for which the initial positions were tuned


@dataclass
class Car:
    name: str
    x: float
    y: float
    heading: float             # z rotation (0 = moving toward +y)
    speed: float
    vanish_t: float            # second when the driver vanishes
    coast: float = 1.4         # deceleration by inertia after the vanishing (m/s^2)
    steer: float = 0.0         # steering drift after the vanishing (rad/s)
    stop_at: float | None = None   # before the vanishing: stops at this distance (red light)
    vx: float = 0.0
    vy: float = 0.0
    spin: float = 0.0
    skidding: bool = False
    track: list = field(default_factory=list)


@dataclass
class Obstacle:
    name: str
    x: float
    y: float
    r: float


def forward(h: float) -> tuple[float, float]:
    return -math.sin(h), math.cos(h)


def circles(c: Car):
    fx, fy = forward(c.heading)
    return [(c.x + fx * o, c.y + fy * o) for o in CIRCLE_OFFSETS]


def simulate(cars: list[Car], obstacles: list[Obstacle], seconds: float):
    """Returns (tracks per car: list of (x, y, heading) per frame, collision events)."""
    for c in cars:
        fx, fy = forward(c.heading)
        c.vx, c.vy = fx * c.speed, fy * c.speed
        c.track = []
    events, hit_pairs = [], set()
    dt = 1 / FPS / SUBSTEPS
    frames = int(seconds * FPS)
    for frame in range(frames):
        for c in cars:
            c.track.append((c.x, c.y, c.heading))
        for sub in range(SUBSTEPS):
            t = (frame * SUBSTEPS + sub) * dt
            for c in cars:
                _drive(c, t, dt)
            _collide_cars(cars, frame, events, hit_pairs)
            _collide_static(cars, obstacles, frame, events, hit_pairs)
            _separate_boxes(cars)
    return {c.name: c.track for c in cars}, events


def _drive(c: Car, t: float, dt: float):
    speed = math.hypot(c.vx, c.vy)
    if c.skidding:
        if speed > 0:
            drop = min(speed, SKID_FRICTION * dt)
            c.vx -= c.vx / speed * drop
            c.vy -= c.vy / speed * drop
        c.spin -= c.spin * min(1.0, SPIN_DAMPING * dt)
        c.heading += c.spin * dt
    else:
        if t < c.vanish_t:
            accel = 0.0
            if c.stop_at is not None:
                dist = max(c.stop_at, 0.3)
                accel = -speed * speed / (2 * dist) if speed > 0.05 else 0.0
                c.stop_at -= speed * dt
        else:
            accel = -c.coast
            c.heading += c.steer * dt * min(1.0, speed / 4)
        speed = max(0.0, speed + accel * dt)
        fx, fy = forward(c.heading)
        c.vx, c.vy = fx * speed, fy * speed
    c.x += c.vx * dt
    c.y += c.vy * dt


def _collide_cars(cars, frame, events, hit_pairs):
    for i, a in enumerate(cars):
        for b in cars[i + 1:]:
            if abs(a.x - b.x) > 6 or abs(a.y - b.y) > 6:
                continue
            for ax, ay in circles(a):
                for bx, by in circles(b):
                    dx, dy = bx - ax, by - ay
                    d = math.hypot(dx, dy)
                    if d >= 2 * CIRCLE_R or d == 0:
                        continue
                    nx, ny = dx / d, dy / d
                    rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                    overlap = 2 * CIRCLE_R - d
                    a.x -= nx * overlap / 2; a.y -= ny * overlap / 2
                    b.x += nx * overlap / 2; b.y += ny * overlap / 2
                    if rel >= 0:
                        continue
                    j = -(1 + RESTITUTION) * rel / 2
                    a.vx -= j * nx; a.vy -= j * ny
                    b.vx += j * nx; b.vy += j * ny
                    # Spin: a collision far from the center spins more.
                    for car, (cx, cy), sign in ((a, (ax, ay), -1), (b, (bx, by), 1)):
                        rx, ry = cx - car.x, cy - car.y
                        car.spin += sign * (rx * ny - ry * nx) * j * 0.35
                        car.skidding = True
                    key = (a.name, b.name)
                    if key not in hit_pairs or j > 3:
                        hit_pairs.add(key)
                        events.append({"frame": frame, "x": (ax + bx) / 2, "y": (ay + by) / 2,
                                       "cars": key, "force": j})


def _separate_boxes(cars):
    """Final correction by the rectangles: the circles leave gaps at the corners, here no car ends up inside another."""
    for i, a in enumerate(cars):
        for b in cars[i + 1:]:
            if abs(a.x - b.x) > 6 or abs(a.y - b.y) > 6:
                continue
            # BOX_GAP clearance between bodies: touching exactly in 2D still left, in 3D (wheels, corners
            # and keys every 2 frames), one car entering another (QA of 2026-10-20).
            m = BOX_GAP / 2
            d = penetration(corners(a.x, a.y, a.heading, margin=m), corners(b.x, b.y, b.heading, margin=m))
            if d <= 0:
                continue
            dx, dy = b.x - a.x, b.y - a.y
            n = math.hypot(dx, dy) or 1.0
            push = (d + 0.02) / 2
            a.x -= dx / n * push; a.y -= dy / n * push
            b.x += dx / n * push; b.y += dy / n * push


def _collide_static(cars, obstacles, frame, events, hit_pairs):
    for c in cars:
        for o in obstacles:
            if abs(c.x - o.x) > 4 or abs(c.y - o.y) > 4:
                continue
            for cx, cy in circles(c):
                dx, dy = o.x - cx, o.y - cy
                d = math.hypot(dx, dy)
                if d >= CIRCLE_R + o.r or d == 0:
                    continue
                nx, ny = dx / d, dy / d
                overlap = CIRCLE_R + o.r - d
                c.x -= nx * overlap; c.y -= ny * overlap
                rel = c.vx * nx + c.vy * ny
                if rel <= 0:
                    continue
                c.vx -= (1 + 0.1) * rel * nx
                c.vy -= (1 + 0.1) * rel * ny
                rx, ry = cx - c.x, cy - c.y
                c.spin += (rx * ny - ry * nx) * rel * 0.25
                c.skidding = True
                key = (c.name, o.name)
                if key not in hit_pairs:
                    hit_pairs.add(key)
                    events.append({"frame": frame, "x": cx + nx * CIRCLE_R, "y": cy + ny * CIRCLE_R,
                                   "cars": key, "force": rel})


def corners(x, y, h, half=CAR_HALF, margin=0.0):
    hx, hy = half[0] + margin, half[1] + margin
    c, s = math.cos(h), math.sin(h)
    return [(x + c * dx - s * dy, y + s * dx + c * dy) for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]


def penetration(a, b):
    """Separating axis test between two rectangles (lists of corners). Returns how much they overlap (0 = none)."""
    best = float("inf")
    for poly in (a, b):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            nx, ny = y1 - y2, x2 - x1
            length = math.hypot(nx, ny)
            nx, ny = nx / length, ny / length
            pa = [px * nx + py * ny for px, py in a]
            pb = [px * nx + py * ny for px, py in b]
            overlap = min(max(pa), max(pb)) - max(min(pa), min(pb))
            if overlap <= 0:
                return 0.0
            best = min(best, overlap)
    return best


def audit(tracks: dict, tolerance: float = 0.05):
    """Pairs of cars with overlapping bodies: returns {pair: (worst overlap, frame)}."""
    names = list(tracks)
    worst = {}
    frames = len(next(iter(tracks.values())))
    for f in range(frames):
        boxes = {n: corners(*tracks[n][f]) for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pa, pb = tracks[a][f], tracks[b][f]
                if abs(pa[0] - pb[0]) > 6 or abs(pa[1] - pb[1]) > 6:
                    continue
                d = penetration(boxes[a], boxes[b])
                if d > tolerance and d > worst.get((a, b), (0, 0))[0]:
                    worst[(a, b)] = (d, f)
    return worst


def scenario(vanish_t: float) -> tuple[list[Car], list[Obstacle]]:
    """The cars at the corner. NB = north (+y), SB = south, EB = east (+x), WB = west."""
    north, south, east, west = 0.0, math.pi, -math.pi / 2, math.pi / 2
    v = vanish_t
    cars = [
        # Queue stopped at the red (inner NB lane) and a fast car behind: chain rear-end collision.
        Car("nb_red", 1.8, -12.0, north, 7.0, v + 0.1, coast=3.0, stop_at=5.0),
        Car("nb_fast", 1.8, -46.0, north, 13.0, v + 0.2, coast=0.4),
        # Outer NB lane: drifts to the right and hits the hydrant.
        Car("nb_drift", 5.2, -48.0, north, 11.0, v, coast=0.6, steer=-0.4),
        # Crossing the intersection to the east when everything happens: side collision.
        Car("eb_cross", -40.0, -2.5, east, 11.5, v + 0.15, coast=0.5),
        Car("wb", 46.0, 2.5, west, 10.0, v + 0.05, coast=1.2, steer=0.05),
        Car("sb_in", -1.8, 44.0, south, 10.0, v + 0.25, coast=1.6, steer=0.04),
        Car("sb_out", -5.2, 30.0, south, 8.0, v, coast=2.0, steer=0.08),
        Car("sb_far", -1.8, 70.0, south, 11.0, v + 0.1, coast=1.0),
        Car("nb_far", 5.2, -70.0, north, 12.0, v + 0.2, coast=0.9, steer=0.03),
    ]
    # The positions above were tuned for the vanishing at 2.6 s. If it comes earlier (opening with the vanishing
    # within the first second), the moving cars start ahead by the same amount; the fast car
    # behind stays a bit farther back so the collision happens after the driver vanishes.
    lead = max(0.0, REFERENCE_VANISH - vanish_t)
    for c in cars:
        if c.stop_at is None:
            fx, fy = forward(c.heading)
            c.x += fx * c.speed * lead
            c.y += fy * c.speed * lead
        if c.name == "nb_fast":
            c.y -= 6.0 * lead / 1.8
    obstacles = [Obstacle("hydrant", 7.7, -7.0, 0.25), Obstacle("streetlight", -7.6, -10.0, 0.2),
                 Obstacle("traffic_pole", -7.7, 5.7, 0.2)]
    return cars, obstacles


if __name__ == "__main__":
    cars, obstacles = scenario(0.8)
    tracks, events = simulate(cars, obstacles, 12.0)
    for e in events:
        print(f"t={e['frame'] / FPS:5.2f}s  {e['cars']}  force {e['force']:.1f}  at ({e['x']:.1f}, {e['y']:.1f})")
    bad = audit(tracks)
    print("overlaps:", {k: (round(v[0], 2), round(v[1] / FPS, 2)) for k, v in bad.items()} or "none")
    for name, tr in tracks.items():
        x, y, h = tr[-1]
        print(f"{name:10s} ends at ({x:6.1f}, {y:6.1f}) heading {math.degrees(h):6.1f}")
