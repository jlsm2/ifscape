"""Live panel in the corner: small label, big amber number and sub-label.

Replaces the static stamp. The number moves:
- "NOW" becomes a running clock (0:00:00, 0:00:01, ...);
- on a time jump, the number rolls quickly from the previous value to the new one (1 HOUR -> 6 HOURS -> 2 DAYS);
- a counter ("counter" in the scene) climbs slowly and drops at the marked instant (population -> 0).
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from . import brand, graphics

if TYPE_CHECKING:
    from .script import Counter

_UNITS = [  # (seconds, singular, plural), from largest to smallest
    (365.25 * 86400, "YEAR", "YEARS"),
    (30.44 * 86400, "MONTH", "MONTHS"),
    (7 * 86400, "WEEK", "WEEKS"),
    (86400, "DAY", "DAYS"),
    (3600, "HOUR", "HOURS"),
    (60, "MIN", "MIN"),
    (1, "SECOND", "SECONDS"),
]
_BY_NAME = {name: secs for secs, *names in _UNITS for name in names}
ROLL_FLOOR = 10.0   # coming from "NOW", the roll starts at 10 s (the clock of the previous scene already ran a few seconds)


def parse_duration(text: str | None) -> float | None:
    """'NOW' -> 0; '2 DAYS' -> seconds; '10,000 YEARS' -> seconds; anything not understood -> None."""
    if not text:
        return None
    t = text.strip().upper()
    if t == "NOW":
        return 0.0
    m = re.fullmatch(r"([\d,]+)\s+([A-Z]+)", t)
    if not m or m.group(2) not in _BY_NAME:
        return None
    return int(m.group(1).replace(",", "")) * _BY_NAME[m.group(2)]


def format_duration(seconds: float) -> str:
    """Largest unit in which the value exceeds 1, whole number: 5400 -> '1 HOUR', 2e6 -> '23 DAYS'."""
    for secs, one, many in _UNITS:
        if seconds >= secs:
            n = int(round(seconds / secs))
            return f"{n:,} {one if n == 1 else many}"
    return "0 SECONDS"


def parse_count(text: str | None) -> float | None:
    """Count without a time unit, for the "YEARS AGO" panel: '200 MILLION' -> 2e8; '300,000' -> 3e5."""
    if not text:
        return None
    m = re.fullmatch(r"([\d,]+)(?:\s+(MILLION|BILLION))?", text.strip().upper())
    if not m:
        return None
    scale = {None: 1, "MILLION": 1e6, "BILLION": 1e9}[m.group(2)]
    return int(m.group(1).replace(",", "")) * scale


def format_count(value: float) -> str:
    """'187 MILLION' from a million up; below that, the whole number with commas ('12,345')."""
    for scale, name in ((1e9, "BILLION"), (1e6, "MILLION")):
        if value >= scale:
            return f"{int(round(value / scale)):,} {name}"
    return f"{int(round(value)):,}"


def roll(a: float, b: float, steps: int, fmt=format_duration) -> list[str]:
    """Intermediate values on a logarithmic scale from a to b (b included, a not), going up or down."""
    lo = math.log(max(a, 1.0))
    hi = math.log(max(b, 1.0))
    seen, out = set(), []
    for k in range(1, steps + 1):
        value = fmt(math.exp(lo + (hi - lo) * k / steps))
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def counter_value(c: Counter, t: float) -> float:
    if t < c.change_at:
        return round(c.start + c.rate * t, c.decimals) if c.decimals else int(c.start + c.rate * t)
    p = min(1.0, (t - c.change_at) / max(c.change_over, 1e-6))
    eased = p if c.unit == "clock" else p * p * (3 - 2 * p)   # the stopwatch runs in real time; the rest starts and ends slowly
    base = c.start + c.rate * c.change_at
    value = base + (c.end - base) * eased
    return round(value, c.decimals) if c.decimals else int(round(value))


CLOCK_RE = re.compile(r"^\d\d:\d\d\.\d\d$")


class FinalWord(str):
    """Word that closes a counter ("HERE", "GONE"): the panel shows it in caps, without lowering it like the units."""


def clock_text(seconds: float) -> str:
    """Linear stopwatch '00:12.40' (hundredths), the same format as the counter with unit \"clock\"."""
    return _counter_text(int(max(0.0, seconds) * 1000), "clock")


