"""Sound effects from a library of real sounds (sfx/library.json).

Pattern of the niche's viral videos (docs/sound-research.md): full ambience before the event, boom at the event and
a cut to near silence; then a few spot sounds at the strong moments and an era ambience rising.

The sounds come from two sources (chosen after pure FFmpeg synthesis sounded
strange): Mixkit for the generic (city, wind, stream, whoosh, impacts) and ElevenLabs Sound Effects
for the specific (hits, blackout, flooding subway, collapse, tick). The files stay in sfx/ and are
downloaded or generated only once.

Four sources of cue ("cue"):
- the script: "sfx" (spot sounds) and "ambience" (layers with a start and end), tied to scene + fraction;
- the data-driven stage ('stage' field, lean mode): sound by rule, without writing a cue (see _stage_cues);
- the live panel: whoosh at the start of each time jump and tick only while a "counter" changes;
- the traffic simulation (tools/blender/traffic.py): a hit on each strong collision.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

from . import brand, panel
from .util import ROOT, duration, load_env, run

RATE = 44100
LIBRARY_DIR = ROOT / "sfx"
LIBRARY = LIBRARY_DIR / "library.json"
TRAFFIC_SCRIPT = ROOT / "tools" / "blender" / "traffic.py"
MIXKIT_URL = "https://assets.mixkit.co/active_storage/sfx/{id}/{id}-preview.mp3"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/sound-generation"
ELEVENLABS_INFLUENCE = 0.45      # 0 to 1: how literally the sound follows the text
MIN_CRASH_FORCE = 1.0            # collisions weaker than this make no noise
CRASH_GAP = 0.25                 # hits closer together than this become one (s)
TICK_GAP = 0.07                  # ticks closer together than this are discarded (s)
WHOOSH_LEAD = 0.5                # the whoosh of the time jumps starts before the cut (s)
BATCH = 12                       # an amix with ~100 inputs hangs FFmpeg 9; mixes in batches
POINT_ATTACK = 0.005             # attack (s) of a spot sound
LOOP_XFADE = 3.0                # crossfade (s) when an ambience repeats the file
# Final volume. The 8 viral videos measured sit between -13 and -18 LUFS (median ~ -15) and all
# use "original sound": the ambience comes in the file, with no platform music on top. At -20 the video
# came out at -24 and sounded quiet, with the hits jumping ~20 dB above the background.
# At -16 the effects sounded too loud on Instagram: lowered to -21.
TARGET_LUFS = -21
TRUE_PEAK = 0.71                 # limiter ceiling (-3 dBFS); after AAC the peak sits near -1.7
# Compression of the effects bus: brings hits and background closer (before, a 19 dB difference).
COMPRESSOR = "acompressor=threshold=0.06:ratio=3:attack=5:release=250:makeup=1"


@dataclass(frozen=True)
class Cue:
    sound: str
    start: float           # second of the video
    seconds: float         # duration of the sound
    gain: float = 1.0
    fade: float = 0.0      # soft fade in and out (ambiences)
    fade_in: float | None = None    # fade in only (L-cut, burst); None = same as 'fade'
    fade_out: float | None = None   # fade out only
    pan: float = 0.0       # -1 (left) to +1 (right); 0 = center. Only for mono spot sounds
    lowpass: float = 0.0   # Hz; cuts the high hiss (stage ambience beds); 0 = no filter
    accent: bool = False   # hit that must be heard (door knock): comes in after the compressor and the normalization


def library() -> dict:
    data = json.loads(LIBRARY.read_text(encoding="utf-8-sig"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ---------- library files ----------

def _download_mixkit(item_id: int, out: Path) -> None:
    req = urllib.request.Request(MIXKIT_URL.format(id=item_id), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        out.write_bytes(resp.read())


def _generate_elevenlabs(prompt: str, seconds: float, out: Path) -> None:
    load_env()
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise SystemExit("Set ELEVENLABS_API_KEY in .env to generate the ElevenLabs sound effects.")
    body = json.dumps({"text": prompt, "duration_seconds": seconds,
                       "prompt_influence": ELEVENLABS_INFLUENCE}).encode()
    req = urllib.request.Request(ELEVENLABS_URL, data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out.write_bytes(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"ElevenLabs Sound Effects falhou ({err.code}): {err.read()[:300]!r}") from err
    print(f"  sound generated on ElevenLabs ({seconds:.1f} s, ~{int(seconds * 20)} credits): {prompt[:60]}...")


def _use(item: dict) -> str:
    """Which source to use: 'use' on the item; IFSCAPE_SFX=mixkit forces Mixkit where available (A/B comparison)."""
    if os.environ.get("IFSCAPE_SFX") == "mixkit" and "mixkit" in item:
        return "mixkit"
    return item.get("use", "mixkit" if "mixkit" in item else "elevenlabs")


def source_file(name: str, lib: dict) -> Path:
    """File of the sound, downloaded (Mixkit) or generated (ElevenLabs) only the first time."""
    item = lib[name]
    if _use(item) == "mixkit":
        out = LIBRARY_DIR / "mixkit" / f"{item['mixkit']}.mp3"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            _download_mixkit(item["mixkit"], out)
        return out
    key = hashlib.sha1(f"{item['elevenlabs']}|{item['seconds']}|{ELEVENLABS_INFLUENCE}".encode()).hexdigest()[:12]
    out = LIBRARY_DIR / "elevenlabs" / f"{name}_{key}.mp3"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        _generate_elevenlabs(item["elevenlabs"], float(item["seconds"]), out)
    return out


def _clip(name: str, seconds: float, lib: dict, work: Path) -> Path:
    """The part of the sound that the cue uses, as stereo WAV. If the cue is longer than the useful part
    ('start' to 'end'), it repeats the part with a crossfade: the old -stream_loop joined dry and clicked."""
    src = source_file(name, lib)
    item = lib[name]
    mixkit = _use(item) == "mixkit"
    start = float(item.get("start", 0.0)) if mixkit else 0.0
    end = float(item["end"]) if mixkit and "end" in item else duration(src)
    usable = end - start
    out = work / f"{name}_{src.stem}_{start:.2f}_{end:.2f}_{seconds:.2f}.wav"
    if out.exists():
        return out
    tmp = out.with_suffix(".tmp.wav")
    if seconds <= usable or usable <= 2 * LOOP_XFADE:
        run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-ss", f"{start:.3f}", "-i", str(src),
             "-t", f"{seconds:.3f}", "-af", f"aresample={RATE}", "-ac", "2", "-c:a", "pcm_s16le", str(tmp)])
    else:
        copies = 1 + math.ceil((seconds - usable) / (usable - LOOP_XFADE))
        inputs = []
        for _ in range(copies):
            inputs += ["-ss", f"{start:.3f}", "-t", f"{usable:.3f}", "-i", str(src)]
        graph, last = "", "0:a"
        for k in range(1, copies):
            graph += f"[{last}][{k}:a]acrossfade=d={LOOP_XFADE}:c1=qsin:c2=qsin[x{k}];"
            last = f"x{k}"
        graph += f"[{last}]aresample={RATE}[out]"
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]",
             "-t", f"{seconds:.3f}", "-ac", "2", "-c:a", "pcm_s16le", str(tmp)])
    tmp.replace(out)
    return out


# ---------- deixas ----------

def _scene_time(starts: dict[str, tuple[float, float]], scene: str, at: float) -> float:
    if scene not in starts:
        raise ValueError(f"sfx: the scene '{scene}' does not exist in the script.")
    t0, dur = starts[scene]
    return t0 + dur * at


def _word_time(manifest: dict | None, scene: str, word: str, offset: float = 0.0) -> float:
    """Second (inside the scene) at which the word starts in the voice; "billions#2" takes the 2nd occurrence.
    A cue tied to a word does not slide when the scene's speech changes duration (the scene fraction slides)."""
    target, _, nth = word.partition("#")
    norm = lambda w: w.strip(".,!?;:\"'").lower()
    words = (manifest or {}).get(scene, {}).get("words") or []
    hits = [w["start"] for w in words if norm(w["word"]) == norm(target)]
    k = int(nth or 1)
    if len(hits) < k:
        raise ValueError(f"sfx: the word '{word}' is not in the voice of scene {scene} (generate the voice before the render).")
    return hits[k - 1] + offset


