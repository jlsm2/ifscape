"""2D stage with camera: the 'wide' shot (the real scene in side view, full-body characters) and the base
of the 'close' and 'duo' framings (close.py, duo.py): the same figure (figure.py) in the same set (sets.py).

    {"shot": "wide", "set": "pharmacy" | "busstop" | "frontdoor",
     "actors": [{"id": "hale", "at": "outside", "facing": "left", "behind": false}], "events": [...]}

Gait calibrated by the planted foot (Walker): the hip moves and each foot stays STILL on the ground while planted;
only the foot in the air moves (sine arc). The number of steps comes from the distance (nominal step per style) and the
last step brings the feet together, so nothing skates. Styles: walk, run and the dragging step of the turned.

Actions: walk/run/move (who, to), recoil, grab (target), hand, talk, expr, knock (who, on: door|counter: fist
on the door or the counter + engine shake), drop (the key falls), lock (the hand turns the latch), light (shop
light), bite (who advances and leans over target's shoulder, gray ring pulse, no blood; triggers the target's
turn), turn (grayish skin, curved posture, dragging step) and heat (infected in the background: curved
dark silhouettes that walk slowly in the set's 'lane'), appear (the still shape behind the door).

Camera: the still background is cropped and enlarged (it gets soft, like depth of field); characters, objects and
silhouettes are redrawn at the zoom scale, so the close has the same sharp stroke as the wide. Silhouettes and
infected in the background go through a glass mask (sets.glass_mask): never in front of the frame or the grille.
The headlamp beam comes from whoever has 'headlamp' in every shot and follows the scene's light (on/off/flicker).
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import figure
from .acting import Acting
from .cast import look_for
from .common import AMB, AMB_D, FPS, H, P, S, VAC, W, WARM, clamp, font, lerp, mix, noise, smooth
from .places import PILLS_X, STAIRS_DOOR, WIDE_DOORS
from .sets import COUNTER, COUNTER_TOP, PH_COUNTER, SETS, glass_box, glass_mask
from .tracks import Track

K = 0.85                         # character scale (head at the top at y ~770 with the foot at 1240)
FOOT_W = 16                      # half the distance between the feet standing (px, with K)
GAITS = {                        # nominal step (px), height of the foot in the air, px/s, arm swing, lean
    "walk": (82, 16, 140, 0.42, 0.03),
    "run": (128, 34, 330, 0.95, 0.16),
    "shuffle": (44, 5, 55, 0.12, 0.0),
}
CLOSE_STEP = 0.22                # the last foot comes together with the other after arriving (s)
BITE_GAP = 150                   # attacker's hip to the target's in the bite (px, with K): the head lands on the shoulder
RING = (214, 218, 224)           # bite ring: grayish white, never red
RING_SECONDS = 0.7
INF_SIL = (6, 8, 12)
LIGHT_SECONDS = 0.25
APPEAR_SECONDS = 1.2
RECOIL_PX = 20
COUNTER_Y = 1080                 # top of the duo's counter, in the world (waist height)
_BG: dict = {}


def _bg(name: str, lit: bool) -> Image.Image:
    key = (name, lit)
    if key not in _BG:
        _BG[key] = SETS[name]["draw"](lit)
    return _BG[key]


class Segment:
    """A hip displacement from xa to xb between t0 and t1, with the steps already planned."""

    def __init__(self, t0: float, dur: float, xa: float, ya: float, xb: float, yb: float, feet: list, gait: str):
        self.t0, self.t1, self.gait = t0, t0 + dur, gait
        self.xa, self.ya, self.xb, self.yb = xa, ya, xb, yb
        self.D = abs(xb - xa)
        self.dirn = 1 if xb >= xa else -1
        stride, self.lift, _, self.arm, self.lean = GAITS[gait]
        stride *= K
        w = FOOT_W * K
        n = max(1, round(self.D / stride))
        self.d = self.D / n if self.D else 1.0
        self.feet0 = list(feet)
        pos = list(feet)
        rear = 0 if pos[0] * self.dirn <= pos[1] * self.dirn else 1
        self.steps = []                                # (foot, s from, s to, x from, x to)
        for k in range(1, n + 1):
            foot = rear if k % 2 else 1 - rear
            to = xa + self.dirn * (k * self.d + self.d / 2) if k < n else xb + self.dirn * w
            self.steps.append((foot, (k - 1) * self.d, k * self.d, pos[foot], to))
            pos[foot] = to
        other = 1 - self.steps[-1][0]
        self.closing = (other, pos[other], xb - self.dirn * w)
        pos[other] = xb - self.dirn * w
        self.feet1 = pos
        self.close_end = self.t1 + CLOSE_STEP

    def s_at(self, t: float) -> float:
        return self.D * smooth((t - self.t0) / (self.t1 - self.t0)) if self.t1 > self.t0 else self.D

    def state(self, t: float) -> dict:
        s = self.s_at(t) if t < self.t1 else self.D
        u = s / self.D if self.D else 1.0
        ground = lerp(self.ya, self.yb, u)
        feet = []
        for i in (0, 1):
            x, lift = self.feet0[i], 0.0
            for foot, s0, s1, xf, xt in self.steps:
                if foot != i or s < s0:
                    continue
                if s >= s1:
                    x = xt
                else:
                    v = (s - s0) / (s1 - s0)
                    x, lift = lerp(xf, xt, smooth(v)), self.lift * K * math.sin(math.pi * v)
            if i == self.closing[0] and t >= self.t1:
                v = clamp((t - self.t1) / (self.close_end - self.t1))
                x = lerp(self.closing[1], self.closing[2], smooth(v))
                lift = 0.6 * self.lift * K * math.sin(math.pi * v)
            feet.append((x, ground - lift))
        moving = self.t0 <= t < self.t1
        ramp = min(1.0, s / self.d, (self.D - s) / self.d) if moving and self.D else 0.0
        frac = (s % self.d) / self.d if self.D else 0.0
        bob = (5 if self.gait != "run" else 12) * K * (1 - math.sin(math.pi * frac)) * ramp
        swing = self.arm * math.sin(math.pi * s / self.d) * ramp if self.D else 0.0
        return {"x": self.xa + self.dirn * s, "ground": ground, "feet": feet, "bob": bob, "swing": swing,
                "lean": self.lean * ramp, "f": self.dirn if self.D else None, "run": self.gait == "run" and moving}


class Walker:
    def __init__(self, x: float, y: float, f: int):
        w = FOOT_W * K
        self.x0, self.y0, self.f0 = x, y, f
        self.feet0 = [x - f * w, x + f * w]           # back foot (0, darker) and front foot (1)
        self.segs: list[Segment] = []
        self.faces: list[tuple[float, int]] = []

    def state(self, t: float) -> dict:
        seg = None
        for sg in self.segs:
            if sg.t0 <= t:
                seg = sg
        f = self.f0
        for sg in self.segs:
            if sg.t0 <= t and sg.D:
                f = sg.dirn
        for tf, ff in self.faces:
            if tf <= t and (seg is None or tf >= seg.t0):
                f = ff
        if seg is None:
            return {"x": self.x0, "ground": self.y0, "feet": [(x, self.y0) for x in self.feet0], "bob": 0.0,
                    "swing": 0.0, "lean": 0.0, "f": f, "run": False}
        st = seg.state(t)
        st["f"] = f
        return st

    def move(self, t: float, x: float, y: float, gait: str, dur: float | None) -> Segment:
        st = self.state(t)
        feet = [p[0] for p in st["feet"]]
        D = abs(x - st["x"])
        speed = GAITS[gait][2]
        dur = dur if dur else max(0.5, D / speed)
        seg = Segment(t, dur, st["x"], st["ground"], x, y, feet, gait)
        self.segs.append(seg)
        return seg

    def face(self, t: float, f: int) -> None:
        self.faces.append((t, f))


def _point(points: dict, value) -> tuple:
    if isinstance(value, (list, tuple)):
        return (float(value[0]), float(value[1]) if len(value) > 1 else 1240.0)
    return points[value]


class Wide:
    """2D stage with camera. The 'wide' uses it directly; the 'close' and the 'duo' (close.py, duo.py) are framings of it,
    with the same figure, the same set and the same stroke, only with another zoom and another view of the body."""

    def __init__(self, flat: dict, events: list[dict], seconds: float, cast: dict | None = None):
        self.seconds = seconds
        self.name = flat.get("set", "pharmacy")
        self.st = st = SETS[self.name]
        self.points = st["points"]
        self.light = Track(1.0 if flat.get("light", "on") not in ("off", "lamp") else (0.12 if flat.get("light") == "lamp" else 0.0))
        self.lamp = Track(1.0 if flat.get("light") == "lamp" else 0.0)   # 'lamp': shop light off, only the headlamp
        self.flicker = Track(flat.get("light", "on") == "flicker")
        self.lit_img = _bg(self.name, True)
        self.unlit_img = None
        if flat.get("light", "on") != "on" or any(e["do"] == "light" for e in events):
            self.unlit_img = _bg(self.name, False)
        self.front = _front_layers(self.name) if st.get("front") else None
        self.lock = Track(1.0 if flat.get("locked") else 0.0)
        self.door = Track(1.0 if flat.get("door") == "open" else 0.0)   # set door (WIDE_DOORS): 0 closed, 1 open
        self.door_on = self.name in WIDE_DOORS and (flat.get("door") in ("open", "closed") or any(
            (e["do"] == "door" and e.get("door") != "stairs") or (e["do"] == "knock" and self.name == "alley")
            for e in events))
        self.stairs = Track(1.0 if flat.get("stairs") == "open" else 0.0)   # stairs door (STAIRS_DOOR)
        self.stairs_on = self.name in STAIRS_DOOR and (flat.get("stairs") in ("open", "closed") or any(
            e["do"] == "door" and e.get("door") == "stairs" for e in events))
        self.hits: list[float] = []                   # instants of the hits on the door (the leaf vibrates)
        self.props = {"jugs": Track(0.0), "scarf": Track(0.0), "pills": Track(0.0)}   # jugs, scarf and medicine on the counter
        for kind in flat.get("props", []):                # objects already on the counter in the 1st frame
            self.props[kind] = Track(1.0)
        self.haze = bool(flat.get("depth"))           # haze over the background: separates the shelf from whoever is in front
        self.count = Track(float(flat.get("infected", 0)))
        app = flat.get("_appear") or {}
        self.sil = Track(1.0 if app.get("start") else 0.0)
        self.sil_xy = (app.get("x", st["sil_x"]), app.get("y", st["sil_y"]))
        self.sil_k = app.get("k", st.get("sil_k", 0.8))
        self.counter_band = bool(flat.get("_counter"))
        self.actors = {}
        for i, a in enumerate(flat.get("actors", [])):
            kind = a.get("kind", "")
            look = look_for(cast, a["id"], kind)
            x, y = _point(self.points, a.get("at", "center"))
            f = {"left": -1, "right": 1}.get(a.get("facing"), 1 if x < 540 else -1)
            act = Acting(look, seconds, 0.6 + i * 1.7, a.get("expr", "calm"))
            if kind == "infected":
                act.turn = Track(1.0)
                act.expr = Track(act.expr.at(0)[:6] + (0.6, 0.0, 1.0))
            self.actors[a["id"]] = {"look": look, "act": act, "walk": Walker(x, y, f), "behind": bool(a.get("behind")),
                                    "turned_at": 0.0 if kind == "infected" else None, "kind": kind,
                                    "view": a.get("_view", "side"), "vf": a.get("_f", 0), "seed": i * 1.3,
                                    "hide": Track(0.0), "outside": a.get("outside") or False}
        self.default_who = next(iter(self.actors), None)
        self.rings: list[tuple[float, str]] = []      # (contact instant, target id)
        self.items: list[tuple[float, str, float | None]] = []   # keys that fall (instant, who, seconds on the ground: None = stays)
        self.extra: list[dict] = []                   # extra cues for the timeline (bite contact, turn)
        if flat.get("_camera"):
            z0, z1, f0, f1 = flat["_camera"]
            self.zoom, self.focus = (z0, z1), (f0, f1)
        else:
            cam = flat.get("camera", {})
            z = cam.get("zoom", 1.0)
            self.zoom = (z, z) if not isinstance(z, list) else tuple(z)
            fcs = cam.get("focus", "center")
            fs = fcs if isinstance(fcs, list) and fcs and not isinstance(fcs[0], (int, float)) else [fcs, fcs]
            self.focus = tuple((p[0], p[1] - 280) for p in (_point(self.points, fs[0]), _point(self.points, fs[-1])))
        self._bg_cache = (None, None)
        for ev in events:
            self._apply(ev)

    # ------------------------------------------------------------ eventos
    def _gait(self, aid: str, t: float, wanted: str) -> str:
        ta = self.actors[aid]["turned_at"]
        return "shuffle" if ta is not None and t >= ta else wanted

    def _apply(self, ev: dict) -> None:
        t, do = ev["t"], ev["do"]
        if do in ("walk", "run", "move"):
            a = self.actors[ev["who"]]
            x, y = _point(self.points, ev["to"])
            a["walk"].move(t, x, y, self._gait(ev["who"], t, "run" if do == "run" else "walk"), ev.get("for"))
        elif do == "turn":
            a = self.actors[ev["who"]]
            a["act"].apply(ev)
            a["turned_at"] = t
        elif do == "bite":
            a, b = self.actors[ev["who"]], self.actors[ev["target"]]
            bx = b["walk"].state(t)["x"]
            ax = a["walk"].state(t)["x"]
            f = 1 if bx >= ax else -1
            stop = bx - f * BITE_GAP * K
            dur = ev.get("for", max(0.35, abs(stop - ax) / 380))
            a["walk"].move(t, stop, b["walk"].state(t)["ground"], "run", dur)   # the lunge is a run, even when turned
            a["walk"].face(t, f)
            a["act"].apply({"do": "lean", "t": t + dur * 0.7, "for": 0.3, "hold": 0.9})
            tc = t + dur + 0.2
            self.rings.append((tc, ev["target"]))
            b["walk"].face(tc, -f)
            # the target staggers one step back (facing the attacker), so the heads do not cover each other
            b["walk"].move(tc + 0.05, bx + f * 70 * K, b["walk"].state(t)["ground"], "walk", 0.55)
            b["walk"].face(tc + 0.06, -f)
            b["act"].apply({"do": "recoil", "t": tc})
            b["act"].apply({"do": "expr", "t": tc, "to": "scared", "for": 0.15})
            tt = tc + 0.35
            b["act"].apply({"do": "turn", "t": tt})
            b["turned_at"] = tt
            self.extra += [{"do": "bite_contact", "who": ev["who"], "target": ev["target"], "t": round(tc, 3),
                            "frame": round(tc * FPS)},
                           {"do": "turn", "who": ev["target"], "t": round(tt, 3), "frame": round(tt * FPS)}]
        elif do == "lock":
            if ev.get("who"):
                self.actors[ev["who"]]["act"].apply(ev)
            self.lock.to(t + (0.35 if ev.get("who") else 0.0), 0.3, 0.0 if ev.get("state") == "unlocked" else 1.0)
        elif do == "door":
            (self.stairs if ev.get("door") == "stairs" else self.door).to(
                t, ev.get("for", 0.45), 1.0 if ev.get("state") == "open" else 0.0)
        elif do == "hide":
            self.actors[ev["who"]]["hide"].to(t, ev.get("for", 0.4), 0.0 if ev.get("state") == "show" else 1.0)
        elif do == "drop":
            self.items.append((t, ev["who"], ev.get("for")))
        elif do == "light":
            self.flicker.to(t, 0, ev["state"] == "flicker")
            self.light.to(t, ev.get("for", LIGHT_SECONDS), {"off": 0.0, "lamp": 0.12}.get(ev["state"], 1.0))
            self.lamp.to(t, ev.get("for", LIGHT_SECONDS), 1.0 if ev["state"] == "lamp" else 0.0)
        elif do == "heat":
            self.count.to(t, ev.get("for", 3.0), float(ev["count"]))
        elif do == "appear":
            self.sil.to(t, ev.get("for", APPEAR_SECONDS), 0.0 if ev.get("state") == "hide" else 1.0)
        elif do == "grab":
            a = self.actors[ev["who"]]
            if not ev.get("target"):
                ev = {**ev, "target": next((i for i in self.actors if i != ev["who"]), None)}
            a["act"].apply(ev)
        elif do == "prop":
            self.props[ev["kind"]].to(t, 0.0, 0.0 if ev.get("state") == "off" else 1.0)
        elif do in ("talk", "expr", "recoil", "hand", "knock", "keys", "phone", "carry", "look", "lean"):
            if do == "knock":
                self.hits += ev.get("_hits", [])
            who = ev.get("who") or (self.default_who if do != "knock" else None)
            if who:
                self.actors[who]["act"].apply(ev)

    def cues(self) -> list[dict]:
        return self.extra

    # ------------------------------------------------------------ poses (no mundo)
    def level(self, t: float) -> float:
        level = self.light.at(t)
        if self.flicker.at(t):
            level *= clamp(0.75 + 1.6 * noise(3.0, t * 5.0))
        return level

    def _pose(self, aid: str, t: float) -> dict:
        a = self.actors[aid]
        ws = a["walk"].state(t)
        act = a["act"]
        turn = act.turn.at(t)
        rec = act.recoil_at(t)
        if a["view"] != "side":                       # front / 3/4: still, breathing
            f = a["vf"]
            breath = 1.6 * K * math.sin(2 * math.pi * t / 3.6 + a["seed"])
            back = -(f or 1) * RECOIL_PX * rec
            hip = (ws["x"] + back, ws["ground"] - figure.HIP_H * K + breath + 6 * K * turn)
            return {"view": a["view"], "f": f, "hip": hip, "ground": ws["ground"], "turn": turn, "hunch": turn,
                    "hands": [None, None], "look_x": act.look.at(t), "head_x": act.look.at(t - 0.22)}
        f = ws["f"]
        hip_h = figure.HIP_H * K - (10 * K if ws["run"] else 0)
        hip = (ws["x"] - f * 20 * rec, ws["ground"] - hip_h + ws["bob"] + 8 * K * turn)
        lean = ws["lean"] + 0.22 * turn + 0.26 * act.lean.at(t) - 0.18 * rec
        breath = 0.015 * math.sin(2 * math.pi * t / 3.4 + a["seed"])
        base = 0.08 + 0.9 * turn
        sw = ws["swing"]
        return {"view": "side", "f": f, "hip": hip, "lean": lean + breath, "feet": ws["feet"], "turn": turn,
                "hunch": turn, "swing": (base + sw, base - sw), "elbow": 1.1 if ws["run"] else 0.25,
                "hands": [None, None], "ground": ws["ground"]}

    def _shoulder(self, pose: dict, toward: float | None = None) -> tuple:
        """Shoulder in the world: in profile, the one at the top of the torso; from the front/3/4, the one on the side of 'toward' (x)."""
        if pose["view"] == "side":
            ux, uy = pose["f"] * math.sin(pose["lean"]), -math.cos(pose["lean"])
            hip = pose["hip"]
            return (hip[0] + ux * figure.TORSO * K, hip[1] + uy * figure.TORSO * K)
        sl, sr = figure.front_shoulders(pose["hip"], K, pose["f"])
        if toward is None:
            return sr if pose["f"] >= 0 else sl
        return sr if toward >= pose["hip"][0] else sl

    def _target(self, on: str, pose: dict, lift: float) -> tuple:
        x0, x1, y, kind = self.st["targets"][on]
        f = pose["f"]
        if kind == "top":
            tx = clamp(pose["hip"][0] + f * 80 * K, x0, x1)
            return (tx, y - 56 * lift)
        tx = clamp(pose["hip"][0] + f * 110 * K, x0, x1) if kind == "glass" else x0
        if kind == "side":                              # fist pulls back and rises before hitting (reads as a hit from afar)
            return (tx - f * 70 * lift, y - 45 * lift)
        return (tx - f * 50 * lift, y)

    def _gestures(self, aid: str, t: float, pose: dict, poses: dict) -> None:
        act = self.actors[aid]["act"]
        hands = pose["hands"]
        if pose["view"] != "side":                     # front/3/4: bandaged hand and grabbing the other
            near = 1 if pose["f"] >= 0 else 0
            sh = figure.front_shoulders(pose["hip"], K, pose["f"])[near]
            rest = (sh[0], sh[1] + 170 * K)
            if act.reach.at(t) > 0.005 and act.reach_target in poses:
                tp = poses[act.reach_target]
                ts = self._shoulder(tp, pose["hip"][0])
                if act.reach_item:                         # offering: arm extended toward the other, at chest height
                    goal = (sh[0] + 0.62 * (ts[0] - sh[0]), ts[1] + 62 * K)
                else:
                    goal = (ts[0], ts[1] + 46 * K)
                hands[near] = lerp(rest, goal, smooth(act.reach.at(t)))
                pose["item"] = act.reach_item
                pose["item_hand"] = near
            elif act.hand.at(t) > 0.005:
                hands[near] = lerp(rest, (pose["hip"][0] + (1 if near else -1) * 22 * K, sh[1] + 40 * K),
                                   smooth(act.hand.at(t)))
            elif act.phone.at(t) > 0.005:                  # phone at chin height, screen toward the camera
                v = act.phone.at(t)
                goal = (sh[0] - 34 * K, sh[1] + 112 * K)      # in front of the belly: arm bent without shrinking too much
                hands[near] = lerp(rest, goal, smooth(v))
                pose["item"] = "phone"
                pose["item_hand"] = near
                pose["hunch"] = 0.9 * v                       # the head lowers
                pose["look_down"] = v                         # the eyes go to the phone
            elif act.keys.at(t) > 0.005:                   # keys in hand in front of the chest, trembling
                v = act.keys.at(t)
                goal = (sh[0] + pose["f"] * 46 * K + 3.5 * K * v * math.sin(t * 58),
                        sh[1] + 78 * K + 3.0 * K * v * math.sin(t * 47 + 1.3))
                hands[near] = lerp(rest, goal, smooth(v))
                pose["item"] = "keys"
                pose["item_hand"] = near
            return
        sh = self._shoulder(pose)
        f = pose["f"]
        rest = (sh[0] + f * 16 * K, sh[1] + 150 * K)
        kn = act.knock_at(t)
        lean = act.lean.at(t)
        cv = act.carry.at(t)
        if cv > 0.005:                                   # jugs: the hands rise from the surface (pallet/counter) until hanging
            v = smooth(cv)
            low = self.st.get("carry_low", 1090)
            hands[0] = lerp((sh[0] + f * 50 * K, low + 8), (sh[0] - f * 14 * K, sh[1] + 158 * K), v)
            hands[1] = lerp((sh[0] + f * 80 * K, low), (sh[0] + f * 46 * K, sh[1] + 150 * K), v)
            pose["lean"] += 0.5 * math.sin(math.pi * cv)     # lowers the torso to pick up/set down and straightens
            pose["item"] = "jug"
        elif act.keys.at(t) > 0.005:                     # keys in the front hand, at chest height, trembling
            v = smooth(act.keys.at(t))
            goal = (sh[0] + f * 52 * K + 3.0 * K * v * math.sin(t * 58), sh[1] + 96 * K + 2.5 * K * v * math.sin(t * 47 + 1.3))
            hands[1] = lerp(rest, goal, v)
            pose["item"] = "keys"
        elif kn:
            lift, on, ramp = kn
            hands[1] = lerp(rest, self._target(on, pose, lift), ramp)
            hands[0] = (sh[0] - f * 4 * K, sh[1] + 150 * K)    # the other arm hangs: only one fist hits
        elif act.lock.at(t) > 0.005:
            lx, ly = self.st["lock_xy"]
            hands[1] = lerp(rest, (lx - f * 4, ly), smooth(act.lock.at(t)))   # the hand arrives; the latch turns in the set
        elif act.reach.at(t) > 0.005 and act.reach_target in poses:
            ts = self._shoulder(poses[act.reach_target], pose["hip"][0])
            if act.reach_item:                                # offering: the hand stops halfway, at chest height
                goal = (pose["hip"][0] + 0.42 * (ts[0] - pose["hip"][0]), ts[1] + 70 * K)
            else:
                goal = (ts[0] - f * 30 * K, ts[1] + 40 * K)
            hands[1] = lerp(rest, goal, smooth(act.reach.at(t)))
            pose["item"] = act.reach_item                     # cup in the outstretched hand (the target does not take it)
        elif act.hand.at(t) > 0.005:
            hands[1] = lerp(rest, (sh[0] + f * 70 * K, sh[1] + 10 * K), smooth(act.hand.at(t)))
        if lean > 0.01:                                  # bite: both hands go to the target's shoulder
            tgt = next((p for tid, p in poses.items() if tid != aid and abs(p["hip"][0] - pose["hip"][0]) < 160), None)
            if tgt:
                ts = self._shoulder(tgt, pose["hip"][0])
                hands[0] = lerp(rest, (ts[0] + f * 6, ts[1] + 30 * K), smooth(lean))
                hands[1] = lerp(rest, (ts[0] - f * 26, ts[1] + 54 * K), smooth(lean))
                pose["head_dx"] = 6 * smooth(lean)

    # ------------------------------------------------------------ camera
    def _cam(self, t: float) -> tuple:
        u = smooth(t / self.seconds) if self.seconds else 0.0
        z = lerp(self.zoom[0], self.zoom[1], u)
        fx, fy = lerp(self.focus[0], self.focus[1], u)
        w, h = W / z, H / z
        cx, cy = clamp(fx, w / 2, W - w / 2), clamp(fy, h / 2, H - h / 2)
        return cx - w / 2, cy - h / 2, z

    def _background(self, level: float, ox: float, oy: float, z: float) -> Image.Image:
        key = (round(ox, 2), round(oy, 2), round(z, 4), round(level, 2) if self.unlit_img else 1.0)
        if self._bg_cache[0] == key:
            return self._bg_cache[1].copy()
        if self.unlit_img is None or level >= 0.995:
            base = self.lit_img
        elif level <= 0.005:
            base = self.unlit_img
        else:
            base = Image.blend(self.unlit_img, self.lit_img, level)
        if z <= 1.0001:
            img = base.copy()
        else:                                            # background enlarged by the camera (gets soft: depth)
            img = base.resize((W * S, H * S), Image.BILINEAR, box=(ox * S, oy * S, (ox + W / z) * S, (oy + H / z) * S))
        self._bg_cache = (key, img)
        return img.copy()

    # ------------------------------------------------------------ desenho
    def _behind_glass(self, img: Image.Image, t: float, T, z: float):
        """The 'appear' silhouette and infected in the background, on a tracing layer cut by the glass mask: they stay behind the
        glass, the frame and the grille. Returns (box in the enlarged frame, mask) so the beam does not lighten."""
        count, p = self.count.at(t), self.sil.at(t)
        if count <= 0.01 and p <= 0.005:
            return None
        gx0, gy0, gx1, gy1 = glass_box(self.name)
        (sx0, sy0), (sx1, sy1) = T(gx0, gy0), T(gx1, gy1)
        bx0, by0 = max(0, int(sx0 * S)), max(0, int(sy0 * S))
        bx1, by1 = min(W * S, int(math.ceil(sx1 * S))), min(H * S, int(math.ceil(sy1 * S)))
        if bx1 - bx0 < 4 or by1 - by0 < 4:
            return None
        layer = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        d = ImageDraw.Draw(layer)
        ox, oy = bx0 / S, by0 / S

        def TL(x, y):
            sx, sy = T(x, y)
            return sx - ox, sy - oy

        if count > 0.01:
            lane = self.st["lane"]
            x0, x1 = lane["x"]
            for i in range(int(math.ceil(count))):
                g = smooth(clamp(count - i))
                span = x1 - x0
                speed = (7 + (i * 5) % 9) * (1 if i % 2 else -1)
                x = x0 + ((0.17 + i * 0.37) % 1.0 * span + speed * t) % span
                edge = clamp(min(x - x0, x1 - x) / 50)
                ph = t * abs(speed) / (22 * lane["k"]) + i
                self._silhouette(d, TL, x, lane["y"] + (i % 3) * 6, lane["k"], ph, int(200 * g * edge),
                                 1 if speed > 0 else -1, z)
        if p > 0.005:
            sx, sy = self.sil_xy
            self._silhouette(d, TL, sx + 4 * noise(9.0, t * 0.5), sy, self.sil_k, 0.0, int(235 * smooth(p)), -1, z,
                             upright=True)
        world = (ox / z + self._ox, oy / z + self._oy, bx1 / S / z + self._ox, by1 / S / z + self._oy)
        mask = glass_mask(self.name).resize(layer.size, Image.BILINEAR, box=world)
        if p > 0.005:
            # backlight: the street behind the shape lightens a little (blue-gray), otherwise the silhouette vanishes in the dark
            sx, sy = TL(*self.sil_xy)
            r = 260 * self.sil_k * z * S
            glow = Image.new("L", layer.size, 0)
            ImageDraw.Draw(glow).ellipse([sx * S - r, sy * S - 2.2 * r, sx * S + r, sy * S + 0.3 * r],
                                         fill=int(255 * smooth(p)))
            glow = ImageChops.multiply(glow.filter(ImageFilter.GaussianBlur(r * 0.3)), mask)
            img.paste((104, 120, 148), (bx0, by0), glow)
        mask = ImageChops.multiply(layer, mask)
        img.paste(INF_SIL, (bx0, by0), mask)
        return (bx0, by0, mask)

    def _silhouette(self, d, TL, x: float, y: float, k: float, ph: float, a: int, f: int, z: float,
                    upright: bool = False) -> None:
        """Infected in the background (curved, dragging step) or the still shape behind the door (upright)."""
        if a <= 0:
            return
        kz = k * z

        def L(pts, w):
            figure.limb(d, [TL(*q) for q in pts], w * kz, a)

        hip = (x, y - 200 * k)
        for s in (-1, 1):
            fx = x + s * (18 if upright else 26 * math.sin(ph)) * k
            knee = (x + s * (16 if upright else 14 * math.sin(ph)) * k + (0 if upright else f * 12 * k), y - 100 * k)
            L([hip, knee, (fx, y)], 44)
        lean = 0.04 if upright else 0.38
        ux, uy = f * math.sin(lean), -math.cos(lean)
        sh = (hip[0] + ux * 200 * k, hip[1] + uy * 200 * k)
        cx, cy = TL((hip[0] + sh[0]) / 2, (hip[1] + sh[1]) / 2)
        figure.block(d, cx, cy, 120 * kz, 250 * kz, 44 * kz, lean * f, a)
        hx, hy = (sh[0] + f * 8 * k, sh[1] - 74 * k) if upright else (sh[0] + f * 46 * k, sh[1] - 34 * k)
        hx, hy = TL(hx, hy)
        r = 64 * kz
        d.ellipse([P(hx - r), P(hy - r), P(hx + r), P(hy + r)], fill=a)
        for s in ((-1, 1) if upright else (1,)):
            if upright:
                sj = (sh[0] + s * 52 * k, sh[1] + 22 * k)
                L([sj, (sj[0] + s * 8 * k, sj[1] + 95 * k), (sj[0] + s * 6 * k, sj[1] + 185 * k)], 36)
            else:
                sway = 10 * k * math.sin(ph * 0.5)
                L([(sh[0], sh[1] + 20 * k), (sh[0] + f * 50 * k, sh[1] + 110 * k),
                   (sh[0] + f * 80 * k + sway, sh[1] + 190 * k)], 36)

    def render(self, t: float) -> Image.Image:
        level = self.level(t)
        ox, oy, z = self._cam(t)
        self._ox, self._oy = ox, oy

        def T(x, y):
            return (x - ox) * z, (y - oy) * z

        img = self._background(level, ox, oy, z)
        if level < 0.999:                                # shop light low: the whole set darkens, only the beam lightens
            img = Image.blend(img, Image.new("RGB", img.size, VAC), 0.42 * (1 - level))
        d = ImageDraw.Draw(img)
        sil = self._behind_glass(img, t, T, z)
        lx, ly = T(*self.st["lock_xy"])                  # latch: little bar that turns 90° when it locks
        a = math.pi / 2 * (1 - smooth(self.lock.at(t)))
        dx, dy = 18 * z * math.sin(a), 18 * z * math.cos(a)
        lock_c = mix((150, 150, 150), (245, 165, 36), smooth(self.lock.at(t)))
        d.line([(P(lx - dx), P(ly - dy)), (P(lx + dx), P(ly + dy))], fill=lock_c, width=max(2, int(7 * z * S)))
        poses = {aid: self._pose(aid, t) for aid in self.actors}
        for aid, pose in poses.items():
            self._gestures(aid, t, pose, poses)
        amb = 0.5 + 0.5 * level if self.name != "busstop" else 0.8 + 0.2 * level

        def shade(c):
            return mix(VAC, c, amb)

        if self.haze:                                    # haze over the background (shelves): less contrast than the action
            y0, y1 = max(0, int(T(0, 600)[1] * S)), min(H * S, int(T(0, 1236)[1] * S))
            if y1 > y0:
                reg = img.crop((0, y0, W * S, y1))
                img.paste(Image.blend(reg, Image.new("RGB", reg.size, VAC), 0.32), (0, y0))
        for aid, pose in poses.items():                  # contact shadow under the feet
            if self.actors[aid]["hide"].at(t) < 0.001:
                gx, gy = T(pose["hip"][0], pose["ground"])
                rx, ry = 66 * K * z, 8 * K * z
                d.ellipse([P(gx - rx), P(gy - ry), P(gx + rx), P(gy + ry)], fill=(7, 9, 14))

        # whoever reaches a hand toward another (grab) is drawn last: the hand sits over the target's body
        reaching = lambda i: self.actors[i]["act"].reach.at(t) > 0.005 and self.actors[i]["act"].reach_target in poses
        order = sorted(self.actors, key=lambda i: (not self.actors[i]["outside"], not self.actors[i]["behind"],
                                                   poses[i]["ground"], reaching(i)))
        lamps = []
        front_done = False
        self._door_draw(d, t, T, z)                      # open door: the dark opening stays behind whoever enters
        for aid in order:
            ac = self.actors[aid]
            if not ac["behind"] and not ac["outside"] and not front_done:
                self._items(d, t, poses, True, T, z)     # what falls behind the counter stays behind it
                self._front(img, level, T, z)
                self._props_draw(d, t, T, z, shade)
                front_done = True
            gone = ac["hide"].at(t)
            if gone >= 0.999:                            # already went in through the door
                continue
            if gone > 0.001:                             # entering: draws on a copy and blends (fade at the opening)
                ghost = img.copy()
                lamps += self._draw_actor(ImageDraw.Draw(ghost), aid, ac, poses[aid], t, shade, T, z, level)
                img.paste(Image.blend(img, ghost, 1 - gone))
                d = ImageDraw.Draw(img)
                continue
            if ac["outside"]:                            # outside: only shows through the glass, behind the frame
                layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                lamps += self._draw_actor(ImageDraw.Draw(layer), aid, ac, poses[aid], t, shade, T, z, level)
                dim = 0.90 if ac["outside"] == "dark" else 0.12   # "dark": silhouette (the face reveal comes later)
                rgb = Image.blend(layer.convert("RGB"), Image.new("RGB", img.size, VAC), dim)
                mask = glass_mask(self.name).resize(
                    (W * S, H * S), Image.BILINEAR, box=(self._ox, self._oy, self._ox + W / z, self._oy + H / z))
                img.paste(rgb, (0, 0), ImageChops.multiply(layer.getchannel("A"), mask))
                d = ImageDraw.Draw(img)
                continue
            lamps += self._draw_actor(d, aid, ac, poses[aid], t, shade, T, z, level)
        if not front_done:
            self._items(d, t, poses, True, T, z)
            self._front(img, level, T, z)
            self._props_draw(d, t, T, z, shade)
        d = ImageDraw.Draw(img)
        self._items(d, t, poses, False, T, z)
        if self.counter_band:
            self._counter(d, level, T, z)
        for tc, tid in self.rings:                       # ring pulse on the target's shoulder
            u = (t - tc) / RING_SECONDS
            if 0 <= u <= 1 and tid in poses:
                sx, sy = T(*self._shoulder(poses[tid]))
                r = (24 + 110 * smooth(u)) * z
                c = mix(VAC, RING, 1 - u * 0.85)
                d.ellipse([P(sx - r), P(sy - r), P(sx + r), P(sy + r)], outline=c, width=max(S, int((5 - 3 * u) * z * S)))
        out = img.resize((W, H), Image.LANCZOS)
        if lamps and max(level, self.lamp.at(t)) > 0.01:
            out = self._beams(out, lamps, max(level, self.lamp.at(t)), sil)
        out.paste(VAC, (0, 0), _top_shade())             # background darkens behind the HUD clock (lamp)
        return out

    def _door_draw(self, d, t: float, T, z: float) -> None:
        """Steel doors that open (`door` event), behind the actors: the dark opening and the leaf, which narrows toward
        the hinge as it opens. Whoever enters walks over the opening and fades out (`hide`). Alley and pharmacy have the
        BACK (exit to the alley); the pharmacy also has the STAIRS (stairs to the pantry)."""
        box = WIDE_DOORS.get(self.name)
        if box and self.door_on:
            self._one_door(d, t, T, z, box, self.door, "BACK", (28, 274))
        sbox = STAIRS_DOOR.get(self.name)
        if sbox and self.stairs_on:
            self._one_door(d, t, T, z, sbox, self.stairs, "STAIRS", (506, 760))

    def _one_door(self, d, t: float, T, z: float, box, track, label: str, wall: tuple) -> None:
        v = smooth(track.at(t))
        shake = 0.0
        if self.name == "alley" and label == "BACK":      # only the alley vibrates; in the pharmacy the hit is on the front glass
            shake = sum(5.5 * math.exp(-(t - h) / 0.09) * math.cos(52 * (t - h)) for h in self.hits if 0 <= t - h < 0.5)
        x0, y0, x1, y1 = box
        if self.name == "pharmacy":                       # the door takes the place of a shelf: repaints the wall and adds a frame
            for y in range(600, 1240, 56):
                (px0, py0), (px1, py1) = T(wall[0], y), T(wall[1], min(1240, y + 56))
                d.rectangle([P(px0), P(py0), P(px1), P(py1)], fill=mix(VAC, (15, 19, 28), min(9, y // 56) / 9))
            (fx0, fy0), (fx1, fy1) = T(x0 - 12, y0 - 14), T(x1 + 12, y1)
            d.rectangle([P(fx0), P(fy0), P(fx1), P(fy1)], fill=(24, 28, 38), outline=WARM, width=max(S, int(2 * z * S)))
        if v >= 0.01:
            (sx0, sy0), (sx1, sy1) = T(x0, y0), T(x1, y1)
            d.rectangle([P(sx0), P(sy0), P(sx1), P(sy1)], fill=mix(VAC, (60, 46, 28), 0.55))
        w = (x1 - x0) * (1 - 0.88 * v)
        dx = shake * (1 - v)                              # the leaf shakes on the impact of the hit (only when closed)
        pts = [T(x0 + dx, y0), T(x0 + w + dx, y0 + 22 * v), T(x0 + w + dx, y1), T(x0 + dx, y1)]
        d.polygon([(P(px), P(py)) for px, py in pts], fill=(30, 34, 44))
        d.line([(P(px), P(py)) for px, py in pts + [pts[0]]], fill=WARM, width=max(S, int(4 * z * S)))
        if v < 0.3:                                       # center line and handle, as in the set's drawing
            mx, top = T(x0 + dx + w * 0.5, y0 + 10)
            d.line([(P(mx), P(top)), (P(mx), P(T(0, y1 - 4)[1]))], fill=(44, 48, 58), width=max(S, int(2 * z * S)))
            hx0, hy0 = T(x0 + dx + w * 0.8, 1010)
            hx1, hy1 = T(x0 + dx + w * 0.92, 1060)
            d.rounded_rectangle([P(hx0), P(hy0), P(hx1), P(hy1)], P(6 * z), fill=AMB_D)
        if self.name == "pharmacy":
            lx, ly = T(x0 + (x1 - x0) / 2 + dx, 700)
            d.text((P(lx), P(ly)), label, font=font(max(10, int(30 * z))), fill=AMB_D, anchor="mm")

    def _props_draw(self, d, t: float, T, z: float, shade) -> None:
        """Jugs and scarf on the pharmacy counter (`prop` event): set objects, behind whoever is in front."""
        if self.name != "pharmacy":
            return
        top = PH_COUNTER[1] - 16
        if self.props["jugs"].at(t) > 0.5:
            for jx in (500, 540):
                sx, sy = T(jx, top)
                figure.jug_shape(d, sx, sy, K * z)
        if self.props["scarf"].at(t) > 0.5:
            sx, sy = T(300, top)
            figure.scarf_shape(d, sx, sy, K * z, shade)
        if self.props["pills"].at(t) > 0.5:
            sx, sy = T(PILLS_X, top)
            figure.pills_shape(d, sx, sy, K * z, shade)

    def _front(self, img: Image.Image, level: float, T, z: float) -> None:
        """Counter in front of whoever is 'behind': RGBA layer of the world, cropped and enlarged by the camera."""
        if not self.front:
            return
        x0, y0, x1, y1 = self.st["front_box"]
        (sx0, sy0), (sx1, sy1) = T(x0, y0), T(x1, y1)
        bx0, by0, bx1, by1 = int(sx0 * S), int(sy0 * S), int(math.ceil(sx1 * S)), int(math.ceil(sy1 * S))
        if bx1 <= 0 or by1 <= 0 or bx0 >= W * S or by0 >= H * S:
            return
        layer = self.front[1] if level > 0.5 else self.front[0]
        piece = layer.resize((bx1 - bx0, by1 - by0), Image.BILINEAR, box=(x0 * S, y0 * S, x1 * S, y1 * S))
        img.paste(piece, (bx0, by0), piece)

    def _counter(self, d, level: float, T, z: float) -> None:
        """Foreground counter of the duo ('counter': true), at waist height."""
        _, top = T(0, COUNTER_Y)
        c = mix(VAC, COUNTER, 0.6 + 0.4 * level)
        tc = mix(VAC, COUNTER_TOP, 0.6 + 0.4 * level)
        d.rectangle([0, P(top), W * S, H * S], fill=c)
        d.rectangle([0, P(top - 7 * z), W * S, P(top + 4 * z)], fill=tc)
        d.line([(0, P(top - 7 * z)), (W * S, P(top - 7 * z))], fill=mix(tc, (245, 165, 36), 0.4 * level + 0.1),
               width=max(S, int(1.5 * z * S)))
        for x in range(0, W, 220):
            d.line([(P(x + 60), P(top + 20 * z)), (P(x + 60), H * S)], fill=mix(VAC, (54, 46, 40), 0.6 + 0.4 * level),
                   width=max(S, int(z * S)))

    def _items(self, d, t: float, poses: dict, behind: bool, T, z: float) -> None:
        for t0, aid, rest in self.items:                 # the key falls from the hand, bounces and stops (rest: disappears when the owner picks it up)
            if t < t0 or self.actors[aid]["behind"] != behind:
                continue
            pose = poses[aid]
            sh = self._shoulder(pose)
            f = pose["f"] or 1
            x0, y0 = sh[0] + f * 16 * K, sh[1] + 150 * K
            gy = pose["ground"] - 4
            tau = t - t0
            fall = math.sqrt(2 * max(1.0, gy - y0) / 2600.0)
            if rest is not None and tau > fall + 0.22 + rest:
                continue
            if tau < fall:
                x, y, ang = x0 + f * 40 * tau, y0 + 0.5 * 2600 * tau * tau, tau * 14
            else:
                b = tau - fall
                bt = 0.22
                hop = 30 * math.sin(math.pi * b / bt) if b < bt else 0.0
                x, y, ang = x0 + f * (40 * fall + 30 * min(b, bt)), gy - hop, fall * 14 + 1.2
            figure.key_shape(d, *T(x, y), z, ang)

    def _draw_actor(self, d, aid: str, a: dict, pose: dict, t: float, shade, T, z: float, level: float) -> list:
        act, look = a["act"], a["look"]
        k = K * z
        sp = dict(pose)                                  # pose in the frame: same figure, scale k
        sp["hip"] = T(*pose["hip"])
        sp["ground"] = T(0, pose["ground"])[1]
        if pose.get("feet"):
            sp["feet"] = [T(*q) for q in pose["feet"]]
        sp["hands"] = [T(*q) if q is not None else None for q in pose["hands"]]
        lamp = max(level, self.lamp.at(t)) if look["accessory"] == "headlamp" else 0.0
        draw = figure.body_side if pose["view"] == "side" else figure.body_front
        out = draw(d, look, sp, k, act.params(t), act.mouth(t), act.blink(t), lamp, shade)
        h = act.hand.at(t)
        if h > 0.5:                                      # bandaged hand shown
            hx, hy = out["hand"]
            figure.hand_shape(d, hx, hy - 10 * z, 0.4 * k * smooth((h - 0.5) * 2), shade(figure.skin_of(look)), True,
                              pose["f"] or 1)
        return [(out["lamp"], out["dir"], k)] if out.get("lamp") else []

    def _beams(self, img: Image.Image, lamps: list, level: float, sil) -> Image.Image:
        """Headlamp beam as added light (1/4 resolution, blurred), with the scene's light level;
        the silhouette behind the glass stays dark inside the beam."""
        small = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
        d = ImageDraw.Draw(small)
        c = tuple(int(v * 60 / 255 * level) for v in AMB)
        for (lx, ly), (dx, dy), k in lamps:
            n = math.hypot(dx, dy) or 1.0
            dx, dy = dx / n, dy / n
            px, py = -dy, dx
            L = 1500
            spread = L * (0.42 if abs(dy) > 0.3 else 0.3)
            w0 = 14 * k
            pts = [(lx + px * w0, ly + py * w0), (lx - px * w0, ly - py * w0),
                   (lx + dx * L - px * spread, ly + dy * L - py * spread), (lx + dx * L + px * spread, ly + dy * L + py * spread)]
            d.polygon([(x / 4, y / 4) for x, y in pts], fill=c)
        beam = small.filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR)
        if sil:
            bx0, by0, mask = sil
            m = mask.resize((max(1, mask.width // S), max(1, mask.height // S)), Image.BILINEAR)
            beam.paste((0, 0, 0), (bx0 // S, by0 // S), m)
        return ImageChops.add(img, beam)


TOP_SHADE = 360                  # px at the top of the frame that darken (the HUD sits at y 230 to 406)


def _top_shade() -> Image.Image:
    """Top gradient mask: almost Vacuum at y 0, nothing at TOP_SHADE (no light touches the clock)."""
    key = "top_shade"
    if key not in _BG:
        m = Image.new("L", (W, TOP_SHADE), 0)
        d = ImageDraw.Draw(m)
        for y in range(TOP_SHADE):
            d.line([(0, y), (W, y)], fill=int(225 * (1 - y / TOP_SHADE) ** 1.5))
        _BG[key] = m
    return _BG[key]


def _front_layers(name: str) -> tuple:
    """Front piece (counter) drawn once in RGBA, off and on."""
    key = ("front", name)
    if key not in _BG:
        layers = []
        for level in (0.0, 1.0):
            im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
            SETS[name]["front"](ImageDraw.Draw(im), level)
            layers.append(im)
        _BG[key] = tuple(layers)
    return _BG[key]
