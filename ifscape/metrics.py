"""Video metrics read from disk (measurement plan): build/<slug>/metrics.json.

Almost everything comes from time stamps and from gates/render_log; the 'analytics' block is filled by hand after
publication (retention at 1 s, 3 s and 10 s, completion) and the command preserves what is already there. Script hours is an
approximation (thesis.md until the first recorded voice): editing the thesis again moves the start earlier.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import timing
from .script import Script
from .util import ROOT, build_dir, clips_dir

ROUND_FILES = {"script_review": "review*.md", "factcheck": "factcheck*.md", "narrative": "narrative*.md"}


def _stamp(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def stage_times(script: Script, script_path: Path | None = None) -> list[tuple[str, float]]:
    """When each stage wrote its first file, in production order (disk time stamps; lean
    mode: measure the time of one session per video). A missing stage is left out."""
    b = build_dir(script.slug)
    voices = sorted((b / "voice").glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    clips = sorted(clips_dir(script.slug).glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    final = ROOT / "out" / f"{script.slug}.mp4"
    files = [("premise", b / "premise.md"), ("thesis", b / "thesis.md"), ("facts", b / "facts.md"),
             ("script", script_path), ("review", b / "review.md"), ("factcheck", b / "factcheck.md"),
             ("voice", voices[0] if voices else None), ("clips", clips[0] if clips else None), ("video", final)]
    return sorted(((n, p.stat().st_mtime) for n, p in files if p and p.exists()), key=lambda x: x[1])


def timeline_line(script: Script, script_path: Path | None = None) -> str:
    """'premise 10:02 > thesis 10:15 > ... (3.2 h from first to last)' or '' if there are no time stamps."""
    times = stage_times(script, script_path)
    if len(times) < 2:
        return ""
    hours = (times[-1][1] - times[0][1]) / 3600
    return " > ".join(f"{n} {datetime.fromtimestamp(t):%d/%m %H:%M}" for n, t in times) + f"  ({hours:.1f} h from first to last)"


def collect(script: Script, script_path: Path | None = None) -> dict:
    b = build_dir(script.slug)
    out: dict = {"slug": script.slug, "when": datetime.now().strftime("%Y-%m-%d %H:%M")}

    times = stage_times(script, script_path)
    if times:
        out["stages"] = {n: _stamp(t) for n, t in times}
        out["hours_first_to_last"] = round((times[-1][1] - times[0][1]) / 3600, 1)

    rounds = {k: len(list(b.glob(pat))) for k, pat in ROUND_FILES.items()}
    out["review_rounds"] = rounds

    thesis, voices = b / "thesis.md", sorted((b / "voice").glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    if thesis.exists() and voices:
        hours = (voices[0].stat().st_mtime - thesis.stat().st_mtime) / 3600
        out["script_hours"] = {"thesis": _stamp(thesis.stat().st_mtime), "first_voice": _stamp(voices[0].stat().st_mtime),
                                   "hours": round(hours, 1) if hours > 0 else None}   # thesis written after the voice (old video)

    if script.format != "text":
        model = script.voice_model or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        seconds, words = timing.estimate_total(script.scenes, model)
        est = {"model": model, "words": words, "estimated_seconds": round(seconds, 1)}
        gate = b / "gates" / "final.json"
        if gate.exists():
            g = json.loads(gate.read_text(encoding="utf-8"))
            real = g["measures"]["seconds"]
            est |= {"actual_seconds": real, "error_pct": round(100 * (seconds - real) / real, 1)}
            out["final_gate"] = {"ok": g["ok"], "errors": g["errors"], "warnings": g["warnings"],
                                  "lufs": g["measures"].get("lufs"), "true_peak_dbtp": g["measures"].get("true_peak"),
                                  "av_drift_s": round(g["measures"]["video_seconds"] - g["measures"]["audio_seconds"], 3)}
        out["duration"] = est

    log = b / "blender" / "render_log.jsonl"
    if log.exists():
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        anim = [r for r in rows if r["mode"] == "anim"]
        partial = [r for r in rows if r["mode"].startswith("frames")]
        stills = [r for r in rows if r["mode"] == "stills"]
        done = anim + partial
        out["render"] = {"stills_runs": len(stills)} if not done else {
            "full": len(anim), "partial": len(partial), "stills_runs": len(stills),
            "animated_frames": sum(r["frames"] for r in done),
            "minutes": round(sum(r["seconds"] for r in done) / 60, 1),
            "s_per_frame": round(sum(r["seconds"] for r in done) / max(sum(r["frames"] for r in done), 1), 3),
        }

    lessons = Path(__file__).resolve().parent.parent / ".claude" / "agents" / "lessons.md"
    out["lessons_total"] = (len(re.findall(r"^\|(?!\s*(?:Video|-{3})\s*\|)", lessons.read_text(encoding="utf-8"), re.M))
                              if lessons.exists() else None)
    return out


def write(script: Script, script_path: Path | None = None) -> Path:
    path = build_dir(script.slug) / "metrics.json"
    data = collect(script, script_path)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        for k in ("analytics", "reopenings"):          # filled by hand
            if k in old:
                data[k] = old[k]
    data.setdefault("analytics", {})
    data.setdefault("reopenings", [])      # [{"what": ..., "cost": "re-record N scenes = X characters; ..."}]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