def _anchor(starts: dict, manifest: dict | None, scene: str, where, offset: float = 0.0) -> float:
    """Cue point: scene fraction (0 to 1) or voice word (text)."""
    if isinstance(where, str):
        _scene_time(starts, scene, 0.0)                      # checks that the scene exists
        return starts[scene][0] + _word_time(manifest, scene, where, offset)
    return _scene_time(starts, scene, float(where)) + offset


def _check(sound: str, lib: dict) -> None:
    if sound not in lib:
        raise ValueError(f"sfx: unknown sound '{sound}'. Options in sfx/library.json: {', '.join(lib)}")


def _peak_offset(entry: dict) -> float:
    """Seconds between the start of the used part and the hit ('peak' in Mixkit, 'el_peak' in ElevenLabs).
    The cue starts that much earlier, so the hit lands on the event."""
    if _use(entry) == "mixkit":
        return max(0.0, float(entry.get("peak", entry.get("start", 0.0))) - float(entry.get("start", 0.0)))
    return float(entry.get("el_peak", 0.0))


def _script_cues(raw: dict, starts: dict, lib: dict, manifest: dict | None = None) -> list[Cue]:
    cues = []
    for item in raw.get("sfx", []):
        _check(item["sound"], lib)
        # "word" (voice word, + "offset" in s) takes precedence over "at" (scene fraction)
        where = item["word"] if "word" in item else float(item.get("at", 0.0))
        t = _anchor(starts, manifest, item["scene"], where, float(item.get("offset", 0.0)))             - _peak_offset(lib[item["sound"]])
        cues.append(Cue(item["sound"], max(0.0, t), float(item.get("seconds", 4.0)), float(item.get("gain", 1.0)),
                        float(item.get("fade", 0.0)), item.get("fade_in"), item.get("fade_out"),
                        float(item.get("pan", 0.0)), accent=bool(item.get("accent", False))))
        # 'fade': fade in and out; 'fade_in'/'fade_out' separate the ends; 'accent': absolute gain, no compressor
    for item in raw.get("ambience", []):
        _check(item["sound"], lib)
        a = _anchor(starts, manifest, item["from"][0], item["from"][1])
        b = _anchor(starts, manifest, item["to"][0], item["to"][1])
        if b <= a:
            raise ValueError(f"ambience '{item['sound']}': 'to' must come after 'from'.")
        cues.append(Cue(item["sound"], a, b - a, float(item.get("gain", 1.0)), float(item.get("fade", 0.6)),
                        item.get("fade_in"), item.get("fade_out")))
    return cues


