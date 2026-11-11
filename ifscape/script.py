"""Reading and validating the JSON script."""

import json
from dataclasses import dataclass, field
from pathlib import Path

_MISSING = object()


@dataclass(frozen=True)
class Counter:
    """Live panel counter: climbs slowly and changes at one instant (e.g. world population -> 0)."""
    label: str
    start: float        # value at the start of the scene
    end: float          # value after the change
    rate: float         # how much it climbs per second before the change
    change_at: float    # second of the scene at which the change starts
    change_over: float  # how long the change lasts
    unit: str = ""      # word after the number ("trillion" -> "38 trillion"); disappears at zero
    final: str = ""     # word in place of the number when the change ends ("HERE", "GONE"); empty = the number stays
    decimals: int = 0   # decimal places of the number (gravity-doubled: 9.81 m/s²); 0 = integer
_COUNTER_KEYS = {"label", "start", "end", "rate", "change_at", "change_over", "unit", "final", "decimals"}


def _counter(sid: str, raw: dict | None) -> Counter | None:
    if not raw:
        return None
    missing = {"start", "end", "change_at"} - raw.keys()
    unknown = raw.keys() - _COUNTER_KEYS
    if missing or unknown:
        raise ValueError(f"Scene {sid}: 'counter' needs {sorted(missing)}" if missing
                         else f"Scene {sid}: 'counter' does not know {sorted(unknown)}")
    dec = int(raw.get("decimals", 0))
    num = float if dec else int
    return Counter(label=str(raw.get("label", "")), start=num(raw["start"]), end=num(raw["end"]), decimals=dec,
                   rate=float(raw.get("rate", 0.0)), change_at=float(raw["change_at"]),
                   change_over=float(raw.get("change_over", 1.0)), unit=str(raw.get("unit", "")).lower(),
                   final=str(raw.get("final", "")).strip().upper())
TOOLS = ("seedance", "veo")
FORMATS = ("voice", "text")


def _join(text: str, suffix: str) -> str:
    return f"{text}, {suffix}" if suffix else text


@dataclass
class Scene:
    id: str
    prompt: str                # first-frame image (or direct video, if there is no motion)
    style: str
    narration: str
    on_screen: str
    stamp: str | None          # effective stamp in this scene (already with the "carried" one from the previous)
    highlight: list[str]
    min_seconds: float
    motion: str = ""           # motion to animate the image; empty = direct video from the prompt
    motion_style: str = ""
    tool: str = "seedance"     # where to generate the video: seedance or veo
    captions: tuple[str, ...] = ()  # caption breaks written by hand; empty = automatic break
    lines: tuple[str, ...] = ()     # "text" format: whole sentences shown one at a time, no narration
    panel_label: str = ""           # small label of the live panel ("TIME WITHOUT HUMANS"), carried between scenes
    panel_sub: str = ""             # data line under the number, only in this scene ("SUBWAY PUMPS: OFF")
    panel_sub_at: float = 0.0       # at what point of the scene (0 to 1) the data line comes in
    counter: Counter | None = None  # counter that climbs and changes at one instant (e.g. population -> 0)
    scrim: bool = False             # soft dark gradient behind the caption, only on a bright scene
    direction: str | None = None    # voice direction tag for this scene only ("[quiet, final tone]"); None = the script's, "" = no tag
    claims: tuple[str, ...] = ()    # IDs of the build/<slug>/facts.md entries the line uses ("F4", "FIN-A")
    panel_rows: tuple = ()          # "hud" style: ((label, value, when 0 to 1), ...) data lines under the number
    fade_in: float = 0.0            # soft cut: the scene video rises from black in N seconds (background only, the text stays)
    fade_out: float = 0.0           # same, drops to black at the end of the scene
    fact: dict | None = None        # fact card: {value, text, source, t, dur} (render.py, graphics.fact_card)
    stage: dict | None = None       # data-driven 3D stage (tools/stage/build.py): set, light, props, camera, cues
    flat: dict | None = None        # data-driven 2D set (tools/flat2d): shot plan/close/card, place, actors, events
    clock: dict | bool | None = None  # 2D HUD: {day, from, to}; None = continues the previous scene's; False = hides it
    chip: tuple = ()                # 2D HUD: info chips that come in and out ({label, value, at, for, level})

    @property
    def caption_text(self) -> str:
        return self.on_screen or self.narration

    @property
    def full_prompt(self) -> str:
        return _join(self.prompt, self.style)

    @property
    def full_motion(self) -> str:
        return _join(self.motion, self.motion_style) if self.motion else ""


