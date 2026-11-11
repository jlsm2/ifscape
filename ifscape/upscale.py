"""Upscales the clips with AI (Real-ESRGAN, runs on the GPU via Vulkan) before the render.

The generators deliver 720p; the render scales down to 1080x1920. Upscaling 2x and then downscaling
leaves edges and textures sharper than stretching 720p directly.
Output in clips/<slug>/hd/<id>.mp4; the render uses this version when it exists.
"""

import json
import shutil
import subprocess
from pathlib import Path

from . import brand
from .script import Script
from .util import ROOT, build_dir, clips_dir, run

ESRGAN_EXE = ROOT / "tools" / "realesrgan" / "realesrgan-ncnn-vulkan.exe"
ESRGAN_MODEL = "realesr-animevideov3"  # made for animation: matches flat-color low-poly
ESRGAN_SCALE = 2
HD_CRF = 16
CLIP_EXTS = (".mp4", ".mov", ".webm", ".mkv")


def hd_dir(slug: str) -> Path:
    return clips_dir(slug) / "hd"


def _source_clip(slug: str, scene_id: str) -> Path | None:
    for ext in CLIP_EXTS:
        p = clips_dir(slug) / f"{scene_id}{ext}"
        if p.exists():
            return p
    return None


def _width(clip: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width", "-of", "json", str(clip)],
                         capture_output=True, text=True, check=True).stdout
    return int(json.loads(out)["streams"][0]["width"])


def _frame_rate(clip: Path) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "json", str(clip)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]["r_frame_rate"]


def _upscale_clip(clip: Path, out: Path, work: Path) -> None:
    frames_in, frames_out = work / "in", work / "out"
    shutil.rmtree(work, ignore_errors=True)
    frames_in.mkdir(parents=True)
    frames_out.mkdir()
    try:
        run(["ffmpeg", "-y", "-i", str(clip), "-an", str(frames_in / "%06d.png")])
        run([str(ESRGAN_EXE), "-i", str(frames_in), "-o", str(frames_out),
             "-n", ESRGAN_MODEL, "-s", str(ESRGAN_SCALE), "-f", "png"])
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-y", "-framerate", _frame_rate(clip), "-i", str(frames_out / "%06d.png"),
             "-c:v", "libx264", "-preset", "medium", "-crf", str(HD_CRF), "-pix_fmt", "yuv420p", str(out)])
    finally:
        shutil.rmtree(work, ignore_errors=True)  # the PNG frames take hundreds of MB per clip


def upscale(script: Script, force: bool = False) -> None:
    if not ESRGAN_EXE.exists():
        raise SystemExit(f"Real-ESRGAN not found at {ESRGAN_EXE}. See the README.")
    work_root = build_dir(script.slug) / "upscale"
    for scene in script.scenes:
        clip = _source_clip(script.slug, scene.id)
        if not clip:
            print(f"  scene {scene.id}: no clip, skipped")
            continue
        out = hd_dir(script.slug) / f"{scene.id}.mp4"
        if _width(clip) >= brand.W:
            print(f"  scene {scene.id}: already {brand.W}p or more, skipped")
            continue
        if out.exists() and not force and out.stat().st_mtime >= clip.stat().st_mtime:
            print(f"  scene {scene.id}: already upscaled, kept")
            continue
        print(f"  scene {scene.id}: upscaling {clip.name}…", flush=True)
        _upscale_clip(clip, out, work_root / scene.id)
