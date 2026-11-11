"""Final gate: checks out/<slug>.mp4 with objective measurements before it goes to the owner.

Writes build/<slug>/gates/final.json. ERROR = not ready; WARNING = look before approving.
Taste (image, timbre, rhythm) stays with the owner; here only what can be measured.
"""

import json
import re
import subprocess
import time
from pathlib import Path

from . import brand
from .render import find_clip
from .script import Script
from .timing import TARGET_SECONDS, scene_duration
from .util import ROOT, build_dir, duration

VOICE_OVER_SFX_LU = 8.0      # rule: effects at least 8 LU below the voice while it speaks
SPEAKING_LUFS = -27.0        # a 400 ms window with voice at this level or above counts as clear speech (sound design criterion)
TRUE_PEAK_MAX = -1.0         # dBTP
BLACK_MIN_SECONDS = 0.25
END_FADE_SECONDS = 4.0       # the end of the video fades out on purpose (end signal before the question)


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL).stdout
    return json.loads(out)


def _ffmpeg_log(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr


def _momentary(path: Path) -> list[tuple[float, float]]:
    """(second, momentary loudness in LUFS) every 100 ms."""
    log = _ffmpeg_log(["-i", str(path), "-af", "ebur128"])
    rows = []
    for t, m in re.findall(r"t:\s*([0-9.]+)\s+TARGET:.*?M:\s*(-?[0-9.]+|-inf)", log):
        rows.append((float(t), float("-inf") if m == "-inf" else float(m)))
    return rows


def _loudness(path: Path) -> tuple[float | None, float | None]:
    log = _ffmpeg_log(["-i", str(path), "-af", "ebur128=peak=true"])
    i = re.findall(r"I:\s*(-?[0-9.]+) LUFS", log)
    p = re.findall(r"Peak:\s*(-?[0-9.]+|-inf) dBFS", log)
    return (float(i[-1]) if i else None, float(p[-1]) if p and p[-1] != "-inf" else None)


def _black(path: Path) -> list[tuple[float, float]]:
    log = _ffmpeg_log(["-i", str(path), "-an", "-vf", f"blackdetect=d={BLACK_MIN_SECONDS}:pix_th=0.08"])
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", log)]


def check(script: Script, manifest: dict | None) -> dict:
    final = ROOT / "out" / f"{script.slug}.mp4"
    errors, warnings, measures = [], [], {}
    if not final.exists():
        raise SystemExit(f"There is no {final.relative_to(ROOT)}: run 'render' first.")
    manifest = manifest or {}

    info = _probe(final)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not video or not audio:
        errors.append("the file needs a video track and an audio track")
        return _write(script, final, errors, warnings, measures)

    # Formato: 1080x1920, 30 fps, yuv420p, bt709 marcado no arquivo.
    size = (video.get("width"), video.get("height"))
    fps = video.get("r_frame_rate", "0/1")
    num, den = (int(v) for v in fps.split("/"))
    measures.update(size=f"{size[0]}x{size[1]}", fps=round(num / den, 3) if den else 0,
                    pix_fmt=video.get("pix_fmt"), color=video.get("color_primaries"))
    if size != (brand.W, brand.H):
        errors.append(f"resolution {size[0]}x{size[1]}, expected {brand.W}x{brand.H}")
    if not den or abs(num / den - brand.FPS) > 0.01:
        errors.append(f"{fps} frames/s, expected {brand.FPS}")
    if video.get("pix_fmt") != "yuv420p":
        errors.append(f"pix_fmt {video.get('pix_fmt')}, expected yuv420p")
    if video.get("color_primaries") != "bt709":
        warnings.append(f"color tagged as {video.get('color_primaries')}, expected bt709")

    # Duration and track sync.
    total = float(info["format"]["duration"])
    v_dur, a_dur = float(video.get("duration", total)), float(audio.get("duration", total))
    expected = sum(scene_duration(s, manifest.get(s.id)) for s in script.scenes)
    measures.update(seconds=round(total, 2), video_seconds=round(v_dur, 3), audio_seconds=round(a_dur, 3),
                    expected_seconds=round(expected, 2))
    lo, hi = TARGET_SECONDS
    if total <= 60.0:
        errors.append(f"{total:.1f} s: TikTok only pays for videos over 1 minute")
    elif total < lo or total > hi:
        warnings.append(f"{total:.1f} s, outside the target of {lo:.0f} to {hi:.0f} s")
    if abs(v_dur - a_dur) > 1.5 / brand.FPS:
        warnings.append(f"video {v_dur:.3f} s and audio {a_dur:.3f} s differ by {abs(v_dur - a_dur) * 1000:.0f} ms")
    if abs(total - expected) > 0.25:
        warnings.append(f"duration {total:.2f} s differs from the sum of the scenes ({expected:.2f} s)")

    # Clips: placeholder card and a clip shorter than the scene (freezes the last frame).
    for scene in script.scenes:
        clip = find_clip(script.slug, scene.id)
        seconds = scene_duration(scene, manifest.get(scene.id))
        if not clip:
            errors.append(f"scene {scene.id} has no clip: the placeholder card came out")
        elif duration(clip) < seconds - 1.0 / brand.FPS:
            warnings.append(f"scene {scene.id}: clip of {duration(clip):.2f} s for a scene of {seconds:.2f} s "
                            "(the last frame freezes)")

    # Black frame outside the end.
    blacks = [(a, b) for a, b in _black(final) if b < total - END_FADE_SECONDS]
    measures["black_segments"] = [[round(a, 2), round(b, 2)] for a, b in blacks]
    for a, b in blacks:
        warnings.append(f"black screen from {a:.2f} to {b:.2f} s")

    # Loudness and peak of the final mix.
    integrated, peak = _loudness(final)
    measures.update(lufs=integrated, true_peak=peak)
    if peak is not None and peak > TRUE_PEAK_MAX:
        (errors if peak > -0.1 else warnings).append(f"true peak {peak:.1f} dBTP (maximum {TRUE_PEAK_MAX:.0f})")

    # Voice vs. effects (voice format only): a MEASUREMENT, not a gate. Isolated voice against the effects track before the
    # mix ducking, in 400 ms windows with clear speech. The numbers did not match the sound design ones
    # on moon-disappeared (33% against 9% of windows below 8 LU): until calibrated, it only informs.
    narration = build_dir(script.slug) / "render" / "narration.wav"
    effects = build_dir(script.slug) / "sfx" / "sfx.wav"
    if script.format != "text" and narration.exists() and effects.exists():
        fx = dict((round(t, 1), m) for t, m in _momentary(effects))
        diffs = sorted((round(m - fx[round(t, 1)], 1), round(t, 1)) for t, m in _momentary(narration)
                       if m >= SPEAKING_LUFS and round(t, 1) in fx)
        if diffs:
            measures["voice_over_sfx"] = {
                "windows": len(diffs),
                "below_8lu_pct": round(100 * sum(1 for d, _ in diffs if d < VOICE_OVER_SFX_LU) / len(diffs), 1),
                "p10_lu": diffs[len(diffs) // 10][0],
                "worst": [[t, d] for d, t in diffs[:5]],
            }
    return _write(script, final, errors, warnings, measures)


def _write(script: Script, final: Path, errors: list[str], warnings: list[str], measures: dict) -> dict:
    result = {"ok": not errors, "when": time.strftime("%Y-%m-%d %H:%M"), "file": final.relative_to(ROOT).as_posix(),
              "errors": errors, "warnings": warnings, "measures": measures}
    gates = build_dir(script.slug) / "gates"
    gates.mkdir(exist_ok=True)
    (gates / "final.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFinal gate ({final.name}): {'OK' if result['ok'] else 'NOT READY'}"
          f" · {measures.get('seconds', '?')} s · {measures.get('lufs', '?')} LUFS · peak {measures.get('true_peak', '?')} dBTP")
    for e in errors:
        print(f"  ERROR: {e}")
    for w in warnings:
        print(f"  WARNING: {w}")
    print(f"  report: {(gates / 'final.json').relative_to(ROOT)}")
    return result
