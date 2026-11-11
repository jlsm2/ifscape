"""Draws caption, handle, end card and placeholder card as PNG ("Instrument" identity).
The live panel is in panel.py."""

from functools import lru_cache
from pathlib import Path
import textwrap

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

from . import brand
from .timing import WEAK_WORDS

_warned = set()
_KINDS = {"text": brand.FONT_TEXT, "bold": brand.FONT_BOLD, "number": brand.FONT_NUMBER, "clock": brand.FONT_CLOCK}


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    """kind: 'text' (sentences), 'bold' (question, label, card), 'number' (panel number) or 'clock' (stopwatch)."""
    path = brand.FONTS_DIR / _KINDS[kind]
    if path.exists():
        f = ImageFont.truetype(str(path), size)
        if kind == "clock":
            f.set_variation_by_axes([brand.FONT_CLOCK_WEIGHT])
        return f
    for fb in brand.FONT_FALLBACKS:
        if Path(fb).exists():
            if kind not in _warned:
                print(f"  warning: brand font {path.name} is not in fonts/; using {Path(fb).name} for testing only")
                _warned.add(kind)
            return ImageFont.truetype(fb, size)
    return ImageFont.load_default(size)


def with_shadow(img: Image.Image) -> Image.Image:
    """Soft shadow under what was drawn (text readable without a hard outline)."""
    alpha = img.getchannel("A")
    shadow = Image.new("RGBA", img.size, brand.VACUO)
    shadow.putalpha(alpha.point(lambda a: int(a * brand.SHADOW_ALPHA)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(brand.SHADOW_BLUR))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(shadow, (0, brand.SHADOW_OFFSET))
    base.alpha_composite(img)
    return base


def handle(out: Path) -> Path:
    f = font("text", brand.HANDLE_SIZE)
    pad = brand.SHADOW_BLUR * 2
    w = int(f.getlength(brand.HANDLE_TEXT) + 2 * pad)
    h = int(sum(f.getmetrics()) + 2 * pad)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad, pad), brand.HANDLE_TEXT, font=f, fill=(244, 246, 248, 215))
    with_shadow(img).save(out)
    return out


_PUNCT = ".,!?;:\"'"


def _clean(word: str) -> str:
    return word.upper().strip(_PUNCT)


def _line_count(widths: list[float], space: float, max_w: float) -> int:
    """How many lines the greedy wrap needs to fit in max_w."""
    count, line_w = 1, 0.0
    for i, ww in enumerate(widths):
        extra = ww if line_w == 0 else line_w + space + ww
        if i and line_w and extra > max_w:
            count, line_w = count + 1, ww
        else:
            line_w = extra
    return count


def _balanced_lines(words: list[str], widths: list[float], space: float, max_w: float) -> list[list[str]]:
    """Splits into lines of similar width (the widest as small as possible), with no orphan word."""
    n = min(_line_count(widths, space, max_w), len(words))

    def width(i: int, j: int) -> float:
        return sum(widths[i:j]) + space * (j - i - 1)

    weak_penalty = max_w * 0.35            # line ending in "THE", "ON", "OF"... only if there is no way around it

    def best(start: int, lines_left: int) -> tuple[float, list[int]]:
        if lines_left == 1:
            return width(start, len(words)), [len(words)]
        result = (float("inf"), [])
        for cut in range(start + 1, len(words) - lines_left + 2):
            rest_w, rest_cuts = best(cut, lines_left - 1)
            line_w = width(start, cut)
            if line_w > max_w:
                continue
            ends_weak = words[cut - 1].lower().strip(_PUNCT) in WEAK_WORDS
            candidate = (max(line_w, rest_w) + (weak_penalty if ends_weak else 0), [cut, *rest_cuts])
            if candidate[0] < result[0]:
                result = candidate
        return result

    cuts = [0, *best(0, n)[1]]
    return [words[a:b] for a, b in zip(cuts, cuts[1:])]


