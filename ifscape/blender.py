"""Continuous 3D set built in Blender, in place of AI clips.

The <slug> script has a tools/blender/<slug>.py that builds the scene and animates each
segment inside the time window of its scene. This module:
  1. computes the timeline (from the generated narration, or by estimate without it);
  2. calls Blender in the background (test frames or the full animation);
  3. joins the frames into a video and cuts it into clips/<slug>/<id>.mp4, one per scene.
The normal render trims each clip to the exact time of the scene, so the cuts join without a jump.
"""

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import brand
from .script import Script
from .timing import estimated_duration, scene_duration
from .util import ROOT, build_dir, clips_dir, run

DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
MARKER = ".blender"          # marks that the clips in the folder came from Blender (may be overwritten)


def find_blender() -> Path:
    env = os.environ.get("BLENDER_EXE")
    for candidate in (env, str(DEFAULT_BLENDER), shutil.which("blender")):
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise SystemExit("Blender not found. Install it (winget install BlenderFoundation.Blender) "
                     "or set BLENDER_EXE in .env.")


STAGE_ENTRY = ROOT / "tools" / "stage" / "stage_main.py"


def legacy_script(slug: str) -> Path:
    return ROOT / "tools" / "blender" / f"{slug}.py"


def uses_stage(script: Script) -> bool:
    """Video made only from data ('stage' field in every scene) and without its own <slug>.py."""
    return not legacy_script(script.slug).exists() and all(s.stage for s in script.scenes)


def scene_script(script: Script) -> Path:
    return STAGE_ENTRY if uses_stage(script) else legacy_script(script.slug)


def timeline(script: Script, manifest: dict | None) -> dict:
    """Start and end frames of each scene (end exclusive), accumulated without losing rounding."""
    t, scenes = 0.0, []
    for scene in script.scenes:
        meta = manifest.get(scene.id) if manifest else None
        seconds = scene_duration(scene, meta) if manifest else estimated_duration(scene)
        start, t = round(t * brand.FPS), t + seconds
        row = {"id": scene.id, "start": start, "end": round(t * brand.FPS), "seconds": seconds, "stamp": scene.stamp}
        if scene.stage:
            row["stage"] = scene.stage
        scenes.append(row)
    estimated = manifest is None and script.format != "text"   # text only: reading time is already the final one
    return {"fps": brand.FPS, "frames": scenes[-1]["end"], "estimated": estimated, "scenes": scenes,
            "source": source_digest(script)}


def _source_files() -> list[Path]:
    """Code that builds the sets: tools/blender/*.py and the module subfolders (lib/), without the examples."""
    base = ROOT / "tools" / "blender"
    return sorted(p for p in base.rglob("*.py")
                  if "examples" not in p.relative_to(base).parts and "__pycache__" not in p.parts)


def _stage_files() -> list[Path]:
    """Data-driven video: depends only on the builder (tools/stage), the catalog and the little it imports from the kit.
    So touching another video's set does not invalidate the frames of a stage video."""
    base = ROOT / "tools" / "stage"
    own = [p for p in base.rglob("*") if p.suffix in (".py", ".json") and "__pycache__" not in p.parts
           and p.name not in ("catalog_scan.py", "sheet.py")]
    blender = ROOT / "tools" / "blender"
    return sorted(own + [blender / "kit.py", blender / "rigs.py", blender / "lib" / "anim_curves.py"])