def clock_subs(n: int, start: float) -> list[str]:
    """Small stopwatch under the damage number, one text per panel frame; 'start' = second of the stopwatch at the
    first frame of the scene (always grows, across scenes too)."""
    return [clock_text(start + i / brand.PANEL_FPS) for i in range(n)]


def _counter_text(value: float, unit: str, decimals: int = 0) -> str:
    """'38 trillion' on the panel (unit in lowercase, as in the stamps); zero stays just '0'.
    With unit "clock", the value is in milliseconds and becomes a stopwatch: 1280 -> '00:01.28' (moon-disappeared)."""
    if unit == "clock":
        cs = max(0, value) // 10
        return f"{cs // 6000:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"
    if unit == "%":                                  # the symbol is attached: "46%"
        return f"{value:,}%" if value else f"{value:,}"
    number = f"{value:,.{decimals}f}" if decimals else f"{value:,}"
    return f"{number} {unit}" if unit and value else number


def values(stamp: str | None, previous: str | None, counter: Counter | None, seconds: float,
           clock_start: float = 0.0, now_clock: bool = True, clock_from: float = 0.0) -> list[str | None]:
    """The panel number in each panel frame (brand.PANEL_FPS) during the scene. 'clock_start': how much the
    "NOW" clock already ran in previous scenes with the same stamp (it continues instead of resetting)."""
    n = max(1, int(math.ceil(seconds * brand.PANEL_FPS)))
    if counter:
        end_at = counter.change_at + counter.change_over
        return [FinalWord(counter.final) if counter.final and i / brand.PANEL_FPS >= end_at
                else _counter_text(counter_value(counter, i / brand.PANEL_FPS), counter.unit,
                                  counter.decimals)
                for i in range(n)]
    if not stamp:
        return [None] * n
    frames = max(2, int(brand.PANEL_ROLL * brand.PANEL_FPS))
    is_now = stamp.strip().upper() == "NOW"
    is_today = stamp.strip().upper() == "TODAY"        # closes the "YEARS AGO" count without becoming a stopwatch (dinosaurs-never-extinct)
    old_count = parse_count(previous)
    if stamp != previous and old_count is not None and (is_now or is_today or parse_count(stamp) is not None):
        # Countdown ("YEARS AGO", pangaea-never-split): rolls down to the new value, "NOW" or "TODAY".
        seq = roll(old_count, parse_count(stamp) if not (is_now or is_today) else 1.0, frames, format_count)
        seq[-1] = stamp
        per = frames / len(seq)
        rolling = [seq[min(len(seq) - 1, int(i / per))] for i in range(frames)]
        return (rolling + [stamp] * n)[:n]
    if is_now:
        # Seconds in words, in the same format as the jumps (with a "0:00:06" clock the format switched in the
        # middle of the count on turning to "19 SECONDS", QA finding).
        # Continues from where the previous scene stopped: resetting on the cut made time run backwards (QA finding).
        if now_clock:
            # Stopwatch going up ("00:02.10"), in the same format as the countdown counter.
            # 'clock_from': second of the "NOW" segment at which the stopwatch reads zero (the instant of the event).
            return [_counter_text(int(max(0.0, clock_start + i / brand.PANEL_FPS - clock_from) * 1000), "clock")
                    for i in range(n)]
        return [format_duration(clock_start + i / brand.PANEL_FPS) for i in range(n)]
    new, old = parse_duration(stamp), parse_duration(previous)
    if new is None or old is None or new <= old or stamp == previous:
        return [stamp] * n
    seq = roll(max(old, ROLL_FLOOR), new, frames)
    seq[-1] = stamp                                  # ends exactly on the script text
    per = frames / len(seq)
    rolling = [seq[min(len(seq) - 1, int(i / per))] for i in range(frames)]
    return (rolling + [stamp] * n)[:n]