def caption(text: str, highlight: list[str], out: Path, size: int | None = None, max_w: int | None = None,
            kind: str = "text", scrim: bool = False) -> Path:
    """Centered sentence, in mixed case as written in the script, with a soft shadow; 'highlight' words
    come out painted amber. "Instrument" identity: no all-caps and no hard outline."""
    size = size or brand.CAPTION_SIZE
    max_w = max_w or brand.CAPTION_MAX_W
    f = font(kind, size)
    words = text.split()
    space = f.getlength(" ")
    pad = brand.SHADOW_BLUR * 2
    lines = _balanced_lines(words, [f.getlength(w) for w in words], space, max_w)

    ascent, descent = f.getmetrics()
    line_h = int((ascent + descent) * 1.08)
    width = max_w + 2 * pad
    height = line_h * len(lines) + 2 * pad
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = pad
    for words_in_line in lines:
        total = sum(f.getlength(w) for w in words_in_line) + space * (len(words_in_line) - 1)
        x = (width - total) / 2
        for w in words_in_line:
            if _clean(w) in highlight:
                core = w.rstrip(_PUNCT)          # final punctuation stays white, like the rest of the sentence
                draw.text((x, y), core, font=f, fill=brand.LUZ)
                draw.text((x + f.getlength(core), y), w[len(core):], font=f, fill=brand.TEXTO)
            else:
                draw.text((x, y), w, font=f, fill=brand.TEXTO)
            x += f.getlength(w) + space
        y += line_h

    out_img = with_shadow(img)
    if scrim:
        # Soft dark gradient behind the text, only on a bright scene (noon sky, snow, moonlight in the final call):
        # canvas at screen width and with vertical slack (otherwise the blur is cut flush with the text and becomes a box).
        W, m = brand.W, 150
        canvas = Image.new("RGBA", (W, height + 2 * m), (0, 0, 0, 0))
        band = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(band).rounded_rectangle(
            [(W - max_w) // 2 - 10, m + pad // 2, (W + max_w) // 2 + 10, m + height - pad // 2], radius=90,
            fill=int(255 * 0.42))
        band = band.filter(ImageFilter.GaussianBlur(60))
        dark = Image.new("RGBA", canvas.size, brand.VACUO)
        dark.putalpha(band)
        canvas.alpha_composite(dark)
        canvas.alpha_composite(out_img, ((W - width) // 2, m))
        out_img = canvas
    out_img.save(out)
    return out


def karaoke_lines(text: str) -> tuple[ImageFont.FreeTypeFont, list[list[tuple[str, float]]]]:
    """Fixed layout of a chunk: lines of (word, x). All the variants of the chunk use the same one, so the
    words do not move when the box passes from one to the other. One line, as in style_v4; it only breaks into 2
    when the chunk exceeds KARAOKE_MAX_W (otherwise it would invade the button strip, x > 930)."""
    f = font("number", brand.KARAOKE_SIZE)
    words = [w.upper() for w in text.split()]
    sp = f.getlength(" ")
    lines = _balanced_lines(words, [f.getlength(w) for w in words], sp, brand.KARAOKE_MAX_W)
    placed = []
    for line in lines:
        total = sum(f.getlength(w) for w in line) + sp * (len(line) - 1)
        x = brand.W / 2 - total / 2
        row = []
        for w in line:
            row.append((w, x))
            x += f.getlength(w) + sp
        placed.append(row)
    return f, placed


def karaoke(text: str, active: int, out: Path) -> Path:
    """Karaoke caption (drawing from tools/flat2d/style_v4.py, karaoke(), with the
    same values): chunk of 1 to 4 words in caps, Barlow SemiCondensed 84; the 'active' word (index
    in the chunk; -1 = none) is amber (the word changes color, no box), the others in
    white; all with a 6 px Vacuum outline. Image at screen width, with the center of the 1st line at KARAOKE_MARGIN + 56: the render
    only positions it in y."""
    f, placed = karaoke_lines(text)
    top, bottom = brand.KARAOKE_BOX
    m = brand.KARAOKE_MARGIN
    line_h = brand.KARAOKE_LINE_H
    img = Image.new("RGBA", (brand.W, m * 2 + top + bottom + line_h * (len(placed) - 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = 0
    for i, row in enumerate(placed):
        y = m + top + i * line_h
        for w, x in row:
            d.text((x, y), w, font=f, fill=brand.LUZ if k == active else brand.TEXTO, anchor="lm",
                   stroke_width=brand.KARAOKE_STROKE, stroke_fill=brand.VACUO)
            k += 1
    img.save(out)
    return out


def fact_card(value: str, text: str, out: Path) -> Path:
    """Fact card: no background, amber bar on the left, amber number (optional)
    and the sentence. No source in the image and no shadow: the background already separates it from the set. Back to the original
    design, ~15% smaller (the lean version did not work)."""
    pad, bar = 24, 6
    inner = brand.FACT_W - 2 * pad - bar - 12
    f_val, f_txt = font("number", brand.FACT_VALUE_SIZE), font("text", brand.FACT_TEXT_SIZE)
    words = text.split()
    lines = [" ".join(l) for l in _balanced_lines(words, [f_txt.getlength(w) for w in words], f_txt.getlength(" "), inner)]
    line_h = int(brand.FACT_TEXT_SIZE * 1.2)
    val_h = int(brand.FACT_VALUE_SIZE * 1.05) if value else 0
    height = pad + val_h + line_h * len(lines) + pad
    img = Image.new("RGBA", (brand.FACT_W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(pad - 6, pad), (pad - 6 + bar, height - pad)], radius=3, fill=brand.LUZ)
    x, y = pad + bar + 6, pad
    if value:
        d.text((x, y), value, font=f_val, fill=brand.LUZ)
        y += val_h
    for line in lines:
        d.text((x, y), line, font=f_txt, fill=brand.TEXTO)
        y += line_h
    with_shadow(img).save(out)      # no dark background: only the soft shadow separates it from the set
    return out


def final_fact_card(text: str, out: Path) -> Path:
    """1-line end card (final_fact): the real fact in small, spaced small caps, centered, with a soft
    shadow. Up to 2 lines at width FINAL_FACT_MAX_W. It sits in the pause before the question, outside the panel strip."""
    f = font("bold", brand.FINAL_FACT_SIZE)
    track = brand.FINAL_FACT_SIZE * 0.08

    def width(word: str) -> float:
        return sum(f.getlength(ch) + track for ch in word)

    words = text.upper().split()
    lines = [" ".join(l) for l in _balanced_lines(words, [width(w) for w in words], width(" "), brand.FINAL_FACT_MAX_W)]
    pad = brand.SHADOW_BLUR * 2
    line_h = int(brand.FINAL_FACT_SIZE * 1.5)
    img = Image.new("RGBA", (brand.FINAL_FACT_MAX_W + 2 * pad, line_h * len(lines) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for line in lines:
        x = (img.width - width(line)) / 2
        for ch in line:
            d.text((x, y), ch, font=f, fill=(244, 246, 248, 205))
            x += f.getlength(ch) + track
        y += line_h
    with_shadow(img).save(out)
    return out


def end_card(fact: str, cta: str, out: Path) -> Path:
    """End card on Vacuum: the fact sentence (the twist) and the call in amber. '|' in the text forces a line
    break (the automatic break separated "the last" from "human face" in QA)."""
    img = Image.new("RGBA", (brand.W, brand.H), brand.VACUO)
    draw = ImageDraw.Draw(img)
    big = font("bold", brand.END_FACT_SIZE)
    if not fact:
        # Only the question, in the center and at the size of the fact sentence.
        draw.text((brand.W / 2, brand.H // 2 - 60), cta, font=big, fill=brand.LUZ, anchor="mm")
        img.save(out)
        return out
    if "|" in fact:
        lines = [part.strip() for part in fact.split("|")]
    else:
        words = fact.split()
        lines = [" ".join(line) for line in
                 _balanced_lines(words, [big.getlength(w) for w in words], big.getlength(" "), brand.TEXT_CAPTION_MAX_W)]
    line_h = int(brand.END_FACT_SIZE * 1.18)
    y = brand.H // 2 - 60 - line_h * len(lines) // 2
    for line in lines:
        draw.text((brand.W / 2, y), line, font=big, fill=brand.TEXTO, anchor="mt")
        y += line_h
    draw.text((brand.W / 2, y + 60), cta, font=font("bold", brand.END_CTA_SIZE), fill=brand.LUZ, anchor="mt")
    img.save(out)
    return out


def placeholder(scene_id: str, prompt: str, seconds: float, out: Path) -> Path:
    """Card in place of a clip that does not exist yet, to review the assembly before generating."""
    img = Image.new("RGB", (brand.W, brand.H), brand.NEVOA)
    draw = ImageDraw.Draw(img)
    big = font("bold", 110)
    small = font("text", 34)
    # Sits below the handle (HANDLE_XY) and the caption strip, so as not to collide with either.
    draw.text((72, 1520), f"Cena {scene_id}", font=big, fill=brand.QUIETO)
    draw.text((72, 1655), f"clipe pendente · {seconds:.1f} s", font=small, fill=brand.LUZ)
    y = 1710
    for line in textwrap.wrap(prompt, width=48)[:4]:
        draw.text((72, y), line, font=small, fill=brand.QUIETO)
        y += 46
    img.save(out)
    return out