@dataclass
class Script:
    slug: str
    channel: str
    title: str
    description: str
    sources: list[dict]
    hashtags: list[str]
    scenes: list[Scene] = field(default_factory=list)
    format: str = "voice"          # "voice" (narration) or "text" (on-screen text only, music added on the platform)
    end_card: str = ""             # fact line of the end card (empty with end_card: true = just the question)
    show_end_card: bool = False    # text format: the final question becomes a full-screen card
    sfx: dict = field(default_factory=dict)   # efeitos sonoros: sfx, ambience, sfx_traffic, sfx_panel (sfx.py)
    credit: str = ""               # @ of the follower who asked for the topic; appears in the pause before the final question
    final_fact: str = ""           # 1-line end card (up to 16 words) in the pause before the final question; voice format
    panel_clock: bool = False      # scene with 'counter': small linear stopwatch under the damage number
    panel_clock_from: float = 0.0  # second of the video at which the small stopwatch reads zero
    now_clock: bool = True         # "NOW" stamp is a stopwatch going up ("00:02.10"); false goes back to seconds spelled out
    now_clock_from: float = 0.0    # second of the "NOW" segment at which the stopwatch reads zero
    closing: str = ""              # final sentence that gets the 2 s pause before it (empty = "What should I imagine next?")
    voice_model: str = ""          # ElevenLabs model for this script only (e.g. "eleven_v4"); empty = ELEVENLABS_MODEL from .env
    panel_style: str = "side"       # "side" (default, middle of the screen) or "hud" (top, compact, with data lines)
    voice_direction: str = ""    # voice direction tag for all narrated scenes (v3/v4 only), e.g. "[calm, dry documentary narration]"
    voice_stability: float | None = None  # ElevenLabs stability for this script only; empty = 0.5
    master_lufs: float | None = None      # integrated loudness of the final mp4; None = no normalization (see _master_lufs)
    caption_style: str = "default"  # "karaoke": word-by-word caption with an amber box on the spoken word (voice only)
    panel: bool = True              # false: no panel/stamp and no title in the whole video (2D series)
    cast: dict = field(default_factory=dict)   # cast of the 2D series: {id: resolved visual} (tools/flat2d/cast.py)