# ---------- sound by rule (lean mode) ----------
# Without writing "sfx" by hand: the stage already says the place, the light, who walks and what happens. Only sounds the library has.
# Ambience bed per stage and per light (the pilot ambience was just a low breath).
# The stage "wind" changes by place; the animals change with the hour: birds at dawn, crickets at dusk.
STAGE_WIND = {"meadow": "leaves_breeze", "savanna": "savanna_wind", "forest": "forest", "desert": "dry_leaves_wind"}
STAGE_BED = {"dawn": [("wind", 1.0), ("birds_small", 0.6)], "noon": [("wind", 1.0), ("birds_small", 0.3)],
             "dry-noon": [("wind", 1.0)], "overcast": [("wind", 1.0), ("wind_top", 0.35)],
             "dusk": [("wind", 0.8), ("crickets", 0.4)], "night": [("crickets", 0.7)]}
STAGE_VACUO = [("drone", 0.9)]
# Volume by target, not by eyeballed gain (in the pilot the ambience came out at -30 LUFS and the light_sweep at -13, and the
# wind was inaudible). LEVEL = LUFS of each sound already with the library gain (measured on 8 s clips);
# the cue gets the gain that takes the sound to the target. Before the final normalization (-21 LUFS).
STAGE_LEVEL = {"chicken": -30.9, "boom": -14.7, "leaves_breeze": -30.0, "birds_small": -28.0, "crickets": -18.6, "wind": -20.7, "wind_top": -20.2,
               "savanna_wind": -31.1, "forest": -30.7, "dry_leaves_wind": -27.4, "drone": -22.7, "hooves": -45.8,
               "rumble": -12.9, "hit": -16.2, "whoosh": -17.9, "plop": -26.8, "light_sweep": -12.9}
STAGE_TARGET = {"voice": -24.0, "end_boom": -21.0, "end_drone": -35.0, "bed": -30.0, "walk": -31.0, "hit": -20.0, "whoosh": -24.0, "plop": -28.0, "light_sweep": -31.0}
STAGE_MAX_GAIN = 5.0
STAGE_VOICE = {"chicken": "chicken"}     # catalog piece that speaks: the sound comes in when the sentence mentions it (and again, low, at the end)
STAGE_BED_LOWPASS = 6000.0     # Hz: the wind and the crickets hissed in the pilot ("too much hiss")


