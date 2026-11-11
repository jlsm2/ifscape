"""State of a video read from disk, stage by stage (production order in CLAUDE.md).

The hand-written progress.md fell behind the disk on plants-extinct (it said "Blender: nothing done" with the render
running). Here each stage is: ok, STALE (the input changed afterwards) or missing. Decisions and human
pending items stay in progress.md.
"""

import json
import os
import re
from pathlib import Path

from . import blender, metrics, timing, voice
from .script import Script
from .util import ROOT, build_dir, clips_dir


def _mtime(p: Path) -> float | None:
    return p.stat().st_mtime if p.exists() else None


def _row(name: str, state: str, note: str = "") -> tuple[str, str, str]:
    return name, state, note


FACT_ID = re.compile(r"\*\*(F\d+|FIN-[A-Z])\.")   # entry in facts.md: "**F4. ..." or "**FIN-A. ..."


def claim_problems(script: Script) -> list[str]:
    """Links sentence -> entry: a cited ID that does not exist in facts.md, and a scene with a number and no cited entry.
    Only checks the scenes when the script already uses 'claims' (old scripts do not)."""
    fatos = build_dir(script.slug) / "facts.md"
    used = [(s.id, c) for s in script.scenes for c in s.claims]
    if not used:
        return ["no scene cites entries ('claims': [\"F4\"]); the fact-check links sentence and source by hand"]
    if not fatos.exists():
        return ["the scenes cite entries, but there is no build/<slug>/facts.md"]
    known = set(FACT_ID.findall(fatos.read_text(encoding="utf-8")))
    problems = [f"scene {sid}: '{c}' does not exist in facts.md" for sid, c in used if c not in known]
    problems += [f"scene {s.id}: has a number in the line and no entry in 'claims'" for s in script.scenes
                 if re.search(r"\d", s.narration) and not s.claims]
    return problems


def report(script: Script, script_path: Path) -> list[tuple[str, str, str]]:
    b = build_dir(script.slug)
    rows = []
    src = _mtime(script_path)

    def doc(name: str, path: Path, newer_than: float | None = None, what: str = "the script"):
        t = _mtime(path)
        if t is None:
            rows.append(_row(name, "missing"))
        elif newer_than and t < newer_than:
            rows.append(_row(name, "STALE", f"{what} changed afterwards"))
        else:
            rows.append(_row(name, "ok"))

    doc("0 premise.md", b / "premise.md")
    doc("0b thesis.md", b / "thesis.md")
    doc("1 facts.md", b / "facts.md")
    model = script.voice_model or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    if script.format != "text":
        seconds, words = timing.estimate_total(script.scenes, model)
        lo, hi = timing.TARGET_SECONDS
        rows.append(_row("2 script", "ok" if lo <= seconds <= hi else "OUT OF TARGET",
                         timing.budget_line(seconds, words, model)))
    problems = claim_problems(script)
    rows.append(_row("2 cited entries", "ok" if not problems else "WARNING", "; ".join(problems)))
    lean = blender.uses_stage(script)          # lean mode: no director plan, art.md, hero frames or contact sheet
    if not lean:
        doc("2b direction.md", b / "direction.md")
    doc("3 review.md", b / "review.md", src)
    doc("3 factcheck.md", b / "factcheck.md", src)

    # Voice: scenes whose line in the script does not match the recorded one (fingerprint).
    if script.format != "text":
        vdir = b / "voice"
        vid = os.environ.get("ELEVENLABS_VOICE_ID", "")
        stale = []
        for s in script.scenes:
            if not s.narration:
                continue
            direction = script.voice_direction if s.direction is None else s.direction
            fp = voice._fingerprint(s.narration, vid, model, direction, script.voice_stability)
            meta_path = vdir / f"{s.id}.json"
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            if meta.get("fingerprint") != fp or meta.get("mode") == "dummy":
                stale.append(s.id)
        if not (b / "voice.json").exists():
            rows.append(_row("5 voice", "missing"))
        elif stale and vid:
            rows.append(_row("5 voice", "STALE", f"re-record: {', '.join(stale)}"))
        elif stale:
            rows.append(_row("5 voice", "?", "no ELEVENLABS_VOICE_ID in the environment to check"))
        else:
            rows.append(_row("5 voice", "ok"))

    bl = b / "blender"
    if not lean:
        doc("5b art.md", b / "art.md")
        heroes = list((bl / "hero").glob("*.png"))
        rows.append(_row("5b hero frames", "ok" if heroes else "missing", f"{len(heroes)} in blender/hero" if heroes else ""))
        sheets = list((bl / "keyframes").glob("*.png"))
        rows.append(_row("6 contact sheet", "ok" if sheets else "missing", f"{len(sheets)} in blender/keyframes" if sheets else ""))

    # Blender render: frames against the current timeline and code.
    stamp = bl / "frames" / "frames.json"
    if stamp.exists():
        tl = json.loads(stamp.read_text(encoding="utf-8"))
        done = len(list((bl / "frames").glob("f_*.png")))
        notes = [f"{done}/{tl['frames']} frames"]
        state = "ok" if done >= tl["frames"] else "INCOMPLETE"
        if tl.get("source") != blender.source_digest(script):
            state, notes = "STALE", notes + ["the code in tools/blender changed afterwards (use --frames on the affected range)"]
        current = blender.timeline(script, voice.load_manifest(script) if script.format != "text" else None)
        if [(s["id"], s["start"], s["end"]) for s in current["scenes"]] != [(s["id"], s["start"], s["end"]) for s in tl["scenes"]]:
            state, notes = "STALE", notes + ["the timeline changed (new voice)"]
        rows.append(_row("9 Blender render", state, "; ".join(notes)))
    else:
        rows.append(_row("9 Blender render", "missing"))

    clips = [clips_dir(script.slug) / f"{s.id}.mp4" for s in script.scenes]
    missing = [c.stem for c in clips if not c.exists()]
    rows.append(_row("9 clips", "missing" if missing else "ok", f"without: {', '.join(missing)}" if missing else ""))

    final = ROOT / "out" / f"{script.slug}.mp4"
    newest_input = max([t for t in [src, _mtime(b / "voice.json")] + [_mtime(c) for c in clips] if t] or [0])
    if not final.exists():
        rows.append(_row("10 out/mp4", "missing"))
    elif _mtime(final) < newest_input:
        rows.append(_row("10 out/mp4", "STALE", "script, voice or clip changed after the render"))
    else:
        rows.append(_row("10 out/mp4", "ok"))
    gate = b / "gates" / "final.json"
    if gate.exists() and final.exists():
        g = json.loads(gate.read_text(encoding="utf-8"))
        if _mtime(gate) < _mtime(final):
            rows.append(_row("10 final gate", "STALE", "run 'qa' again"))
        else:
            rows.append(_row("10 final gate", "ok" if g["ok"] else "ERROR",
                             f"{len(g['errors'])} error(s), {len(g['warnings'])} warning(s)"))
    else:
        rows.append(_row("10 final gate", "missing"))
    return rows


def show(script: Script, script_path: Path) -> None:
    rows = report(script, script_path)
    width = max(len(r[0]) for r in rows)
    for name, state, note in rows:
        print(f"  {name:<{width}}  {state:<12} {note}")
    line = metrics.timeline_line(script, script_path)
    if line:
        print(f"\n  Timeline: {line}")