def _direction(raw, where: str) -> str | None:
    """Voice direction tag: text in square brackets, or "" to turn it off in the scene. None = not given."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text and not (text.startswith("[") and text.endswith("]") and text.count("[") == 1 and text.count("]") == 1):
        raise ValueError(f"{where}: the voice direction must be a tag in square brackets, like '[calm, dry narration]'.")
    return text


MASTER_LUFS_VOICE = -16.0   # default of the voice format: the first 6 videos came out at -21 to -24


def _master_lufs(data: dict, fmt: str) -> float | None:
    """'master_lufs': number = target; false = no normalization. Absent: -16 with voice; text-only stays as it comes out
    (at -16 the effects sounded too loud on Instagram)."""
    raw = data.get("master_lufs", MASTER_LUFS_VOICE if fmt == "voice" else False)
    if raw is False or raw is None:
        return None
    value = float(raw)
    if not -30.0 <= value <= -9.0:
        raise ValueError(f"'master_lufs' outside the reasonable range (-30 to -9): {value}")
    return value


def _credit(raw) -> str:
    """'credit': the @ of whoever suggested the topic ("@username")."""
    credit = str(raw or "").strip()
    if credit and (not credit.startswith("@") or len(credit.split()) != 1):
        raise ValueError(f"'credit' must be a single @, like '@username', not '{credit}'.")
    return credit


def _final_fact(raw) -> str:
    """'final_fact': 1 line of fact (the real fact written out), up to 16 words, shown in the final pause."""
    text = str(raw or "").strip()
    if len(text.split()) > 16:
        raise ValueError(f"'final_fact' has {len(text.split())} words; the maximum is 16.")
    return text


def _end_card_text(raw) -> str:
    """'end_card': text of the fact sentence, or true for a card with just the final question."""
    if raw is True or raw is False or raw is None:
        return ""
    if not isinstance(raw, str):
        raise ValueError("'end_card' must be text or true.")
    return raw.strip()


_TOP_KEYS = {"slug", "channel", "title", "description", "sources", "hashtags", "scenes", "style", "format", "motion_style",
             "panel_label", "panel_style", "end_card", "sfx", "ambience", "sfx_traffic", "sfx_panel", "sfx_lufs", "sfx_auto", "credit", "closing",
             "final_fact", "panel_clock", "panel_clock_from", "now_clock", "now_clock_from", "voice_model", "voice_direction", "voice_stability", "master_lufs",
             "caption_style", "panel", "cast"}
_SCENE_KEYS = {"id", "prompt", "style", "narration", "on_screen", "highlight", "min_seconds", "motion", "motion_style",
               "tool", "captions", "text", "stamp", "panel_label", "panel_sub", "panel_sub_at", "panel_rows", "counter", "scrim",
               "direction", "claims", "stage", "fact", "fade_in", "fade_out",
               "flat", "clock", "chip"}


def _fact(sid: str, raw, style: str) -> dict | None:
    """Fact card: {text, value?, t?, dur?, source?}. The source is internal control only: it does not appear in the video.
    With the side panel ('side') the card sits at the top, on the left (brand.FACT_XY_SIDE)."""
    if not raw:
        return None
    from . import brand
    if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
        raise ValueError(f"Scene {sid}: 'fact' needs 'text' (the sentence).")
    extra = set(raw) - {"value", "text", "source", "t", "dur"}
    if extra:
        raise ValueError(f"Scene {sid}: unknown field(s) in 'fact': {sorted(extra)}.")
    text = str(raw["text"]).strip()
    if len(text) > brand.FACT_MAX_CHARS:
        raise ValueError(f"Scene {sid}: 'fact.text' with {len(text)} characters (maximum {brand.FACT_MAX_CHARS}; legibility).")
    dur = float(raw.get("dur", 4.0))
    if dur < 2.0:
        raise ValueError(f"Scene {sid}: 'fact.dur' under 2 s leaves no time to read.")
    return {"value": str(raw.get("value", "")).strip(), "text": text, "source": str(raw.get("source", "")).strip(),
            "t": max(0.0, float(raw.get("t", 1.0))), "dur": dur}


def _panel_rows(sid: str, raw, has_hook: bool, style: str) -> tuple:
    """Data lines of the HUD panel: [[label, value] or [label, value, when 0 to 1], ...]."""
    if not raw:
        return ()
    if style != "hud":
        raise ValueError(f"Scene {sid}: 'panel_rows' only applies with \"panel_style\": \"hud\" in the script.")
    from . import brand
    limit = brand.HUD_MAX_ROWS_WITH_HOOK if has_hook else brand.HUD_MAX_ROWS
    if len(raw) > limit:
        raise ValueError(f"Scene {sid}: 'panel_rows' accepts at most {limit} lines"
                         f"{' with the opening question on screen' if has_hook else ''} (legibility on a phone).")
    rows = []
    for r in raw:
        if not (isinstance(r, (list, tuple)) and len(r) in (2, 3)):
            raise ValueError(f"Scene {sid}: each 'panel_rows' line is [label, value] or [label, value, when 0 to 1].")
        label, value = str(r[0]).strip(), str(r[1]).strip()
        if not label or not value or len(label) > 26 or len(value) > 14:
            raise ValueError(f"Scene {sid}: line '{label}: {value}' (label up to 26 and value up to 14 characters).")
        rows.append((label, value, min(1.0, max(0.0, float(r[2]) if len(r) == 3 else 0.0))))
    return tuple(rows)


def _stage(sid: str, raw: dict | None, carried: set | None = None) -> dict | None:
    """Data-driven stage of the scene (tools/stage/validate.py checks names, catalog ids, camera and triggers)."""
    if raw is None:
        return None
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "tools" / "stage" / "validate.py"
    spec = importlib.util.spec_from_file_location("stage_validate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.check(sid, raw, frozenset(carried or ()))
    if carried is not None:                     # pieces with 'span' stay referenceable in the following scenes of the same stage
        if raw.get("set", "meadow") != "same":
            carried.clear()
        carried |= {n for n in mod.prop_names({"props": [p for p in raw.get("props", []) if p.get("span")]})}
    return raw


def _flat_validate():
    """tools/flat2d/validate.py (without Pillow): imported as the 'flat2d' package from tools/."""
    import sys
    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from flat2d import validate
    return validate


def _flat(sid: str, raw: dict, fmt: str, cast: dict | None = None) -> tuple:
    """2D fields of the scene: 'flat' (plan and events) and the series HUD ('clock', 'chip')."""
    narration = str(raw.get("narration", ""))
    flat, clock, chip = raw.get("flat"), raw.get("clock", _MISSING), raw.get("chip")
    if flat is None and clock is _MISSING and chip is None:
        return None, None, ()
    v = _flat_validate()
    if flat is not None:
        v.check(sid, flat, narration, cast)
    v.check_hud(sid, None if clock is _MISSING else clock, chip, narration)
    clock = None if clock is _MISSING else (clock or False)
    return flat, clock, tuple(chip if isinstance(chip, list) else [chip] if chip else [])


def _reject_unknown(keys, known: set, where: str) -> None:
    """An unknown key is a typo the loader would silently ignore ('direcion' does not change the scene voice).
    Keys starting with '_' are free comments."""
    import difflib
    for key in keys:
        if key in known or str(key).startswith("_"):
            continue
        near = difflib.get_close_matches(str(key), sorted(known), n=1)
        raise ValueError(f"{where}: campo desconhecido '{key}'" + (f" (quis dizer '{near[0]}'?)" if near else "") + ".")


def load(path: str | Path) -> Script:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("slug", "title", "scenes"):
        if key not in data:
            raise ValueError(f"The script needs the field '{key}'.")
    if not data["scenes"]:
        raise ValueError("The script has no scenes.")
    _reject_unknown(data, _TOP_KEYS, "Roteiro")

    style = data.get("style", "")
    fmt = data.get("format", "voice")
    if fmt not in FORMATS:
        raise ValueError(f"'format' must be one of {FORMATS}, not '{fmt}'.")
    motion_style = data.get("motion_style", "")
    panel_style = data.get("panel_style", "side")
    if panel_style not in ("side", "hud"):
        raise ValueError(f"'panel_style' must be \"side\" (default) or \"hud\", not '{panel_style}'.")
    cast = _flat_validate().check_cast(data["cast"]) if "cast" in data else {}
    scenes, current_stamp, seen, carried = [], None, set(), set()
    current_label = data.get("panel_label", "")
    for raw in data["scenes"]:
        sid = str(raw.get("id", "")).strip()
        if not sid or sid in seen:
            raise ValueError(f"Each scene needs a unique 'id' (problem in: {raw!r:.80}).")
        seen.add(sid)
        _reject_unknown(raw, _SCENE_KEYS, f"Cena {sid}")
        lines = tuple(s.strip() for s in raw.get("text", []) if s.strip())
        if fmt == "text" and not lines and not raw.get("on_screen"):
            raise ValueError(f"Scene {sid}: in 'text' format it needs 'text' (list of sentences) or 'on_screen'.")
        if fmt == "voice" and not raw.get("narration") and not raw.get("on_screen"):
            raise ValueError(f"Scene {sid}: it needs 'narration' or 'on_screen'.")

        # "stamp" absent = keeps the stamp of the previous scene; null = hides it; text = changes it.
        stamp = raw.get("stamp", _MISSING)
        if stamp is not _MISSING:
            current_stamp = stamp or None
        current_label = raw.get("panel_label", current_label)

        tool = str(raw.get("tool", "seedance")).strip().lower()
        if tool not in TOOLS:
            raise ValueError(f"Scene {sid}: 'tool' must be one of {TOOLS}, not '{tool}'.")

        captions = tuple(c.strip() for c in raw.get("captions", []) if c.strip())
        narration_words = raw.get("narration", "").split()
        if captions and " ".join(captions).split() != narration_words:
            raise ValueError(f"Scene {sid}: joined 'captions' must repeat the narration word for word.")

        flat, clock, chip = _flat(sid, raw, fmt, cast)
        scenes.append(Scene(
            id=sid,
            prompt=raw.get("prompt", "").strip(),
            style=raw.get("style", style).strip(),
            narration=raw.get("narration", "").strip(),
            on_screen=raw.get("on_screen", "").strip(),
            stamp=current_stamp,
            highlight=[w.upper().strip(".,!?;:\"'") for w in raw.get("highlight", [])],
            min_seconds=float(raw.get("min_seconds", 2.0)),
            motion=raw.get("motion", "").strip(),
            motion_style=raw.get("motion_style", motion_style).strip(),
            tool=tool,
            captions=captions,
            lines=lines,
            panel_label=current_label,
            panel_sub=raw.get("panel_sub", "").strip(),
            panel_sub_at=min(1.0, max(0.0, float(raw.get("panel_sub_at", 0.0)))),
            panel_rows=_panel_rows(sid, raw.get("panel_rows"), bool(raw.get("on_screen")), panel_style),
            fact=_fact(sid, raw.get("fact"), panel_style),
            fade_in=max(0.0, float(raw.get("fade_in", 0.0))),
            fade_out=max(0.0, float(raw.get("fade_out", 0.0))),
            counter=_counter(sid, raw.get("counter")),
            scrim=bool(raw.get("scrim", False)),
            direction=_direction(raw.get("direction"), f"Cena {sid}"),
            claims=tuple(str(c).strip() for c in raw.get("claims", []) if str(c).strip()),
            stage=_stage(sid, raw.get("stage"), carried),
            flat=flat,
            clock=clock,
            chip=chip,
        ))

    caption_style = data.get("caption_style", "default")
    if caption_style not in ("default", "karaoke"):
        raise ValueError(f"'caption_style' must be \"default\" or \"karaoke\", not '{caption_style}'.")
    if not isinstance(data.get("panel", True), bool):
        raise ValueError("'panel' is true (default) or false.")
    return Script(
        slug=data["slug"],
        channel=data.get("channel", "ifscape"),
        title=data["title"],
        description=data.get("description", ""),
        sources=data.get("sources", []),
        hashtags=data.get("hashtags", []),
        scenes=scenes,
        format=fmt,
        end_card=_end_card_text(data.get("end_card", "")),
        show_end_card=data.get("end_card") is True or bool(_end_card_text(data.get("end_card", ""))),
        sfx={k: data[k] for k in ("sfx", "ambience", "sfx_traffic", "sfx_panel", "sfx_lufs", "sfx_auto") if k in data},
        credit=_credit(data.get("credit")),
        final_fact=_final_fact(data.get("final_fact")),
        panel_clock=bool(data.get("panel_clock", False)),
        panel_clock_from=float(data.get("panel_clock_from", 0.0)),
        closing=str(data.get("closing", "")).strip(),
        now_clock=bool(data.get("now_clock", True)),
        now_clock_from=float(data.get("now_clock_from", 0.0)),
        voice_model=str(data.get("voice_model", "")).strip(),
        voice_direction=_direction(data.get("voice_direction"), "Roteiro") or "",
        voice_stability=float(data["voice_stability"]) if "voice_stability" in data else None,
        panel_style=panel_style,
        master_lufs=_master_lufs(data, fmt),
        caption_style=caption_style,
        panel=data.get("panel", True),
        cast=cast,
    )