def _to_target(sound: str, target: float, factor: float = 1.0) -> float:
    """Cue gain for the sound to reach 'target' LUFS (on top of the library gain), times 'factor'."""
    if sound not in STAGE_LEVEL:
        return factor
    return min(STAGE_MAX_GAIN, 10 ** ((target - STAGE_LEVEL[sound]) / 20)) * factor
STAGE_WALK = {"animal": "hooves", "dino": "rumble"}   # catalog type that walks -> footsteps ambience
STAGE_CUE = {"shake": ("hit", "hit", 1.5), "vanish": ("whoosh", "whoosh", 1.2), "pop": ("plop", "plop", 1.0),
             "dust": ("whoosh", "whoosh", 1.6)}
STAGE_CUE_LAG = {"dust": 0.45}     # s: the sound peak comes when the dust gets near the lens, not at the impact
_catalog_kinds: dict | None = None


def _kind_of(ident) -> str:
    global _catalog_kinds
    if _catalog_kinds is None:
        data = json.loads((ROOT / "tools" / "stage" / "catalog.json").read_text(encoding="utf-8"))["items"]
        _catalog_kinds = {i["id"]: i["kind"] for i in data}
    return _catalog_kinds.get(ident[0] if isinstance(ident, list) else ident, "")


def _stage_when(cue: dict, sid: str, starts: dict, manifest: dict | None) -> float:
    words = (manifest or {}).get(sid, {}).get("words")
    if "word" in cue and words:
        word = cue["word"] + (f"#{int(cue['nth']) + 1}" if cue.get("nth") else "")
        return starts[sid][0] + _word_time(manifest, sid, word, float(cue.get("off", 0.0)))
    if "t" in cue:
        return starts[sid][0] + float(cue["t"])
    return starts[sid][0] + starts[sid][1] * float(cue.get("frac", 0.5))


def _bed(set_name: str, light: str) -> list[tuple[str, float]]:
    if set_name == "vacuo":
        return STAGE_VACUO
    wind = STAGE_WIND.get(set_name, "leaves_breeze")
    return [(wind if sound == "wind" else sound, gain) for sound, gain in STAGE_BED.get(light, STAGE_BED["noon"])]


def _closing_time(script, starts: dict) -> float | None:
    """Second at which the final question ('What should I imagine next?') appears in text format; None without an end card."""
    if not getattr(script, "show_end_card", False):
        return None
    from .timing import line_seconds
    for sc in script.scenes:
        for k, line in enumerate(sc.lines):
            if "what should i imagine next" in line.lower():
                at = starts[sc.id][0] + sum(line_seconds(x) for x in sc.lines[:k])
                if k == len(sc.lines) - 1 and k > 0:   # the scene's slack stays on the previous sentence (timing.chunks)
                    at += max(0.0, starts[sc.id][1] - sum(line_seconds(x) for x in sc.lines))
                return at
    return None


