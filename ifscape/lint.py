"""Script lint: the mechanical checks from the audits, without spending an agent or tokens.

Rules that became code after the study of the viral videos and the audit of the 8 published videos:
- duration stamp ("6 MONTHS", "1 WEEK") only with a source that states the period (it was the most frequent error);
- imperial unit on screen, in the line or in the description (the channel is metric);
- absolute word or "never/only/every" for the `script-review` to look at (warning, may be a false positive);
- at most 2 numbers in the voice per video (evidence from the viral videos; MEDIUM until calibrated);
- `post.txt` with an internal note from `sources` ("OWN CALCULATION", "[SOURCE PENDING]");
- estimated duration outside 61 to 70 s (same computation as `voice`; HIGH above 5% over the target);
- `final_fact` consistent with the rest;
- more than 3 pieces with a number on the same screen, or the same number in two pieces (information audit).

Usage: py -m ifscape lint scripts/<slug>.json
The lint only points things out; the decision belongs to `fact-check`/`script-review`/the owner. Severities: HIGH, MEDIUM, WARNING.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import timing
from .script import Script
from .util import ROOT

IMPERIAL = re.compile(r"\b(gallons?|inch(?:es)?|feet|foot|miles?|mph|pounds?|ounces?|yards?|fahrenheit|psi)\b|°\s?F\b", re.I)
ABSOLUTE = re.compile(r"\b(every|everyone|everything|any|anyone|only|never|always|nobody|no one|nowhere)\b", re.I)
NUMBER = re.compile(r"\d[\d,\.]*")
FIXED_STAMPS = {"NOW", "TODAY", "UNTESTED"}          # not durations: NOW is the stopwatch; the others are labels
UNIT_WORDS = {"SECOND": "second", "SECONDS": "second", "MIN": "minute", "HOUR": "hour", "HOURS": "hour",
              "DAY": "day", "DAYS": "day", "WEEK": "week", "WEEKS": "week", "MONTH": "month", "MONTHS": "month",
              "YEAR": "year", "YEARS": "year"}
WEAK_SOURCE = re.compile(r"unverified|own calculation|editorial|no source|pending", re.I)
INTERNAL_POST = ("OWN CALCULATION", "[SOURCE PENDING]")
INTERNAL_MARK = "INTERNAL (do not paste)"             # render.py splits post.txt into PASTE INTO POST and INTERNAL
TITLE_LINE_MAX = 22                                     # characters per title line (2 balanced lines)


TITLE_PX_MAX = 980                                      # px of the widest line of the video title (1080 screen)


def _title_px(text: str):
    """Real width of the widest title line, with the same font and the same wrap as the render (cover._title).
    Returns (px, line) or None if it cannot measure (missing font)."""
    try:
        from . import cover, graphics
        f = graphics.font("bold", cover.TITLE_SIZE)
        words = text.split()
        space = f.getlength(" ")
        lines = graphics._balanced_lines(words, [f.getlength(w) for w in words], space, cover.TITLE_MAX_W)
        wide = max((" ".join(line) for line in lines), key=lambda s: f.getlength(s))
        return f.getlength(wide), wide
    except Exception:
        return None


def _title_lines(text: str) -> tuple[str, str]:
    """Breaks by words into 2 balanced lines (estimate of the render's wrap)."""
    words = text.split()
    best = (text, "")
    best_w = len(text)
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if max(len(a), len(b)) < best_w:
            best, best_w = (a, b), max(len(a), len(b))
    return best


def _screen_findings(sc: Script) -> list[tuple[str, str]]:
    """On-screen text: a scene with on_screen ignores `text`; wide title; counter/panel outside the limits."""
    found: list[tuple[str, str]] = []
    titles = [(f"scene {s.id}", s.on_screen) for s in sc.scenes if s.on_screen] + [("title", sc.title)]
    for s in sc.scenes:
        if s.on_screen and len(s.lines) > 1:
            found.append(("HIGH", f"scene {s.id}: has `on_screen` and `text` with {len(s.lines)} lines; the render only shows the "
                                  "on_screen on the whole scene and the other sentences disappear. Put them in a scene of their own."))
    for where, t in titles:
        if "\n" in t:
            found.append(("HIGH", f"{where}: '\\n' in the title is ignored by the render; the break is automatic."))
        if where == "title":
            continue                                        # the post title is not drawn on screen
        wide = _title_px(t.replace("\n", " "))
        if wide is not None and wide[0] > TITLE_PX_MAX:
            found.append(("HIGH", f"{where}: the widest title line measures {wide[0]:.0f} px (> {TITLE_PX_MAX}, the screen is 1080) "
                                  f"and overflows the edges: \"{wide[1]}\". Use shorter words (e.g. 'human-sized')."))
        elif wide is None:
            a, b = _title_lines(t.replace("\n", " "))
            if max(len(a), len(b)) > TITLE_LINE_MAX:
                found.append(("HIGH", f"{where}: title in 2 lines of {len(a)} and {len(b)} characters (> {TITLE_LINE_MAX}) "
                                      f"may overflow the edges: \"{a}\" / \"{b}\". Use shorter words."))
    for s in sc.scenes:
        c = s.counter
        if c and len(c.unit) > 8:
            found.append(("MEDIUM", f"scene {s.id}: counter.unit '{c.unit}' with more than 8 characters (cut off on screen)."))
        for k, v, *_ in s.panel_rows:
            if len(str(v)) > 14 or len(str(k)) > 26:
                found.append(("MEDIUM", f"scene {s.id}: panel_rows '{k}': '{v}' (value > 14 or label > 26 characters)."))
    raw_path = ROOT / "scripts" / f"{sc.slug}.json"
    if raw_path.exists():
        try:
            import json
            for raw in json.loads(raw_path.read_text(encoding="utf-8")).get("scenes", []):
                rc = raw.get("counter") or {}
                vals = [rc.get("start"), rc.get("end")]
                if not rc.get("decimals") and any(isinstance(v, float) and v != int(v) for v in vals) or \
                        (not rc.get("decimals") and isinstance(rc.get("end"), (int, float)) and 0 < rc["end"] < 1):
                    found.append(("MEDIUM", f"scene {raw.get('id')}: counter with a decimal value or end < 1; the counter only shows "
                                           "inteiros (use outra unidade, ex. '2,665,928 x')."))
        except (ValueError, OSError):
            pass
    return found


MAX_NUMBERS_ON_SCREEN = 3                               # counter + 1 panel line + 1 card or sentence


def _density_findings(sc: Script) -> list[tuple[str, str]]:
    """Numbers on the same screen (information audit): scene 02 showed 4,900,000x, x28,900,
    9X, 33 TIMES and '50 times' together, with no reading order. One screen = one main message."""
    found: list[tuple[str, str]] = []
    for s in sc.scenes:
        items = []                                          # (element, numbers) of each piece the audience reads
        if s.counter:
            items.append(("contador", {str(s.counter.end)}))
        items += [(f"panel '{k}'", set(NUMBER.findall(str(v)))) for k, v, *_ in s.panel_rows]
        if s.fact:
            items.append(("card", set(NUMBER.findall(f"{s.fact.get('value', '')} {s.fact.get('text', '')}"))))
        items += [("frase", set(NUMBER.findall(line))) for line in s.lines]
        with_numbers = [(name, nums) for name, nums in items if nums]
        if len(with_numbers) > MAX_NUMBERS_ON_SCREEN:
            names = ", ".join(name for name, _ in with_numbers)
            found.append(("HIGH", f"scene {s.id}: {len(with_numbers)} pieces with a number on the same screen ({names}); maximum "
                                  f"{MAX_NUMBERS_ON_SCREEN}. One screen = one main message: move numbers to another scene."))
        norm = lambda n: n.replace(",", "").rstrip(".")
        seen: dict[str, str] = {}
        for name, nums in with_numbers:
            for n in nums:
                key = norm(n)
                if len(key) >= 3 and key in seen and seen[key] != name:
                    found.append(("MEDIUM", f"scene {s.id}: the number {n} appears in '{seen[key]}' and in '{name}' at the same time "
                                           "(repeating does not inform; keep it in one place)."))
                seen.setdefault(key, name)
    return found


def _flat_findings(sc: Script) -> list[tuple[str, str]]:
    """2D series ('flat' field): validate already rejects a wrong field on load; here only what is content.
    Card with a digit needs 'source' in the block (spec: no number without a source); karaoke without voice does not show."""
    found: list[tuple[str, str]] = []
    for s in sc.scenes:
        flat = s.flat or {}
        for i, b in enumerate(flat.get("blocks", [])):
            if NUMBER.search(f"{b.get('value', '')} {b.get('note', '')}") and not str(b.get("source", "")).strip():
                found.append(("MEDIUM", f"scene {s.id}: card block {i + 1} has a number ('{b.get('value')}') without 'source'; "
                                       "a number on the card only with a source."))
    if sc.caption_style == "karaoke" and sc.format == "text":
        found.append(("WARNING", "'caption_style': 'karaoke' only applies with voice (format voice); in text format the normal caption stays."))
    return found


def _texts(sc: Script) -> list[tuple[str, str]]:
    """(where, text) of everything the audience reads or hears, scene by scene, plus description and end card."""
    out: list[tuple[str, str]] = []
    for s in sc.scenes:
        where = f"scene {s.id}"
        out += [(where, s.narration), (where, s.on_screen), (where, s.panel_sub), (where, s.stamp or "")]
        out += [(where, line) for line in s.lines]
        if s.fact:
            out += [(where, f"{s.fact.get('value', '')} {s.fact.get('text', '')}")]
        if s.counter:
            out += [(where, f"{s.counter.label} {s.counter.unit}")]
        out += [(where, f"{k} {v}") for k, v, *_ in s.panel_rows]
        out += [(where, f"{b.get('label', '')} {b.get('value', '')} {b.get('note', '')}")
                for b in (s.flat or {}).get("blocks", [])]
        out += [(where, f"{c.get('label', '')} {c.get('value', '')}") for c in s.chip]
    out += [("description", sc.description), ("final_fact", sc.final_fact), ("closing", sc.closing)]
    return [(w, t) for w, t in out if t and t.strip()]


def _stamp_findings(sc: Script) -> list[tuple[str, str]]:
    found, seen = [], set()
    for s in sc.scenes:
        stamp = (s.stamp or "").strip()
        if not stamp or stamp.upper() in FIXED_STAMPS or stamp.upper() in seen:
            continue
        seen.add(stamp.upper())
        words = {UNIT_WORDS[w] for w in re.findall(r"[A-Z]+", stamp.upper()) if w in UNIT_WORDS}
        decade = re.findall(r"\d{4}", stamp)
        if not words and not decade:
            if stamp.strip().upper() in ("SOON", "LATER"):
                found.append(("HIGH", f"scene {s.id}: stamp '{stamp}' tells nothing. A stamp only with important information "
                                      "(a period with a source, a date, 'NOW'); without that, remove the stamp (stamp: null) and the panel disappears."))
            continue                                   # label without a period
        key = list(words) + decade
        number = re.match(r"[\d,]+", stamp)
        digits = number.group(0).replace(",", "") if number else ""

        def _supports(claim: str) -> bool:
            text = claim.lower().replace(",", "")
            if decade:
                return any(d in text for d in decade)
            has_unit = any(w in text for w in words)
            # 1 YEAR / 1 DAY accept "a year", "within a day"; the others require the number itself
            return has_unit and (digits in ("", "1") or re.search(r"(?<!\d)" + digits + r"(?!\d)", text) is not None)

        support = [src for src in sc.sources if _supports(str(src.get("claim", "")))]
        if not support:
            found.append(("HIGH", f"scene {s.id}: stamp '{stamp}' without a source that states the period (no claim in "
                                  f"`sources` cites {', '.join(key)}). Without a study, remove the stamp (stamp: null): the panel disappears."))
        elif all(not src.get("url") for src in support) or all(WEAK_SOURCE.search(src.get("claim", "")) for src in support):
            found.append(("HIGH", f"scene {s.id}: stamp '{stamp}' only has a source without a URL or marked as an own "
                                  "estimate/UNVERIFIED."))
    return found


def lint(sc: Script, post_path: Path | None = None) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    findings += _stamp_findings(sc)

    for where, text in _texts(sc):
        for m in IMPERIAL.finditer(text):
            findings.append(("HIGH", f"{where}: imperial unit '{m.group(0)}' in \"{text[:70]}\" (the channel is metric)"))
        for m in ABSOLUTE.finditer(text):
            findings.append(("WARNING", f"{where}: absolute word '{m.group(0)}' in \"{text[:70]}\" "
                                      "(check that the fact sheet has that scope)"))

    if sc.format == "voice":
        spoken = [n for s in sc.scenes for n in NUMBER.findall(s.narration)]
        if len(spoken) > 2:
            findings.append(("MEDIUM", f"{len(spoken)} numbers in the voice ({', '.join(spoken[:6])}...): the maximum is 2; "
                                      "the rest goes to the panel, sub-line or card"))

    if sc.format == "voice":
        model = sc.voice_model or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        seconds, words = timing.estimate_total(sc.scenes, model)
        lo, hi = timing.TARGET_SECONDS
        if seconds > hi * 1.05:
            findings.append(("HIGH", timing.budget_line(seconds, words, model) + " (the voice refuses above 5%)"))
        elif seconds < 60:
            findings.append(("HIGH", timing.budget_line(seconds, words, model) + " (TikTok only pays for videos over 60 s)"))
        elif not lo <= seconds <= hi:
            findings.append(("MEDIUM", timing.budget_line(seconds, words, model)))

    # "In our world" abolished: the real fact closes in final_fact, without the frame.
    texts = [sc.final_fact or ""] + [t for s in sc.scenes for t in (s.narration, s.on_screen, *s.lines)]
    if any(re.search(r"in our world", t or "", re.I) for t in texts):
        findings.append(("HIGH", "'In our world' in the line or on screen: abolished; the real fact goes straight in final_fact"))

    findings += _screen_findings(sc)
    findings += _density_findings(sc)
    findings += _flat_findings(sc)

    post = post_path or (ROOT / "out" / f"{sc.slug}.post.txt")
    if post.exists():
        body = post.read_text(encoding="utf-8")
        paste = body.partition(INTERNAL_MARK)[0]                 # the internal note can only stay in the INTERNAL block
        for token in INTERNAL_POST:
            if token in paste:
                findings.append(("HIGH", f"{post.name} contains internal note '{token}' in the PASTE INTO POST block: do not paste it"))
    return findings


def show(sc: Script, post_path: Path | None = None) -> int:
    findings = lint(sc, post_path)
    order = {"HIGH": 0, "MEDIUM": 1, "WARNING": 2}
    findings.sort(key=lambda f: order[f[0]])
    if not findings:
        print("\nLint: nada a apontar.")
        return 0
    print(f"\nLint ({len(findings)}): the lint only points things out; the decision belongs to fact-check, script-review and the owner.")
    for sev, msg in findings:
        print(f"  [{sev}] {msg}")
    return 1 if any(sev == "HIGH" for sev, _ in findings) else 0