def display(value: str) -> str:
    """How the number appears: units in lowercase ('2 DAYS' -> '2 days'); digits stay the same."""
    if isinstance(value, FinalWord):
        return str(value)
    if value.strip().upper() in ("NOW", "TODAY"):      # alone (cover): lowercase looked like an error
        return value.strip().capitalize()
    return value.lower()


def draw(label: str, value: str | None, sub: str, out: Path) -> Path:
    """One panel image, always the same size (the position on screen does not jump between frames).
    "Instrument" style: amber dot + small spaced label, thin line, big white number,
    data line in small normal text; soft shadow in place of an outline."""
    img = Image.new("RGBA", (brand.PANEL_W, brand.PANEL_H), (0, 0, 0, 0))
    if value is not None:
        d = ImageDraw.Draw(img)
        x, y = brand.SHADOW_BLUR * 2, brand.SHADOW_BLUR
        if label:
            small = graphics.font("bold", brand.PANEL_LABEL_SIZE)
            dot = int(brand.PANEL_LABEL_SIZE * 0.36)
            top = y + int(brand.PANEL_LABEL_SIZE * 0.36)
            d.rectangle([x, top, x + dot, top + dot], fill=brand.LUZ)
            lx = x + dot + 14
            for ch in label.upper():                      # letter spacing, instrument look
                d.text((lx, y), ch, font=small, fill=(244, 246, 248, 175))
                lx += small.getlength(ch) + brand.PANEL_LABEL_SIZE * 0.08
            y += int(brand.PANEL_LABEL_SIZE * 1.45)
            d.line([x, y, x + brand.PANEL_RULE_W, y], fill=(244, 246, 248, 95), width=2)
            y += 8
        big = graphics.font("clock" if CLOCK_RE.match(value) else "number", brand.PANEL_VALUE_SIZE)
        d.text((x - 4, y), display(value), font=big, fill=brand.TEXTO)
        y += int(brand.PANEL_VALUE_SIZE * 1.08)
        if sub:
            if CLOCK_RE.match(sub):
                # small linear stopwatch under the damage number (panel_clock)
                d.text((x, y), sub, font=graphics.font("clock", brand.PANEL_SUB_SIZE), fill=(244, 246, 248, 175))
            else:
                # small normal text, no amber: repeats the number the voice says
                d.text((x, y), sub[:1].upper() + sub[1:], font=graphics.font("text", brand.PANEL_SUB_SIZE),
                       fill=brand.TEXTO)
    graphics.with_shadow(img).save(out)
    return out