def _stage_cues(script, starts: dict, lib: dict, manifest: dict | None = None) -> list[Cue]:
    """Stage ambience in layers that change with the light (one bed per scene, equal neighbors become one), footsteps
    of animals and dinos that walk, and one sound per trigger (shake, vanish, pop, light). Tied to the scene time."""
    cues, spans, set_name, light = [], [], "meadow", "noon"
    voiced: dict = {}
    from .timing import line_seconds
    for sc in script.scenes:
        if not sc.stage:
            continue
        if sc.stage.get("set", "meadow") != "same" or not spans:
            set_name, light = sc.stage.get("set", "meadow"), sc.stage.get("light", "noon")
        t0, dur = starts[sc.id]
        # scene light: that of the last 'light' trigger that starts before its middle (the change is slow)
        for cue in sorted((c for c in sc.stage.get("cues", []) if c["do"] == "light"),
                          key=lambda c: _stage_when(c, sc.id, starts, manifest)):
            if _stage_when(cue, sc.id, starts, manifest) < t0 + dur / 2:
                light = cue["light"]
        for sound, gain in _bed(set_name, light):
            spans.append([sound, t0, t0 + dur, gain])
        for p in sc.stage.get("props", []):
            ident = p.get("id") if isinstance(p.get("id"), str) else None
            if ident in STAGE_VOICE and ident not in voiced:
                at = t0 + 1.0
                for k, line in enumerate(sc.lines):        # sentence that mentions the piece ("Even the chicken is…")
                    if ident in line.lower():
                        at = t0 + sum(line_seconds(x) for x in sc.lines[:k])
                        break
                voiced[ident] = STAGE_VOICE[ident]
                cues.append(Cue(STAGE_VOICE[ident], max(0.0, at - _peak_offset(lib[STAGE_VOICE[ident]])), 3.0,
                                _to_target(STAGE_VOICE[ident], STAGE_TARGET["voice"])))
        walkers = {STAGE_WALK[k] for p in sc.stage.get("props", []) if ("to" in p or "path" in p)
                   for k in [_kind_of(p.get("id", ""))] if k in STAGE_WALK}
        for sound in sorted(walkers):
            cues.append(Cue(sound, t0, dur, _to_target(sound, STAGE_TARGET["walk"]), 0.5))
        for cue in sc.stage.get("cues", []):
            when = _stage_when(cue, sc.id, starts, manifest)
            if cue["do"] in STAGE_CUE:
                sound, key, secs = STAGE_CUE[cue["do"]]
                gain = _to_target(sound, STAGE_TARGET[key])
                when += STAGE_CUE_LAG.get(cue["do"], 0.0)
                cues.append(Cue(sound, max(0.0, when - _peak_offset(lib[sound])), secs, gain))
            elif cue["do"] == "light":
                cues.append(Cue("light_sweep", when, min(float(cue.get("dur", 10.0)), 4.0),
                                _to_target("light_sweep", STAGE_TARGET["light_sweep"]), 0.5))
    # Closing: when the final question becomes a card, the ambience
    # ends, a low impact comes in and only a low drone stays under the question (as in bacteria-disappeared).
    close_t = _closing_time(script, starts)
    total_end = starts[script.scenes[-1].id][0] + starts[script.scenes[-1].id][1]
    if close_t is not None:
        for span in spans:
            span[2] = min(span[2], close_t)
        spans = [sp for sp in spans if sp[2] - sp[1] > 0.5]
        cues.append(Cue("boom", max(0.0, close_t - _peak_offset(lib["boom"])), 5.0,
                        _to_target("boom", STAGE_TARGET["end_boom"])))
        for sound in voiced.values():              # the piece says goodbye: a low sound right after the impact
            cues.append(Cue(sound, close_t + 1.3, 3.0, 0.6 * _to_target(sound, STAGE_TARGET["voice"])))
        cues.append(Cue("drone", close_t, max(1.0, total_end - close_t),
                        _to_target("drone", STAGE_TARGET["end_drone"]), 1.0, lowpass=STAGE_BED_LOWPASS))
    merged: list[list] = []
    for span in spans:                      # neighboring scenes with the same sound (and gain) become one continuous layer
        prev = next((m for m in merged if m[0] == span[0] and m[3] == span[3] and abs(m[2] - span[1]) < 1e-6), None)
        if prev:
            prev[2] = span[2]
        else:
            merged.append(span)
    for sound, a, b, gain in merged:
        cues.append(Cue(sound, a, b - a, _to_target(sound, STAGE_TARGET["bed"], gain), 1.2,
                        lowpass=STAGE_BED_LOWPASS))
    for c in cues:
        _check(c.sound, lib)
    return cues


def _closing_cues(script, starts: dict, lib: dict, cues: list[Cue]) -> list[Cue]:
    """Closing for a script with a hand-written sound list: when the final question becomes a card, the ambience
    cuts on it, the low impact comes in and only the low drone stays under the
    question. The stage already does this in _stage_cues; here it applies to the rest of the text format."""
    close_t = _closing_time(script, starts)
    if close_t is None:
        return cues
    last = script.scenes[-1].id
    total_end = starts[last][0] + starts[last][1]
    out = []
    for c in cues:
        if c.seconds > 3.0 and c.start < close_t < c.start + c.seconds:
            c = replace(c, seconds=close_t - c.start, fade_out=0.35)
        out.append(c)
    out.append(Cue("boom", max(0.0, close_t - _peak_offset(lib["boom"])), 5.0,
                   _to_target("boom", STAGE_TARGET["end_boom"])))
    out.append(Cue("drone", close_t, max(1.0, total_end - close_t),
                   _to_target("drone", STAGE_TARGET["end_drone"]), 1.0, lowpass=STAGE_BED_LOWPASS))
    return out