def source_digest(script: Script | None = None) -> str:
    """Fingerprint of the set code: if it changes, the finished frames cannot be used to resume.
    Until 2026-10-24 it only looked at tools/blender/*.py, and a change in lib/ let a resume use old frames.
    With a stage script (uses_stage), only the builder counts; without a script, all of tools/blender counts as before."""
    digest = hashlib.sha1()
    for path in (_stage_files() if script is not None and uses_stage(script) else _source_files()):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _log_render(out: Path, mode: str, frames: int, seconds: float) -> None:
    """Appends the render time to blender/render_log.jsonl (basis for measuring cost per video)."""
    row = {"when": time.strftime("%Y-%m-%d %H:%M"), "mode": mode, "frames": frames, "seconds": round(seconds, 1),
           "s_per_frame": round(seconds / frames, 3) if frames else None}
    with (out / "render_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    rate = f", {row['s_per_frame']} s/frame" if frames else ""
    print(f"  Blender: {seconds / 60:.1f} min ({frames} frames{rate})")


def _check_clip_dir(slug: str, force: bool) -> Path:
    d = clips_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    foreign = [p.name for p in d.glob("*.mp4")]
    if foreign and not (d / MARKER).exists() and not force:
        raise SystemExit(f"clips/{slug}/ already has clips that did not come from Blender ({', '.join(foreign[:4])}…). "
                         "Use --force to replace them.")
    (d / MARKER).write_text("clips generated by 'python -m ifscape blender'\n", encoding="utf-8")
    return d


def _encode(frames_dir: Path, out: Path) -> None:
    run(["ffmpeg", "-y", "-framerate", str(brand.FPS), "-start_number", "1", "-i", str(frames_dir / "f_%04d.png"),
         "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(out)])


def _split(tl: dict, full: Path, clip_dir: Path) -> None:
    for sc in tl["scenes"]:
        out = clip_dir / f"{sc['id']}.mp4"
        run(["ffmpeg", "-y", "-i", str(full), "-vf",
             f"trim=start_frame={sc['start']}:end_frame={sc['end']},setpts=PTS-STARTPTS",
             "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(out)])
        print(f"  {out.relative_to(ROOT)}  ({sc['end'] - sc['start']} frames)")


def _parse_range(frames: str, total: int) -> tuple[int, int]:
    try:
        a, b = (int(v) for v in frames.split("-"))
    except ValueError:
        raise SystemExit(f"--frames expects START-END, e.g. 1-1640 (got '{frames}').") from None
    if not 1 <= a <= b <= total:
        raise SystemExit(f"--frames {frames} is outside the timeline (1 to {total}).")
    return a, b


def _prepare_partial(frames: str, frames_dir: Path, full: Path, total: int) -> None:
    """Redoes only the START-END range: the other frames come from the previous render (leftover PNGs, or
    extracted from full.mp4). Blender skips frames that already exist, so only the range is rendered."""
    a, b = _parse_range(frames, total)
    frames_dir.mkdir(exist_ok=True)
    have = len(list(frames_dir.glob("f_*.png")))
    if 0 < have < total:
        # interrupted render: the leftover PNGs belong to this set; Blender renders the missing ones.
        # Never extract full.mp4 over them (ants v2, 2026-10-26: full.mp4 was from an old version
        # and erased 1866 new frames).
        print(f"  {have} of {total} frames already exist; Blender renders the {total - have} that are missing and the range")
    elif have == 0:
        if not full.exists():
            raise SystemExit("--frames needs the frames of the previous render (or full.mp4), and there are none.")
        print(f"  extracting the frames of the previous render from {full.name}")
        tmp = frames_dir / "_extract"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(full), "-start_number", "1",
             str(tmp / "f_%04d.png")])
        got = sorted(tmp.glob("f_*.png"))
        if len(got) != total:
            shutil.rmtree(tmp, ignore_errors=True)
            raise SystemExit(f"full.mp4 has {len(got)} frames and the timeline has {total}: it is from another version; "
                             "redo the whole render.")
        for f in got:
            f.replace(frames_dir / f.name)
        tmp.rmdir()
    for f in range(a, b + 1):
        (frames_dir / f"f_{f:04d}.png").unlink(missing_ok=True)
    print(f"  redoing only frames {a} to {b} ({b - a + 1} of {total})")


def render(script: Script, manifest: dict | None, stills: str | None = None, force: bool = False,
           fresh: bool = False, frames: str | None = None) -> Path:
    """stills='120,400' renders only those frames (PNG) for review; frames='1-1640' redoes only that range
    of the animation and reuses the rest of the previous render; with neither, the whole animation.
    Use frames only when the set change does not affect anything outside the range."""
    entry = scene_script(script)
    if not entry.exists():
        raise SystemExit(f"There is no 3D set for this script: create {legacy_script(script.slug).relative_to(ROOT)} "
                         "or give every scene a 'stage' (tools/stage/build.py).")
    out = build_dir(script.slug) / "blender"
    out.mkdir(exist_ok=True)
    tl = timeline(script, manifest)
    tl_path = out / "timeline.json"
    tl_text = json.dumps(tl, indent=2)
    tl_path.write_text(tl_text, encoding="utf-8")
    total = tl["frames"] / brand.FPS
    note = " (estimated: narration not generated yet)" if tl["estimated"] else ""
    print(f"  timeline: {tl['frames']} frames, {total:.1f} s{note}")

    clip_dir = None if stills else _check_clip_dir(script.slug, force)
    frames_dir = out / "frames"
    # The signature (timeline + set code) lives inside the frames folder: only animation renders
    # write it, so test frames do not fool the "resume".
    stamp = frames_dir / "frames.json"
    if frames and not stills:
        _prepare_partial(frames, frames_dir, out / "full.mp4", tl["frames"])
        stamp.write_text(tl_text, encoding="utf-8")
    elif not stills:
        same = stamp.exists() and stamp.read_text(encoding="utf-8") == tl_text
        if frames_dir.exists() and same and not fresh:
            done = len(list(frames_dir.glob("f_*.png")))
            print(f"  resuming: {done} frames already done (same set and timeline); use --fresh to redo")
        elif frames_dir.exists():
            shutil.rmtree(frames_dir)      # frames from another set or another timeline
        frames_dir.mkdir(exist_ok=True)
        stamp.write_text(tl_text, encoding="utf-8")
    mode = ["--stills", stills] if stills else ["--anim"]
    cmd = [str(find_blender()), "-b", "-P", str(entry), "--", "--timeline", str(tl_path), "--out", str(out), *mode]
    before = len(list(frames_dir.glob("f_*.png"))) if not stills else 0
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode != 0 or "Traceback" in proc.stderr + proc.stdout:
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
        raise RuntimeError(f"O Blender falhou:\n{tail}")
    rendered = len(stills.split(",")) if stills else len(list(frames_dir.glob("f_*.png"))) - before
    _log_render(out, "stills" if stills else ("frames " + frames if frames else "anim"), rendered,
                time.monotonic() - t0)
    if "Shadow buffer full" in proc.stdout + proc.stderr:
        print("  Warning: Blender reported 'Shadow buffer full' (shadow will flicker): increase "
              "scene.eevee.shadow_pool_size and redo the range.")

    if stills:
        print(f"  test frames in {out.relative_to(ROOT)}/still_*.png")
        return out
    full = out / "full.mp4"
    _encode(frames_dir, full)
    print(f"  continuous video: {full.relative_to(ROOT)}")
    _split(tl, full, clip_dir)
    return full