def _hud_scrim(slots: int) -> Image.Image:
    """Soft, diffuse dark patch behind the HUD (no card border): on a bright sky, the white text and the amber
    lost contrast. The size applies to the whole scene (slots = maximum rows)."""
    from PIL import ImageFilter
    h = (int(brand.HUD_LABEL_SIZE * 1.4) + 6 + int(brand.HUD_VALUE_SIZE * 1.12) + 10 + slots * brand.HUD_ROW_H
         + brand.SHADOW_BLUR * 2 + 8)
    plate = Image.new("RGBA", (brand.HUD_W, brand.HUD_H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([0, 0, brand.HUD_RULE_W + 150, h], radius=26, fill=(11, 15, 23, 120))
    return plate.filter(ImageFilter.GaussianBlur(16))


def draw_hud(label: str, value: str | None, rows: tuple, out: Path, slots: int | None = None) -> Path:
    """HUD panel: small label, thin line, stopwatch/number and data rows (gray label, amber value on the
    right). Fixed size (the position does not jump between frames)."""
    img = Image.new("RGBA", (brand.HUD_W, brand.HUD_H), (0, 0, 0, 0))
    if value is not None:
        d = ImageDraw.Draw(img)
        x, y = brand.SHADOW_BLUR * 2, brand.SHADOW_BLUR
        if label:
            small = graphics.font("bold", brand.HUD_LABEL_SIZE)
            dot = int(brand.HUD_LABEL_SIZE * 0.36)
            top = y + int(brand.HUD_LABEL_SIZE * 0.36)
            d.rectangle([x, top, x + dot, top + dot], fill=brand.LUZ)
            lx = x + dot + 12
            for ch in label.upper():
                d.text((lx, y), ch, font=small, fill=(244, 246, 248, 175))
                lx += small.getlength(ch) + brand.HUD_LABEL_SIZE * 0.08
            y += int(brand.HUD_LABEL_SIZE * 1.4)
            d.line([x, y, x + brand.HUD_RULE_W, y], fill=(244, 246, 248, 95), width=2)
            y += 6
        big = graphics.font("clock" if CLOCK_RE.match(value) else "number", brand.HUD_VALUE_SIZE)
        d.text((x - 3, y), display(value), font=big, fill=brand.TEXTO)
        y += int(brand.HUD_VALUE_SIZE * 1.12) + 10
        row_label = graphics.font("text", brand.HUD_ROW_LABEL_SIZE)
        row_value = graphics.font("bold", brand.HUD_ROW_VALUE_SIZE)
        right = x + brand.HUD_RULE_W + 60                       # values column, right-aligned
        for k, v in rows:
            d.text((x, y + 2), k, font=row_label, fill=(244, 246, 248, 190))
            d.text((right - row_value.getlength(v), y), v, font=row_value, fill=brand.LUZ)
            y += brand.HUD_ROW_H
    # Without the dark patch of _hud_scrim ("remove that dark part"): only the soft shadow of the text.
    base = Image.new("RGBA", (brand.HUD_W, brand.HUD_H), (0, 0, 0, 0))
    base.alpha_composite(graphics.with_shadow(graphics.with_shadow(img)))     # double shadow: holds the contrast on a bright sky
    base.save(out)
    return out


def layer(label: str, sub: str, sub_at: float, vals: list[str | None], work: Path,
          scene_id: str, rows: tuple = (), style: str = "side", subs: list[str] | None = None) -> tuple[list[str], bool] | None:
    """Builds the scene panel. 'sub_at' (0 to 1) is when the data line comes in (e.g. only at the blackout).
    In "hud" style, 'rows' = ((label, value, when 0 to 1), ...) come in at the given instants.
    Returns the ffmpeg input arguments and whether it is a sequence, or None when the scene has no panel."""
    if all(v is None for v in vals):
        return None
    if style == "hud":
        n = len(vals)
        frames = [(v, tuple((k, val) for k, val, at in rows if i >= int(at * n))) for i, v in enumerate(vals)]
        slots = len(rows)
        draw_fn = lambda lb, v, rws, out: draw_hud(lb, v, rws, out, slots)
    else:
        start = int(sub_at * len(vals))
        frames = [(v, sub if i >= start else "") for i, v in enumerate(vals)]
        if subs:
            # sub per frame (small stopwatch); disappears together with the final word, which closes the panel
            frames = [(v, "" if isinstance(v, FinalWord) else subs[min(i, len(subs) - 1)]) for i, v in enumerate(vals)]
        draw_fn = draw
    if len(set(frames)) == 1:
        png = draw_fn(label, frames[0][0], frames[0][1], work / f"{scene_id}_panel.png")
        # Looped across the whole scene (not a single frame), to allow fade in and out.
        seconds = len(vals) / brand.PANEL_FPS
        return ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{seconds:.3f}", "-i", str(png)], False
    folder = work / f"{scene_id}_panel"
    folder.mkdir(exist_ok=True)
    for old in folder.glob("p_*.png"):
        old.unlink()
    cache: dict[tuple, Image.Image] = {}
    for i, fr in enumerate(frames):
        if fr not in cache:
            draw_fn(label, fr[0], fr[1], folder / "tmp.png")
            cache[fr] = Image.open(folder / "tmp.png").copy()
        cache[fr].save(folder / f"p_{i:04d}.png")
    (folder / "tmp.png").unlink(missing_ok=True)
    return ["-framerate", str(brand.PANEL_FPS), "-i", str(folder / "p_%04d.png")], True