def _panel_cues(script, starts: dict) -> list[Cue]:
    """Whoosh at the start of each time jump; tick only while a counter changes (population drop).
    The earlier version ticked at every change of the number: too much sound."""
    cues, previous, last_tick = [], None, -1.0
    for scene in script.scenes:
        t0, dur = starts[scene.id]
        vals = panel.values(scene.stamp, previous, scene.counter, dur)
        if (scene.stamp and previous and scene.stamp != previous
                and scene.stamp.strip().upper() != "NOW" and vals[0] != scene.stamp):
            # The whoosh (Mixkit 1492) rises slowly and peaks at 1.07 s: it starts before the cut so the peak
            # lands at the end of the number roll (sound design finding: it arrived 1 s late).
            cues.append(Cue("whoosh", max(0.0, t0 - WHOOSH_LEAD), 1.2 + WHOOSH_LEAD))
        if scene.counter:
            c = scene.counter
            a, b = t0 + c.change_at, t0 + c.change_at + c.change_over
            changes = sum(1 for i in range(1, len(vals))
                          if a <= t0 + i / brand.PANEL_FPS <= b and vals[i] != vals[i - 1])
            # A counter that changes every frame (hundreds of values) cannot become a machine gun: 1 tick per ~0.6 s
            gap = TICK_GAP if changes <= 60 else 0.6
            for i in range(1, len(vals)):
                t = t0 + i / brand.PANEL_FPS
                if a <= t <= b and vals[i] != vals[i - 1] and t - last_tick >= gap:
                    cues.append(Cue("tick", t, 0.4))
                    last_tick = t
        previous = scene.stamp or previous
    return cues


def _traffic_cues(raw: dict, starts: dict, lib: dict) -> list[Cue]:
    """Hits at the instants of the same simulation Blender uses (same vanishing, same collisions)."""
    spec = raw.get("sfx_traffic")
    if not spec or not TRAFFIC_SCRIPT.exists():
        return []
    mod_spec = importlib.util.spec_from_file_location("traffic", TRAFFIC_SCRIPT)
    traffic = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(traffic)
    fps = brand.FPS
    vanish_frame = round(_scene_time(starts, spec["scene"], float(spec["at"])) * fps)
    cars, obstacles = traffic.scenario(vanish_frame / fps)
    until = _scene_time(starts, spec["until"], 1.0)        # same end as the 3D set simulation
    _, events = traffic.simulate(cars, obstacles, until)
    cues, last = [], -1.0
    for e in sorted(events, key=lambda e: e["frame"]):
        t = e["frame"] / fps
        if e["force"] < MIN_CRASH_FORCE or t - last < CRASH_GAP:
            continue
        name = "crash_a" if len(cues) % 2 == 0 else "crash_b"      # alternates the two hits
        # The hit of the file lands on the frame of the collision ('crash_a' takes 0.13 s to peak: it sounded late).
        start = max(0.0, t - _peak_offset(lib[name]))
        cues.append(Cue(name, start, 2.0, min(1.0, 0.45 + e["force"] / 12)))
        last = t
    return cues


# ---------- mixagem ----------

def _mix(cues: list[Cue], total: float, lib: dict, work: Path, out: Path) -> None:
    """Mixes a batch of cues into a track the size of the whole video."""
    inputs, branches, labels = [], [], []
    for i, c in enumerate(cues):
        seconds = min(c.seconds, total - c.start)
        inputs += ["-i", str(_clip(c.sound, seconds, lib, work))]
        item = lib[c.sound]
        base = item.get("el_gain", item.get("gain", 1.0)) if _use(item) == "elevenlabs" else item.get("gain", 1.0)
        gain = c.gain * float(base)
        chain = f"[{i}:a]volume={gain:.3f}"
        if c.lowpass:
            chain += f",lowpass=f={c.lowpass:.0f}"
        if c.pan:
            # pan 0.2 = ~20% to the right: the left channel drops and the right one stays (mono becomes stereo)
            chain += f",pan=stereo|c0={1 - abs(c.pan) if c.pan > 0 else 1.0:.3f}*c0|c1={1.0 if c.pan > 0 else 1 - abs(c.pan):.3f}*c0"
        if c.fade:
            fade_in = min(c.fade if c.fade_in is None else float(c.fade_in), seconds / 3)
            fade_out = min(c.fade if c.fade_out is None else float(c.fade_out), seconds / 3)
        else:
            # Spot sound: 5 ms attack (only avoids a click). With 50 ms the hit of the collisions got soft and late.
            fade_in, fade_out = min(POINT_ATTACK, seconds / 4), min(0.05, seconds / 4)
        chain += f",afade=t=in:d={fade_in:.3f},afade=t=out:st={seconds - fade_out:.3f}:d={fade_out:.3f}"
        ms = int(c.start * 1000)
        chain += f",adelay={ms}|{ms}[s{i}]"
        branches.append(chain)
        labels.append(f"[s{i}]")
    graph = (";".join(branches) + ";" + "".join(labels) +
             # apad=whole_dur, not apad+atrim: on FFmpeg 9 the combination sometimes did not finish near the end.
             f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}[out]")
    out_args = ["-t", f"{total:.3f}"]
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph,
         "-map", "[out]", *out_args, "-ac", "2", "-c:a", "pcm_s16le", str(out)])


