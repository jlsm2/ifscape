"""Delivery sheet of a finished video: what the owner reads at the end (self-review gates G3, G6, G7, G8).

Usage: py tools/qa/delivery.py <slug> [--no-sheet]
Reads scripts/<slug>.json, out/<slug>.mp4, build/<slug>/gates/final.json, build/<slug>/blender/render_log.jsonl,
build/<slug>/sfx/*.wav and build/<slug>/briefing.md; runs `py -m ifscape lint` and `tools/qa/sfx_check.py` and (without --no-sheet)
`tools/qa/final_sheet.py`. Writes build/<slug>/delivery.md with the automatic parts filled in and the judgment
parts (what I decided, what stayed weak, hypothesis) marked "FILL IN": the orchestrator completes them before answering the owner.
Read-only on the video; renders nothing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, cwd=ROOT)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def render_cost(slug: str) -> str:
    log = ROOT / "build" / slug / "blender" / "render_log.jsonl"
    if not log.exists():
        return "no render log"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    full = [r for r in rows if r.get("mode") != "stills" and r.get("frames")]
    if not full:
        return "only stills logged"
    hours = sum(r.get("seconds", 0.0) for r in full) / 3600
    last = full[-1]
    return f"{hours:.1f} h of Blender in {len(full)} render(s); last {last.get('s_per_frame', '?')} s/frame, {last.get('frames')} frames"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--no-sheet", action="store_true")
    args = ap.parse_args()
    slug = args.slug
    script = ROOT / "scripts" / f"{slug}.json"
    video = ROOT / "out" / f"{slug}.mp4"
    build = ROOT / "build" / slug
    if not script.exists() or not video.exists():
        sys.exit(f"Missing {script if not script.exists() else video}")
    data = json.loads(script.read_text(encoding="utf-8"))

    # G7: qa gate
    gates = {}
    gp = build / "gates" / "final.json"
    if gp.exists():
        gates = json.loads(gp.read_text(encoding="utf-8"))
    m = gates.get("measures", {})
    g7 = "OK" if gates.get("ok") else "FAILED"
    g7_line = (f"{m.get('seconds', '?')} s, {m.get('size', '?')}, {m.get('lufs', '?')} LUFS, peak {m.get('true_peak', '?')} dBTP; "
               f"errors: {gates.get('errors') or 'none'}; warnings: {gates.get('warnings') or 'none'}")

    # G3/G8: lint
    code, lint_out = run([sys.executable, "-m", "ifscape", "lint", f"scripts/{slug}.json"])
    lint_lines = [l.strip() for l in lint_out.splitlines() if "[HIGH]" in l or "[MEDIUM]" in l]
    highs = [l for l in lint_lines if "[HIGH]" in l]
    g3 = "OK" if not highs else f"{len(highs)} HIGH"

    # G6: silent new effects?
    sfx_dir = build / "sfx"
    wavs = sorted(p for p in sfx_dir.glob("*.wav") if not p.name.startswith(("lote_", "sfx"))) if sfx_dir.exists() else []
    mute = []
    if wavs:
        c, o = run([sys.executable, "tools/qa/sfx_check.py", *[str(p) for p in wavs]])
        mute = [l.replace(str(ROOT) + "\\", "").strip() for l in o.splitlines() if "SILENT" in l.upper() or "ALMOST" in l.upper()]
    g6 = "OK" if not mute else f"{len(mute)} suspect file(s)"
    n_amb = len(data.get("ambience", []))
    n_sfx = len(data.get("sfx", []))

    # frame sheet
    sheet = ""
    if not args.no_sheet:
        c, o = run([sys.executable, "tools/qa/final_sheet.py", f"out/{slug}.mp4"])
        sheet = o.strip()

    brief = build / "briefing.md"
    brief_txt = brief.read_text(encoding="utf-8").strip() if brief.exists() else "(no briefing.md: video predates the briefing process)"
    scenes = data.get("scenes", [])
    words = sum(len(t.split()) for s in scenes for t in s.get("text", []))

    md = f"""# Delivery: {data.get('title', slug)} ({date.today().isoformat()})

## Product
- Video: `out/{slug}.mp4` ({m.get('seconds', '?')} s) · cover: `out/{slug}.cover.jpg` · post: `out/{slug}.post.txt` (paste only the "PASTE INTO POST" block)
- Scenes: {len(scenes)} · words on screen: {words} · effects: {n_sfx} cues, {n_amb} ambience layers
- Frame sheet: `build/{slug}/final/final_sheet.jpg`

## Gates
| Gate | Result | Detail |
| --- | --- | --- |
| G3 script (lint) | {g3} | {len(lint_lines)} lint finding(s); {'; '.join(highs[:3]) if highs else 'no HIGH'} |
| G6 sound | {g6} | {n_sfx} cues and {n_amb} layers; {'; '.join(mute[:3]) if mute else 'no silent effect'}. FILL IN: did the sound designer run? audible loop? |
| G7 assembly | {g7} | {g7_line} |
| G1, G2, G4, G5, G8 | FILL IN | premise, facts, set still approved on <date>, animation, post |

## Cost
- Render: {render_cost(slug)}
- Tokens and agents: FILL IN (research, reviews, sound design, Gemini: candidates received / verified / false)

## What I decided (FILL IN, 3 to 6 lines)
- set, panel, sound, narration, where I did not follow the briefing and why

## What stayed weak (FILL IN, honest)
- residue from the gates that failed in round 2; what I would change with more time

## Not verified (FILL IN; never count as approved)
- criterion I could not check and why (e.g. sync of a cue without a visible contact frame)

## Retention hypothesis
- FILL IN (table moment → change → what to expect on the retention curve)

## Owner's pending items
- Approve the video; post on the 3 platforms with the follower credit in the description; answer the comment.

## Briefing (contract)
{brief_txt}

## Frames and audio
```
{sheet}
```
"""
    out = build / "delivery.md"
    out.write_text(md, encoding="utf-8")
    print(f"Delivery: {out}")
    print(f"  G3 {g3} · G6 {g6} · G7 {g7}")


if __name__ == "__main__":
    main()
