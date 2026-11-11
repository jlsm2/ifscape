"""List of what to paste into each tool: image (Nano Banana) and motion (Seedance or Veo), per scene."""

import math
from pathlib import Path

from .script import Scene, Script
from .timing import estimated_duration, scene_duration
from .util import build_dir, clips_dir, refs_dir

# Seedance accepts duration in whole seconds, from 4 s.
MIN_CLIP_SECONDS = 4
# In Flow, Veo always generates 8 s and charges per clip; the render trims the excess.
VEO_SECONDS = 8
# A clip up to 0.3 s shorter than the scene is acceptable: the render freezes the last frame and it goes unnoticed.
FREEZE_TOLERANCE = 0.3
# Measured on 2026-10-19: Seedance 2.0 Mini, 720P, no promotion.
SEEDANCE_CREDITS_PER_SECOND = 28

TOOL_SETUP = {
    "seedance": "SEEDANCE · AI video · 2.0 Mini · 9:16 · 720P · {seconds} s",
    "veo": "VEO (Flow) · Veo 3.1 Lite · 9:16 · x1 · 8 s fixo",
}


def clip_seconds(scene_seconds: float) -> int:
    """Smallest whole duration that covers the scene: avoids paying for seconds the render trims."""
    return max(MIN_CLIP_SECONDS, math.ceil(scene_seconds - FREEZE_TOLERANCE))


def _header(script: Script, durations: list[float]) -> list[str]:
    seedance_s = sum(clip_seconds(d) for s, d in zip(script.scenes, durations) if s.tool == "seedance")
    veo_n = sum(1 for s in script.scenes if s.tool == "veo")
    return [
        script.title,
        "",
        "Method: 1) generate the IMAGE in Nano Banana (9:16) and approve it;",
        "        2) animate it in VIDEO with the image as the first frame and paste only the motion prompt.",
        f"Images in: {refs_dir(script.slug)}\\<scene>.jpg",
        f"Clips in:   {clips_dir(script.slug)}\\<scene>.mp4",
        f"Seedance: {seedance_s} s in total (~{seedance_s * SEEDANCE_CREDITS_PER_SECOND} credits). "
        f"Veo: {veo_n} clipes.",
        "Copy only the English texts, never the configuration lines.",
        "",
    ]


def _scene_block(scene: Scene, seconds: float, note: str) -> list[str]:
    setup = TOOL_SETUP[scene.tool].format(seconds=clip_seconds(seconds))
    lines = [f"===== SCENE {scene.id} · the scene lasts {seconds:.1f} s{note}", f"Where: {setup}"]
    if scene.tool == "veo" and seconds > VEO_SECONDS + FREEZE_TOLERANCE:
        lines.append(f"WARNING: the scene exceeds Veo's {VEO_SECONDS} s; the last frame would be frozen "
                     f"{seconds - VEO_SECONDS:.1f} s. Split the scene or use Seedance.")
    lines.append("")
    if scene.full_motion:
        lines += ["1) IMAGEM (Nano Banana):", scene.full_prompt, "",
                  "2) MOTION (paste into the video tool, with the image as a reference):",
                  scene.full_motion, ""]
    else:
        lines += ["VIDEO straight from text (no image):", scene.full_prompt, ""]
    lines += [f"-> save: refs/{scene.id}.jpg and clips/{scene.id}.mp4", ""]
    return lines


FLOW_IMAGES = (
    "STEP 1 of 2. Generate images only, no videos yet. Make one vertical 9:16 image for each scene below, "
    "all in the same visual style, so they look like shots from the same short film. Keep the same look "
    "across all images: {style}. Generate them in the order listed. Never write scene numbers or any text "
    "inside the images. Do not animate anything yet."
)
FLOW_VIDEOS = (
    "STEP 2 of 2. Now animate each approved image into a video, using the image as the first frame. "
    "Use Veo 3.1 Lite, vertical 9:16, one video per scene, 8 seconds each. Keep the same camera and style "
    "as the image. Use only the motion described below for each scene. No text, no logos, no music needed."
)


def write_flow_batch(script: Script) -> Path | None:
    """Two messages for the Flow agent: all the images, and then all the videos."""
    scenes = [s for s in script.scenes if s.tool == "veo" and s.motion]
    if not scenes:
        return None
    images = [FLOW_IMAGES.format(style=scenes[0].style), ""]
    images += [f"Scene {s.id}: {s.prompt}" + (f" ({s.style})" if s.style != scenes[0].style else "")
               for s in scenes]
    videos = [FLOW_VIDEOS, ""] + [f"Scene {s.id}: {s.full_motion}" for s in scenes]
    out = build_dir(script.slug) / "flow-lote.txt"
    out.write_text("\n".join(images) + "\n\n--------\n\n" + "\n".join(videos) + "\n", encoding="utf-8")
    return out


def write(script: Script, manifest: dict | None) -> Path:
    durations = [scene_duration(s, (manifest or {}).get(s.id)) if manifest else estimated_duration(s)
                 for s in script.scenes]
    note = "" if manifest else " (estimated: run 'voice' for the exact time)"
    lines = _header(script, durations)
    for scene, seconds in zip(script.scenes, durations):
        lines += _scene_block(scene, seconds, note)
    out = build_dir(script.slug) / "prompts.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