def build(script, starts: dict[str, tuple[float, float]], total: float, work: Path,
          manifest: dict | None = None) -> Path | None:
    """Builds the effects track of the whole video. 'starts' = {scene: (start in s, duration in s)};
    'manifest' = voice with per-word time (for cues with "word")."""
    raw = script.sfx
    auto = any(sc.stage for sc in script.scenes) and raw.get("sfx_auto", True)
    if not raw and not auto:
        return None
    work.mkdir(parents=True, exist_ok=True)
    lib = library()
    cues = _script_cues(raw, starts, lib, manifest) + _traffic_cues(raw, starts, lib)
    if auto:
        cues += _stage_cues(script, starts, lib, manifest)
    else:
        cues = _closing_cues(script, starts, lib, cues)
    if raw.get("sfx_panel", True) and getattr(script, "panel", True):      # "panel": false = no panel on screen, no panel sounds
        cues += _panel_cues(script, starts)
    cues = sorted((c for c in cues if c.start < total), key=lambda c: c.start)

    accents = [c for c in cues if c.accent]
    cues = [c for c in cues if not c.accent]
    batches = []
    for k in range(0, len(cues), BATCH):
        part = work / f"lote_{k // BATCH:02d}.wav"
        _mix(cues[k:k + BATCH], total, lib, work, part)
        batches.append(part)
    out = work / "sfx.wav"
    pre = work / "sfx_pre.wav"
    inputs = [arg for b in batches for arg in ("-i", str(b))]
    labels = "".join(f"[{i}:a]" for i in range(len(batches)))
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
         f"{labels}amix=inputs={len(batches)}:normalize=0:dropout_transition=0,{COMPRESSOR}[out]",
         "-map", "[out]", "-ac", "2", "-c:a", "pcm_s16le", str(pre)])
    # Two passes: measures and applies a fixed gain. Single-pass loudnorm came out 4 dB below the target.
    # 'sfx_lufs' in the script changes the target: with voice, the effects track goes to -25 (at -21 it overtook the voice).
    gain = float(raw.get("sfx_lufs", TARGET_LUFS)) - loudness(pre)
    # Limiter at 4x the rate: limits the true peak. At 44.1 kHz AAC overshot +2 dBFS on the hits.
    limiter = f"aresample={RATE * 4},alimiter=limit={TRUE_PEAK}:attack=5:release=80:level=false,aresample={RATE}"
    if accents:   # accents: absolute gain on top of the already normalized track (the compressor flattened the hits)
        acc = work / "acentos.wav"
        _mix(accents, total, lib, work, acc)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-i", str(acc), "-filter_complex",
             f"[0:a]volume={gain:.2f}dB[m];[m][1:a]amix=inputs=2:normalize=0:dropout_transition=0,{limiter}[out]",
             "-map", "[out]", "-ac", "2", "-c:a", "pcm_s16le", str(out)])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(pre), "-af", f"volume={gain:.2f}dB,{limiter}",
             "-ac", "2", "-c:a", "pcm_s16le", str(out)])
    print(f"  sound effects: {len(cues)} cues in {len(batches)} batches, {loudness(out):.1f} LUFS -> {out}")
    return out


def loudness(path: Path) -> float:
    """Integrated loudness (LUFS, EBU R128) of an audio or video file."""
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128",
                           "-f", "null", "-"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", proc.stderr)
    if not found:
        raise RuntimeError(f"Could not measure the loudness of {path}")
    return float(found[-1])
