"""Palette, fonts and easing of the 2D system (values from the approved prototype, style_v3.py)."""

import math
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"

S = 2                          # supersample: draws at 2160x3840 and downsizes with LANCZOS
W, H = 1080, 1920              # = brand.W, brand.H (without importing ifscape here: the module stays independent)
FPS = 30

VAC = (11, 15, 23)             # brand.VACUO
AMB = (245, 165, 36)           # brand.LUZ
AMB_D = (120, 82, 24)          # muted amber: dimension lines, shelves, street
TXT = (244, 246, 248)          # brand.TEXTO
QUI = (138, 148, 166)          # brand.QUIETO
INF = (96, 120, 150)           # infected heat blob
INF_DOT = (170, 190, 215)      # infected dot
GRID = (18, 24, 34)            # technical paper grid
LIT = (22, 21, 20)             # floor with the light on (slight warmth over the Vacuum)
WARM = (70, 62, 58)            # warm outline of the close

FONT_NUMBER = "BarlowSemiCondensed-SemiBold.ttf"
FONT_BOLD = "Barlow-SemiBold.ttf"


@lru_cache(maxsize=None)
def font(size: float, name: str = FONT_NUMBER, scale: int = S) -> ImageFont.FreeTypeFont:
    """Font in px of the final frame (1080x1920); scale=S to draw on the enlarged frame."""
    return ImageFont.truetype(str(FONTS / name), int(size * scale))


def P(v: float) -> int:
    """Final frame coordinate -> enlarged frame."""
    return int(round(v * S))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def smooth(x: float) -> float:
    """Smoothstep: every movement eases in and out (nothing jumps)."""
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, u: float):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u


def mix(c1: tuple, c2: tuple, u: float) -> tuple:
    return tuple(int(round(x + (y - x) * u)) for x, y in zip(c1, c2))


def noise(seed: float, t: float) -> float:
    """Smooth deterministic noise in -1..1 (sum of sines): basis of the flicker and of the infected's drift."""
    return (math.sin(t * 1.7 + seed * 12.9) * 0.6 + math.sin(t * 3.1 + seed * 7.3) * 0.3
            + math.sin(t * 7.9 + seed * 3.1) * 0.1)
