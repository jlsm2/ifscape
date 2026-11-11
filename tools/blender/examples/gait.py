"""Gaits of bipeds and quadrupeds in pure Python (no bpy): phases, duty factor, stride from speed.

  py tools/blender/examples/gait.py      # prints the test: feet on the ground in each gait

Use in Blender: for each leg, foot_y(t) gives the foot position along the body direction (in world) and the
height; the IK (see walk_biped_ik.py) makes the leg follow. The foot stays PLANTED during stance and does not slide.

Phases (fraction of the cycle at which the leg TOUCHES the ground; Hildebrand; see docs/blender/scripted-animation.md):
- walk_lateral: lateral sequence (rear left -> front left -> rear right -> front
  right). That of slow-stepping mammals (elephant, cow). Duty 0.75.
- sauropod: lateral sequence in a "diagonal pair" (Lallensack & Falkingham 2022): the front foot touches 0.35 of the
  cycle after the rear one on the same side; there is always diagonal support. Duty 0.7.
- trot: diagonal pairs together; duty ~0.5 (at 0.4 there is an aerial phase).
- pace: same-side pairs together (camel, giraffe).
- gallop: transverse; duty ~0.35, with an aerial phase.
- biped_walk / biped_run: human; duty 0.6 walking and ~0.35 running.
"""
import math

G = 9.81

GAITS = {
    #               phases per leg (LH, LF, RH, RF) or (L, R)               duty
    "walk_lateral": ({"LH": 0.0, "LF": 0.25, "RH": 0.5, "RF": 0.75}, 0.75),
    "sauropod":     ({"LH": 0.0, "LF": 0.35, "RH": 0.5, "RF": 0.85}, 0.70),
    "trot":         ({"LH": 0.0, "RF": 0.0, "RH": 0.5, "LF": 0.5}, 0.50),
    "pace":         ({"LH": 0.0, "LF": 0.0, "RH": 0.5, "RF": 0.5}, 0.55),
    "gallop":       ({"LH": 0.0, "RH": 0.1, "LF": 0.5, "RF": 0.6}, 0.35),
    "biped_walk":   ({"L": 0.0, "R": 0.5}, 0.60),
    "biped_run":    ({"L": 0.0, "R": 0.5}, 0.35),
}


def froude(speed, hip_height):
    """Froude number v²/(g·h). Walking < ~0.5; above that the animal switches to trot/run."""
    return speed * speed / (G * hip_height)


def stride_length(speed, hip_height):
    """Stride (contact to contact of the SAME foot) from speed: λ/h = 2.3·Fr^0.3 (Alexander 1976)."""
    return hip_height * 2.3 * froude(speed, hip_height) ** 0.3


def cycle_seconds(speed, hip_height):
    return stride_length(speed, hip_height) / speed


def foot_y(t, speed, cycle, phase, duty, lift):
    """(foot displacement along the path in meters, foot height) at time t.
    Stance: the foot stays still. Swing: advances one stride with smoothstep and rises in an arc (sine).
    Mid-stance falls under the hip/shoulder of the leg (the leg's offset on the body drops out)."""
    stride = speed * cycle
    p = t / cycle - phase
    c, u = math.floor(p), p % 1.0
    y0 = stride * (duty / 2 + phase)
    if u < duty:
        return stride * c + y0, 0.0
    v = (u - duty) / (1 - duty)
    e = v * v * (3 - 2 * v)
    return stride * (c + e) + y0, lift * math.sin(math.pi * v)


def body_bob(t, cycle, amp, legs=2):
    """Rises and falls 'legs' times per cycle; lowest right after each contact (Williams' 'down')."""
    u = (t / cycle) % 1.0
    return -amp * 0.5 * (1 + math.cos(2 * math.pi * legs * (u - 0.1)))


def _test():
    hip = {"walk_lateral": 1.4, "sauropod": 4.0, "trot": 0.9, "pace": 1.6, "gallop": 0.9,
           "biped_walk": 0.92, "biped_run": 0.92}
    speed = {"walk_lateral": 1.2, "sauropod": 1.5, "trot": 3.0, "pace": 2.5, "gallop": 7.0,
             "biped_walk": 1.3, "biped_run": 3.5}
    for name, (phases, duty) in GAITS.items():
        v, h = speed[name], hip[name]
        cyc = cycle_seconds(v, h)
        down = []
        worst_slide = 0.0
        for k in range(400):
            t = cyc * k / 400
            n = 0
            for ph in phases.values():
                y, z = foot_y(t, v, cyc, ph, duty, 0.1)
                if z == 0.0:
                    n += 1
                    y2, z2 = foot_y(t + 1e-4, v, cyc, ph, duty, 0.1)
                    if z2 == 0.0:
                        worst_slide = max(worst_slide, abs(y2 - y))
            down.append(n)
        for ph in phases.values():                       # mid-stance: foot under the hip (body = v·t)
            t_mid = cyc * (ph + duty / 2 + 3)
            assert abs(foot_y(t_mid, v, cyc, ph, duty, 0.1)[0] - v * t_mid) < 1e-6, name
        print(f"{name:13s} v={v:4.1f} m/s Fr={froude(v, h):4.2f} stride={stride_length(v, h):5.2f} m "
              f"cycle={cyc:4.2f} s | feet on the ground: min {min(down)} max {max(down)} | slide {worst_slide:.1e} m")


if __name__ == "__main__":
    _test()
