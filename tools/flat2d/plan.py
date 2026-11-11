"""'plan' shot: technical floor plan of a place (paper grid, amber line walls, labels and dimension lines), with
Sam, ordinary people and the infected as markers, doors and windows with state and the room's light.

The still background (grid, walls, labels) is drawn once in two versions, light off and on; each
frame only blends the two and draws what moves on top. The heat blob is blurred at 1/4 of the resolution.
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .common import (AMB, AMB_D, FPS, GRID, H, INF, INF_DOT, LIT, P, QUI, S, TXT, VAC, W, clamp, font, lerp,
                     mix, noise, smooth)
from .cast import look_for
from .places import PLACES
from .tracks import Track

COLORS = {"amb": AMB, "dim": AMB_D, "txt": TXT, "qui": QUI}
HEAT_DOWN = 4              # the heat blob is drawn at 1/4 and enlarged (the blur hides the loss)
MOVE_SPEED = 260.0         # px per second of a walking marker (without 'for')
DOOR_SECONDS = 0.5
HEAT_SECONDS = 3.0
LIGHT_SECONDS = 0.25
TURN_SECONDS = 0.6         # cast actor turns infected: colored marker -> blue-gray dot
BITE_GAP = 34              # the attacker stops at this distance from the target
RING = (214, 218, 224)     # bite pulse: grayish white, never red
RING_SECONDS = 0.7


def _point(place: dict, value) -> tuple[float, float]:
    return tuple(value) if isinstance(value, (list, tuple)) else place["points"][value]


def _static(place: dict, lit: bool) -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), VAC)
    d = ImageDraw.Draw(img)
    if lit:
        for room in place["rooms"]:
            if room.get("light"):
                x0, y0, x1, y1 = room["rect"]
                d.rectangle([P(x0), P(y0), P(x1), P(y1)], fill=LIT)
    for gx in range(0, W, 40):                             # technical paper grid
        d.line([(P(gx), 0), (P(gx), H * S)], fill=GRID, width=S)
    for gy in range(0, H, 40):
        d.line([(0, P(gy)), (W * S, P(gy))], fill=GRID, width=S)
    if lit:                                                # warm glow around the lamps
        glow = Image.new("L", (W // HEAT_DOWN, H // HEAT_DOWN), 0)
        gd = ImageDraw.Draw(glow)
        for room in place["rooms"]:
            for x, y in place["lights"].get(room.get("light"), []):
                r = 150 / HEAT_DOWN
                gd.ellipse([x / HEAT_DOWN - r, y / HEAT_DOWN - r, x / HEAT_DOWN + r, y / HEAT_DOWN + r], fill=34)
        glow = glow.filter(ImageFilter.GaussianBlur(60 / HEAT_DOWN)).resize(img.size, Image.BILINEAR)
        room_mask = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(room_mask)
        for room in place["rooms"]:
            x0, y0, x1, y1 = room["rect"]
            md.rectangle([P(x0), P(y0), P(x1), P(y1)], fill=255)
        img.paste(AMB, mask=ImageChops.multiply(glow, room_mask))
    for x0, y0, x1, y1 in place["rects"]:
        d.rectangle([P(x0), P(y0), P(x1), P(y1)], outline=AMB_D, width=2 * S)
    for x0, y0, x1, y1, color, width in place["lines"]:
        d.line([(P(x0), P(y0)), (P(x1), P(y1))], fill=COLORS[color], width=width * S)
    for x0, y0, x1, y1 in place["dashes"]:
        n = int(math.hypot(x1 - x0, y1 - y0) // 40)
        for k in range(n):
            a, b = k / n, (k + 0.5) / n
            d.line([(P(lerp(x0, x1, a)), P(lerp(y0, y1, a))), (P(lerp(x0, x1, b)), P(lerp(y0, y1, b)))],
                   fill=AMB_D, width=2 * S)
    for x, y, text, size, color in place["labels"]:
        d.text((P(x), P(y)), text, font=font(size), fill=COLORS[color])
    for room in place["rooms"]:
        x0, y0, x1, y1 = room["rect"]
        d.rectangle([P(x0), P(y0), P(x1), P(y1)], outline=AMB, width=4 * S)
    for door in place["doors"].values():                   # door opening in the wall
        hx, hy = door["hinge"]
        a = math.radians(door["closed"])
        d.line([(P(hx), P(hy)), (P(hx + door["length"] * math.cos(a)), P(hy + door["length"] * math.sin(a)))],
               fill=LIT if lit else VAC, width=6 * S)
        r = door["length"]
        lo, hi = sorted((door["closed"], door["open"]))
        d.arc([P(hx - r), P(hy - r), P(hx + r), P(hy + r)], lo, hi, fill=AMB_D, width=S)
    for win in place["windows"].values():
        (ax, ay), (bx, by) = win["a"], win["b"]
        d.line([(P(ax), P(ay)), (P(bx), P(by))], fill=VAC, width=6 * S)
        d.text((P(win["label_xy"][0]), P(win["label_xy"][1])), win["label"], font=font(18), fill=AMB_D)
    for room in place["rooms"]:                            # lamps: circle with X (floor plan convention)
        for x, y in place["lights"].get(room.get("light"), []):
            c = AMB if lit else AMB_D
            d.ellipse([P(x - 13), P(y - 13), P(x + 13), P(y + 13)], outline=c, width=2 * S)
            k = 9
            d.line([(P(x - k), P(y - k)), (P(x + k), P(y + k))], fill=c, width=2 * S)
            d.line([(P(x - k), P(y + k)), (P(x + k), P(y - k))], fill=c, width=2 * S)
    tx, ty = place["title_xy"]
    d.text((P(tx), P(ty)), place["title"], font=font(30), fill=AMB)
    for (x0, y0), (x1, y1), text in place["dims"]:        # cotas
        d.line([(P(x0), P(y0)), (P(x1), P(y1))], fill=AMB_D, width=2 * S)
        for xx, yy in ((x0, y0), (x1, y1)):
            d.line([(P(xx), P(yy - 12)), (P(xx), P(yy + 12))], fill=AMB_D, width=2 * S)
        d.text((P((x0 + x1) / 2), P(y0 + 26)), text, font=font(24), fill=AMB_D, anchor="mm")
    return img


class Plan:
    def __init__(self, flat: dict, events: list[dict], seconds: float, cast: dict | None = None):
        self.place = place = PLACES[flat.get("place", "pharmacy")]
        self.seconds = seconds
        self.unlit, self.lit = _static(place, False), _static(place, True)
        # initial states: preset + what the scene asks for
        self.doors = {k: Track(0.0 if flat.get("doors", {}).get(k, v["state"]) != "open" else 1.0)
                      for k, v in place["doors"].items()}
        self.locks = {k: Track(1.0 if flat.get("doors", {}).get(k, v["state"]) == "locked" else 0.0)
                      for k, v in place["doors"].items()}
        self.windows = {k: Track(flat.get("windows", {}).get(k, v["state"])) for k, v in place["windows"].items()}
        self.light = Track(1.0 if flat.get("light", "on") != "off" else 0.0)
        self.flicker = Track(flat.get("light", "on") == "flicker")
        self.count = Track(float(flat.get("infected", 0)))
        self.actors = {}
        self.looks, self.inf = {}, {}
        self.rings: list[tuple[float, str]] = []
        self.extra: list[dict] = []
        cast = cast or {}
        actors = flat.get("actors") or [{"id": "sam", "kind": "sam", "at": place["sam"]}]
        for a in actors:
            # cast actor (id in 'cast'): marker with a top-down head, name and arrow; without a cast, the old one
            kind = "cast" if a["id"] in cast else a.get("kind", "cast")
            self.actors[a["id"]] = (kind, Track(_point(place, a.get("at", place["sam"]))))
            self.looks[a["id"]] = look_for(cast, a["id"], a.get("kind", ""))
            self.inf[a["id"]] = Track(1.0 if a.get("kind") == "infected" else 0.0)
        self.inf_center = Track(_point(place, place["infected_center"]))
        cam = flat.get("camera", {})
        z = cam.get("zoom", 1.0)
        self.zoom = (z, z) if not isinstance(z, list) else tuple(z)
        f = cam.get("focus", "center")
        fs = f if isinstance(f, list) and f and not isinstance(f[0], (int, float)) else [f, f]
        self.focus = (_point(place, fs[0]), _point(place, fs[-1]))
        for ev in events:
            self._apply(ev)

    def _apply(self, ev: dict) -> None:
        t, do = ev["t"], ev["do"]
        if do == "door":
            k = ev.get("door", next(iter(self.place["doors"])))
            dur = ev.get("for", DOOR_SECONDS)
            if ev["state"] == "open":
                self.locks[k].to(t, 0.15, 0.0)
                self.doors[k].to(t + 0.1, dur, 1.0)
            else:
                self.doors[k].to(t, dur, 0.0)
                self.locks[k].to(t + dur, 0.2, 1.0 if ev["state"] == "locked" else 0.0)
        elif do == "window":
            self.windows[ev.get("window", next(iter(self.place["windows"])))].to(t, 0, ev["state"])
        elif do == "light":
            self.flicker.to(t, 0, ev["state"] == "flicker")
            self.light.to(t, ev.get("for", LIGHT_SECONDS), 0.0 if ev["state"] == "off" else 1.0)
        elif do == "heat":
            self.count.to(t, ev.get("for", HEAT_SECONDS), float(ev["count"]))
        elif do == "move":
            track = self.inf_center if ev["who"] == "infected" else self.actors[ev["who"]][1]
            a, b = track.at(t), _point(self.place, ev["to"])
            dur = ev.get("for", max(0.6, math.hypot(b[0] - a[0], b[1] - a[1]) / MOVE_SPEED))
            track.to(t, dur, b)
        elif do == "turn":
            self.inf[ev["who"]].to(t, ev.get("for", TURN_SECONDS), 1.0)
        elif do == "bite":
            # the attacker gets close to the target, ring pulse, and the target turns (turn) right after
            track, target = self.actors[ev["who"]][1], self.actors[ev["target"]][1]
            a, b = track.at(t), target.at(t)
            dist = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            stop = (b[0] - (b[0] - a[0]) / dist * BITE_GAP, b[1] - (b[1] - a[1]) / dist * BITE_GAP)
            dur = ev.get("for", max(0.4, (dist - BITE_GAP) / (MOVE_SPEED * 1.5)))
            track.to(t, dur, stop)
            tc = t + dur
            self.rings.append((tc, ev["target"]))
            self.inf[ev["target"]].to(tc + 0.1, TURN_SECONDS, 1.0)
            self.extra += [{"do": "bite_contact", "who": ev["who"], "target": ev["target"], "t": round(tc, 3),
                            "frame": round(tc * FPS)},
                           {"do": "turn", "who": ev["target"], "t": round(tc + 0.1, 3), "frame": round((tc + 0.1) * FPS)}]

    def cues(self) -> list[dict]:
        return self.extra

    def light_level(self, t: float) -> float:
        level = self.light.at(t)
        if self.flicker.at(t):
            # flicker: almost always on, with short drops (smooth noise, no repeating pattern)
            level *= clamp(0.75 + 1.6 * noise(3.0, t * 5.0))
        return level

    def render(self, t: float) -> Image.Image:
        level = self.light_level(t)
        if level >= 0.995:
            img = self.lit.copy()
        elif level <= 0.005:
            img = self.unlit.copy()
        else:
            img = Image.blend(self.unlit, self.lit, level)
        place = self.place
        count = self.count.at(t)
        cx, cy = self.inf_center.at(t)
        spots = []
        for i, (ox, oy) in enumerate(place["infected_spots"]):
            g = clamp(count - i)
            if g <= 0:
                continue
            # slow drift of each infected (nothing still, nothing jumping)
            spots.append((cx + ox + 6 * noise(i, t * 0.7), cy + oy + 6 * noise(i + 0.5, t * 0.6), smooth(g)))
        # actors who turned (turn/bite) also heat up: blob around the point, growing with the change
        turned = [(aid, *self.actors[aid][1].at(t), smooth(tr.at(t))) for aid, tr in self.inf.items() if tr.at(t) > 0.01]
        if spots or turned:
            small = Image.new("L", (W // HEAT_DOWN, H // HEAT_DOWN), 0)
            hd = ImageDraw.Draw(small)
            for x, y, g in spots + [(x, y, g) for _, x, y, g in turned]:
                r = (60 + 20 * g) * g / HEAT_DOWN
                hd.ellipse([x / HEAT_DOWN - r, y / HEAT_DOWN - r, x / HEAT_DOWN + r, y / HEAT_DOWN + r], fill=150)
            small = small.filter(ImageFilter.GaussianBlur(28 / HEAT_DOWN))
            img.paste(INF, mask=small.resize(img.size, Image.BILINEAR))
        d = ImageDraw.Draw(img)
        for x, y, g in spots:
            r = 9 * g
            d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=INF_DOT)
        if spots:
            top = min(spots, key=lambda s: s[1])
            a = clamp(count)
            d.text((P(top[0] + 26), P(top[1] - 34)), "INF", font=font(22),
                   fill=tuple(int(VAC[i] + (INF_DOT[i] - VAC[i]) * a) for i in range(3)))
        for k, door in place["doors"].items():
            self._door(d, door, self.doors[k].at(t), self.locks[k].at(t))
        for k, win in place["windows"].items():
            self._window(d, win, self.windows[k].at(t))
        for tc, tid in self.rings:                         # bite pulse around the target
            u = (t - tc) / RING_SECONDS
            if 0 <= u <= 1:
                x, y = self.actors[tid][1].at(t)
                r = 24 + 80 * smooth(u)
                d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], outline=mix(VAC, RING, 1 - 0.85 * u),
                          width=int((5 - 3 * u) * S))
        for aid, (kind, track) in self.actors.items():
            x, y = track.at(t)
            inf = smooth(self.inf[aid].at(t))
            if inf >= 0.999:
                d.ellipse([P(x - 9), P(y - 9), P(x + 9), P(y + 9)], fill=INF_DOT)
            elif kind == "cast":
                self._named(d, aid, track, x, y, t, inf)
            elif kind == "sam":
                c = mix(AMB, INF_DOT, inf)
                ring = lerp(40 + 2.5 * math.sin(t * 2.4), 12, inf)
                d.ellipse([P(x - ring), P(y - ring), P(x + ring), P(y + ring)], outline=c, width=3 * S)
                r = lerp(16, 9, inf)
                d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=c)
                # label above the marker: does not cross the wall when Sam reaches the door
                d.text((P(x), P(y - 50)), "SAM", font=font(34), fill=mix(VAC, AMB, 1 - inf), anchor="ms")
            else:
                c = mix(QUI, INF_DOT, inf)
                r = lerp(22, 12, inf)
                d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], outline=c, width=2 * S)
                r = lerp(10, 9, inf)
                d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=c)
        return self._camera(img, t)

    def _named(self, d, aid: str, track, x: float, y: float, t: float, inf: float) -> None:
        """Cast actor: ring in the 'marker' color, shoulders (disc) and top-down head in the hair color,
        name above and a short arrow toward where they walk. With 'turn' everything becomes the blue-gray dot."""
        look = self.looks[aid]
        mk = mix(look["marker"], INF_DOT, inf)
        head = look["skin"] if look["hair_style"] == "bald" else look["hair"]
        ring = lerp(40 + 2.5 * math.sin(t * 2.4 + len(aid)), 12, inf)
        d.ellipse([P(x - ring), P(y - ring), P(x + ring), P(y + ring)], outline=mk, width=3 * S)
        r = lerp(22, 9, inf)
        d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=mk)
        r = lerp(13, 0, inf)
        if r > 1:
            d.ellipse([P(x - r), P(y - r), P(x + r), P(y + r)], fill=mix(head, INF_DOT, inf), outline=VAC, width=2 * S)
        d.text((P(x), P(y - 50)), look["name"], font=font(30), fill=mix(VAC, mk, 1 - inf), anchor="ms")
        px, py = track.at(max(0.0, t - 0.1))
        vx, vy = (x - px) / 0.1, (y - py) / 0.1
        speed = math.hypot(vx, vy)
        a = clamp((speed - 15) / 100) * (1 - inf)
        if a > 0.02:
            ux, uy = vx / speed, vy / speed
            c = mix(VAC, mk, a)
            x0, y0 = x + ux * (ring + 8), y + uy * (ring + 8)
            x1, y1 = x + ux * (ring + 32), y + uy * (ring + 32)
            d.line([(P(x0), P(y0)), (P(x1), P(y1))], fill=c, width=3 * S)
            d.polygon([(P(x1 + ux * 10), P(y1 + uy * 10)), (P(x1 - uy * 8), P(y1 + ux * 8)), (P(x1 + uy * 8), P(y1 - ux * 8))],
                      fill=c)

    def _door(self, d, door: dict, openness: float, lock: float) -> None:
        hx, hy = door["hinge"]
        ang = math.radians(lerp(door["closed"], door["open"], openness))
        L = door["length"]
        ex, ey = hx + L * math.cos(ang), hy + L * math.sin(ang)
        d.line([(P(hx), P(hy)), (P(ex), P(ey))], fill=AMB, width=4 * S)
        if lock > 0.01:                                    # lock: filled square that grows near the tip
            mx, my = lerp((hx, hy), (ex, ey), 0.78)
            nx, ny = -math.sin(ang), math.cos(ang)
            side = -1 if door["open"] > door["closed"] else 1
            qx, qy = mx + nx * 16 * side, my + ny * 16 * side
            r = 11 * smooth(lock)
            d.rectangle([P(qx - r), P(qy - r), P(qx + r), P(qy + r)], fill=AMB)
        state = "LOCKED" if lock > 0.5 else "OPEN" if openness > 0.5 else "CLOSED"
        lx, ly = door["label_xy"]
        d.text((P(lx), P(ly)), f"{door['label']} · {state}", font=font(22), fill=AMB)

    def _window(self, d, win: dict, state: str) -> None:
        (ax, ay), (bx, by) = win["a"], win["b"]
        L = math.hypot(bx - ax, by - ay)
        nx, ny = -(by - ay) / L, (bx - ax) / L
        if state == "closed":
            for s in (-4, 4):
                d.line([(P(ax + nx * s), P(ay + ny * s)), (P(bx + nx * s), P(by + ny * s))], fill=AMB, width=2 * S)
        elif state == "broken":
            pts = []
            for k in range(9):
                u = k / 8
                s = (7 if k % 2 else -7) if 0 < k < 8 else 0
                pts.append((P(lerp(ax, bx, u) + nx * s), P(lerp(ay, by, u) + ny * s)))
            d.line(pts, fill=AMB_D, width=2 * S)

    def _camera(self, img: Image.Image, t: float) -> Image.Image:
        u = smooth(t / self.seconds) if self.seconds else 0.0
        z = lerp(self.zoom[0], self.zoom[1], u)
        fx, fy = lerp(self.focus[0], self.focus[1], u)
        w, h = W / z, H / z
        cx, cy = clamp(fx, w / 2, W - w / 2), clamp(fy, h / 2, H - h / 2)
        box = (P(cx - w / 2), P(cy - h / 2), P(cx + w / 2), P(cy + h / 2))
        return img.resize((W, H), Image.LANCZOS, box=box)
