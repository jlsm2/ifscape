"""Assembly: scenes with stamp, caption and handle, narration and optional music track, into a 9:16 MP4."""

import json
import re
import subprocess
from pathlib import Path

from . import brand, cover, graphics, panel, sfx
from .script import Script
from .timing import Chunk, chunks, scene_duration
from .util import ROOT, build_dir, clips_dir, duration, run

CLIP_EXTS = (".mp4", ".mov", ".webm", ".mkv")
# Color standard declared in the file: without it Instagram may interpret it wrongly and wash out the dark tones.
COLOR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
# Music track: louder in the silences; the voice compresses (ducks) the music while it speaks.
MUSIC_VOLUME = 0.30
DUCK_THRESHOLD = 0.02
DUCK_RATIO = 8
DUCK_ATTACK_MS = 20
DUCK_RELEASE_MS = 400
# Effects under the voice are lowered much less than the music: with the music ducking (12 dB per sentence) the ambience
# disappeared, because the voice speaks almost the whole video (sound design finding, bacteria-disappeared).
EFFECTS_DUCK_THRESHOLD = 0.03
EFFECTS_DUCK_RATIO = 3
MUSIC_FADE_IN = 0.5
MUSIC_FADE_OUT = 1.5
MIN_TIKTOK_SECONDS = 61.0
# End of the final question: fade that hides the breath of the last consonant.
CLOSING_FADE = 0.2
SPEECH_FLOOR_DB = -50
MASTER_TRUE_PEAK = -1.5     # dBTP of the final mp4 (AAC overshoots the WAV peak a little)


def find_clip(slug: str, scene_id: str) -> Path | None:
    """Prefers the upscaled version (clips/<slug>/hd/, 'upscale' command) when it is newer than the original."""
    d = clips_dir(slug)
    if not d.exists():
        return None
    for ext in CLIP_EXTS:
        p = d / f"{scene_id}{ext}"
        if p.exists():
            hd = d / "hd" / f"{scene_id}.mp4"
            return hd if hd.exists() and hd.stat().st_mtime >= p.stat().st_mtime else p
    return None


CLOSING_QUESTION = "what should i imagine next"


def _is_closing(text: str) -> bool:
    return CLOSING_QUESTION in text.lower()


def _has_panel(scene, meta, previous_stamp: str | None) -> bool:
    return any(v is not None for v in panel.values(scene.stamp, previous_stamp, scene.counter,
                                                   scene_duration(scene, meta)))


def _karaoke_segments(ch: Chunk, words: list[dict]) -> list[tuple[float, float, int]]:
    """(start, end, active word) inside the chunk: the box stays on the word from its start until the next one begins
    (at most KARAOKE_HOLD after its end); before the 1st word and in silences, the chunk without a box (-1)."""
    frame = 1.0 / brand.FPS
    segs, t = [], ch.start
    for j, w in enumerate(words):
        nxt = min(ch.end, words[j + 1]["start"]) if j + 1 < len(words) else ch.end
        start = min(max(t, float(w["start"])), nxt)
        if start - t >= frame:
            segs.append((t, start, -1))
        end = max(start, min(nxt, float(w["end"]) + brand.KARAOKE_HOLD))
        if end - start > 0:
            segs.append((start, end, j))
        if nxt - end >= frame:
            segs.append((end, nxt, -1))
        t = max(end, nxt) if nxt - end >= frame else end
    return segs


def _scene_video(script: Script, scene, meta, seconds: float, work: Path, handle_png: Path,
                 previous_stamp: str | None, fade_in: bool = False, fade_out: bool = False,
                 clock_start: float = 0.0, video_t: float = 0.0) -> tuple[Path, bool]:
    clip = find_clip(script.slug, scene.id)
    inputs, filters = [], []

    if clip:
        inputs += ["-i", str(clip)]
    else:
        card = graphics.placeholder(scene.id, scene.full_prompt, seconds, work / f"{scene.id}_card.png")
        inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-i", str(card)]

    filters.append(
        f"[0:v]scale={brand.W}:{brand.H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={brand.W}:{brand.H},setsar=1,fps={brand.FPS},"
        f"tpad=stop_mode=clone:stop_duration=120,trim=duration={seconds},setpts=PTS-STARTPTS"
        + (f",fade=t=in:st=0:d={scene.fade_in}" if scene.fade_in else "")
        + (f",fade=t=out:st={max(0.0, seconds - scene.fade_out):.3f}:d={scene.fade_out}" if scene.fade_out else "")
        + "[v0]"
    )
    last, n = "v0", 1

    scene_chunks = chunks(scene, meta, seconds)
    if script.format != "text" and scene.on_screen and script.panel:
        # With voice, the opening question also becomes the big title (cover.hook) from frame 0; the line
        # repeats the question, so the small caption would come out duplicated (QA finding, bacteria-disappeared).
        scene_chunks = [Chunk(scene.on_screen, 0.0, seconds)]
    # Start of the end card in this scene, if any: the panel has to disappear before it, otherwise it shows through the
    # card while it fades in (QA finding: "10,000 years" on top of the card text).
    card_at = next((ch.start for ch in scene_chunks
                    if script.format == "text" and script.show_end_card and _is_closing(ch.text)), None)

    vals = panel.values(scene.stamp, previous_stamp, scene.counter, seconds, clock_start,
                        script.now_clock, script.now_clock_from)
    label = scene.counter.label if scene.counter else scene.panel_label
    hud_label = None
    subs = None
    if script.panel_clock and scene.counter and scene.counter.unit != "clock":
        # Big damage number and a small linear stopwatch under it
        subs = panel.clock_subs(len(vals), video_t - script.panel_clock_from)
    # "panel": false (2D series) turns off the panel and the stamp for the whole video
    layer = panel.layer(label, scene.panel_sub, scene.panel_sub_at, vals, work, scene.id,
                        scene.panel_rows, script.panel_style, subs) if script.panel else None
    if layer:
        args, _ = layer
        inputs += args
        # The panel disappears and returns with a fade when the neighboring scene has no panel (it used to cut in one frame).
        fades = ""
        if fade_in:
            fades += f",fade=t=in:st=0:d={brand.PANEL_FADE}:alpha=1"
        if card_at is not None:
            fades += f",fade=t=out:st={max(0.0, card_at - brand.PANEL_FADE):.3f}:d={brand.PANEL_FADE}:alpha=1"
        elif fade_out:
            fades += f",fade=t=out:st={seconds - brand.PANEL_FADE:.3f}:d={brand.PANEL_FADE}:alpha=1"
        filters.append(f"[{n}:v]format=rgba,fps={brand.FPS}{fades}[p{n}]")
        # The number sequence ends on the last frame; eof_action=repeat holds the final value on screen.
        if script.panel_style == "hud":
            # The HUD sits at the top, where the title gradient passes: it comes in last (over the caption and the
            # title), otherwise the gradient erases it (seen in testing).
            hud_label, n = f"p{n}", n + 1
        else:
            filters.append(f"[{last}][p{n}]overlay={brand.STAMP_XY[0]}:{brand.STAMP_XY[1]}:eof_action=repeat[v{n}]")
            last, n = f"v{n}", n + 1

    # Karaoke (caption_style "karaoke", voice only): the words from voice.json, in the order of the chunks
    karaoke = (list(meta["words"]) if script.caption_style == "karaoke" and script.format != "text" and meta
               and meta.get("words") and not (scene.on_screen and script.panel) else None)
    wi = 0
    flat = scene.flat or {}
    caption_y = flat.get("caption_y", brand.KARAOKE_CLOSE_Y if flat.get("shot") in ("close", "duo")
                         else brand.KARAOKE_CENTER_Y)
    for k, ch in enumerate(scene_chunks):
        png_path = work / f"{scene.id}_cap{k:02d}.png"
        if script.format == "text" and script.show_end_card and _is_closing(ch.text):
            # The final question becomes the full-screen end card, fading in over the scene.
            png = graphics.end_card(script.end_card, ch.text, png_path)
            dur = ch.end - ch.start
            fade = min(brand.TEXT_FADE * 2, dur / 3)
            inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{dur + 1:.3f}", "-i", str(png)]
            filters.append(f"[{n}:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1,"
                           f"setpts=PTS-STARTPTS+{ch.start}/TB[c{n}]")
            filters.append(f"[{last}][c{n}]overlay=0:0:eof_action=pass[v{n}]")
        elif scene.on_screen and script.panel:
            # Opening question in the cover poster style, already at frame 0 (no fade in): 3 of the 8
            # viral videos use the first frame as the cover (docs/covers.md). Fades out.
            png = cover.hook(ch.text, scene.highlight, png_path)
            dur = ch.end - ch.start
            fade = min(brand.TEXT_FADE * 2, dur / 4)
            fade_in = f"fade=t=in:st=0:d={fade}:alpha=1," if ch.start > 0 else ""
            inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{dur:.3f}", "-i", str(png)]
            filters.append(f"[{n}:v]format=rgba,{fade_in}fade=t=out:st={dur - fade:.3f}:d={fade}:alpha=1,"
                           f"setpts=PTS-STARTPTS+{ch.start}/TB[c{n}]")
            filters.append(f"[{last}][c{n}]overlay=0:0:eof_action=pass[v{n}]")
        elif script.format == "text":
            # Text only: small sentences at the bottom, one at a time, with a fade.
            if scene.on_screen:
                size, center_y, kind = brand.TEXT_HOOK_SIZE, brand.TEXT_HOOK_CENTER_Y, "bold"
            else:
                size, center_y, kind = brand.TEXT_CAPTION_SIZE, brand.TEXT_CAPTION_CENTER_Y, "text"
            png = graphics.caption(ch.text, scene.highlight, png_path, size, brand.TEXT_CAPTION_MAX_W, kind, scrim=scene.scrim)
            dur = ch.end - ch.start
            fade = min(brand.TEXT_FADE, dur / 4)
            inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{dur:.3f}", "-i", str(png)]
            filters.append(
                f"[{n}:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1,"
                f"fade=t=out:st={dur - fade:.3f}:d={fade}:alpha=1,setpts=PTS-STARTPTS+{ch.start}/TB[c{n}]"
            )
            filters.append(
                f"[{last}][c{n}]overlay=x=(W-w)/2:y={center_y}-h/2:eof_action=pass[v{n}]"
            )
        elif karaoke:
            # Karaoke: one PNG per word of the chunk (same layout), each at the time of the word in voice.json
            words, wi = karaoke[wi:wi + len(ch.text.split())], wi + len(ch.text.split())
            for start, end, active in _karaoke_segments(ch, words):
                png = graphics.karaoke(ch.text, active, work / f"{scene.id}_cap{k:02d}_w{active + 1:02d}.png")
                inputs += ["-i", str(png)]
                filters.append(f"[{last}][{n}:v]overlay=x=0:y={caption_y}-h/2:"
                               f"enable='gte(t,{start:.3f})*lt(t,{end:.3f})'[v{n}]")
                last, n = f"v{n}", n + 1
            continue
        else:
            png = graphics.caption(ch.text, scene.highlight, png_path, scrim=scene.scrim)
            inputs += ["-i", str(png)]
            filters.append(
                f"[{last}][{n}:v]overlay=x=(W-w)/2:y={brand.CAPTION_CENTER_Y}-h/2:"
                f"enable='gte(t,{ch.start})*lt(t,{ch.end})'[v{n}]"
            )
        last, n = f"v{n}", n + 1

    if scene.fact:
        # Fact card with a source ('fact' field): fades in and out, under the HUD, on the left.
        fact = scene.fact
        t0 = min(fact["t"], max(0.0, seconds - 2.0))
        dur = min(fact["dur"], seconds - t0)
        png = graphics.fact_card(fact["value"], fact["text"], work / f"{scene.id}_fact.png")
        fade = brand.FACT_FADE
        fx, fy = brand.FACT_XY if script.panel_style == "hud" else brand.FACT_XY_SIDE
        inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{dur:.3f}", "-i", str(png)]
        filters.append(f"[{n}:v]format=rgba,fade=t=in:st=0:d={fade}:alpha=1,"
                       f"fade=t=out:st={dur - fade:.3f}:d={fade}:alpha=1,setpts=PTS-STARTPTS+{t0}/TB[c{n}]")
        filters.append(f"[{last}][c{n}]overlay={fx}:{fy}:eof_action=pass[v{n}]")
        last, n = f"v{n}", n + 1

    if script.credit and meta and meta.get("pause"):
        # Credit to the follower who asked for the topic: comes in at the start of the pause before the final question and stays until the
        # end, above the caption. Voice format only, which has the pause.
        png = graphics.caption(f"Idea by {script.credit}", [script.credit.upper()], work / f"{scene.id}_credit.png",
                               brand.CREDIT_SIZE, brand.TEXT_CAPTION_MAX_W)
        start = meta["pause_at"]
        inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{seconds - start:.3f}", "-i", str(png)]
        filters.append(f"[{n}:v]format=rgba,fade=t=in:st=0:d={brand.TEXT_FADE * 2}:alpha=1,"
                       f"setpts=PTS-STARTPTS+{start}/TB[c{n}]")
        filters.append(f"[{last}][c{n}]overlay=x=(W-w)/2:y={brand.CREDIT_CENTER_Y}-h/2:eof_action=pass[v{n}]")
        last, n = f"v{n}", n + 1

    if script.final_fact and meta and meta.get("pause"):
        # 1-line end card (the real fact written out): comes in at the start of the pause before the
        # final question and stays until the end, in the gap between the HUD and the side panel.
        png = graphics.final_fact_card(script.final_fact, work / f"{scene.id}_final_fact.png")
        start = meta["pause_at"]
        inputs += ["-loop", "1", "-framerate", str(brand.FPS), "-t", f"{seconds - start:.3f}", "-i", str(png)]
        filters.append(f"[{n}:v]format=rgba,fade=t=in:st=0:d={brand.TEXT_FADE * 2}:alpha=1,"
                       f"setpts=PTS-STARTPTS+{start}/TB[c{n}]")
        filters.append(f"[{last}][c{n}]overlay=x=(W-w)/2:y={brand.FINAL_FACT_CENTER_Y}-h/2:eof_action=pass[v{n}]")
        last, n = f"v{n}", n + 1

    if hud_label:
        filters.append(f"[{last}][{hud_label}]overlay={brand.HUD_XY[0]}:{brand.HUD_XY[1]}:eof_action=repeat[vhud]")
        last = "vhud"                              # own label: n is also the index of the inputs (the handle comes later)

    inputs += ["-i", str(handle_png)]
    # The PNG layers arrive tagged as sRGB; the video comes out declared as bt709 (HD video standard).
    hx, hy = brand.HANDLE_XY if script.panel else brand.HANDLE_XY_SERIES
    filters.append(f"[{last}][{n}:v]overlay={hx}:{hy},"
                   "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[out]")

    seg = work / f"{scene.id}.mp4"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
         "-t", str(seconds), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", *COLOR_TAGS, "-r", str(brand.FPS), str(seg)])
    return seg, clip is not None


def _speech_end(audio: Path) -> float:
    """Last instant with sound above SPEECH_FLOOR_DB (alignment stretches the last word to the end)."""
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(audio), "-af",
                          f"silencedetect=n={SPEECH_FLOOR_DB}dB:d=0.05", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", out)]
    total = duration(audio)
    # Final silence: without "silence_end" after the last start, or an end glued to the end of the file.
    trailing = starts and (len(ends) < len(starts) or ends[-1] >= total - 0.05)
    return starts[-1] if trailing else total


def _scene_audio(meta, seconds: float, work: Path, scene_id: str) -> Path:
    seg = work / f"{scene_id}.wav"
    if meta and meta.get("audio") and meta.get("pause"):
        # Silence before the final question: speech up to the cut + silence + rest of the speech.
        # Without music underneath, the breath of the last "t" (ElevenLabs) becomes a hiss: short fade at the end of the speech.
        cut, pause = meta["pause_at"], meta["pause"]
        fade_start = max(cut, _speech_end(Path(meta["audio"])) - CLOSING_FADE) + pause
        run(["ffmpeg", "-y", "-i", meta["audio"], "-f", "lavfi", "-t", str(pause),
             "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex",
             f"[0:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[x][y];"
             f"[x]atrim=end={cut},asetpts=PTS-STARTPTS[a];[y]atrim=start={cut},asetpts=PTS-STARTPTS[b];"
             f"[a][1:a][b]concat=n=3:v=0:a=1,afade=t=out:st={fade_start:.3f}:d={CLOSING_FADE},apad[out]",
             "-map", "[out]", "-t", str(seconds), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(seg)])
    elif meta and meta.get("audio"):
        run(["ffmpeg", "-y", "-i", meta["audio"], "-af", "apad", "-t", str(seconds),
             "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(seg)])
    else:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(seconds),
             "-c:a", "pcm_s16le", str(seg)])
    return seg


def _concat(paths: list[Path], list_file: Path, out: Path) -> None:
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in paths))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)])


def music_filter(total: float, fade_end: float | None = None) -> str:
    """Looping track with fade, lowered by the narration (sidechain), added to the voice.

    fade_end: when the music should finish fading out (start of the final question); default = end of the video.
    """
    fade_out_start = max(0.0, (fade_end if fade_end is not None else total) - MUSIC_FADE_OUT)
    return (
        f"[2:a]volume={MUSIC_VOLUME},afade=t=in:d={MUSIC_FADE_IN},"
        f"afade=t=out:st={fade_out_start:.3f}:d={MUSIC_FADE_OUT}[m];"
        "[1:a]asplit=2[voice][key];"
        f"[m][key]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:"
        f"attack={DUCK_ATTACK_MS}:release={DUCK_RELEASE_MS}[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0[a]"
    )


def _mix_effects(narration: Path, effects: Path, out: Path) -> Path:
    """Effects under the voice: they lower when the narration speaks (in text format the voice is silence)."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(narration), "-i", str(effects), "-filter_complex",
         "[0:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[voice][key];"
         "[1:a]aresample=44100,aformat=channel_layouts=stereo[fx];"
         f"[fx][key]sidechaincompress=threshold={EFFECTS_DUCK_THRESHOLD}:ratio={EFFECTS_DUCK_RATIO}:"
         f"attack={DUCK_ATTACK_MS}:release={DUCK_RELEASE_MS}[ducked];"
         "[voice][ducked]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "[a]", "-c:a", "pcm_s16le", str(out)])
    return out


def mix_music(video: Path, narration: Path, music: Path, total: float, out: Path,
              start: float = 0.0, fade_end: float | None = None) -> None:
    run(["ffmpeg", "-y", "-i", str(video), "-i", str(narration),
         "-stream_loop", "-1", "-ss", f"{start:.3f}", "-i", str(music),
         "-filter_complex", music_filter(total, fade_end),
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", str(out)])


def _master(final: Path, target: float) -> None:
    """Normalizes the volume of the final mp4 in two passes (linear loudnorm: one gain only, no pumping) and
    limits the true peak. The image is copied without re-encoding."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final), "-af",
                          f"loudnorm=I={target}:TP={MASTER_TRUE_PEAK}:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    m = json.loads(out[out.rindex("{"):out.rindex("}") + 1])
    if m["input_i"] in ("-inf", "inf"):
        # --dummy narration without effects: all audio is silent, loudnorm has nothing to measure (it used to break 'all')
        print("  final volume: audio is silent (--dummy?), not normalizing")
        return
    tmp = final.with_suffix(".master.mp4")
    run(["ffmpeg", "-y", "-i", str(final), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af",
         f"loudnorm=I={target}:TP={MASTER_TRUE_PEAK}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
         "aresample=48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)])
    tmp.replace(final)
    print(f"  volume final: {float(m['input_i']):.1f} -> {target:.0f} LUFS")


def post_text(script: Script) -> str:
    # scene numbering stays that of the `claim` itself in the script `sources`: nothing is renumbered here
    sources = "\n".join(f"- {s.get('claim', '')}: {s.get('url') or '[SOURCE PENDING]'}" for s in script.sources)
    return (
        "PASTE INTO POST\n"
        f"TITLE\n{script.title}\n\n"
        f"DESCRIPTION\n{script.description}\n\n{' '.join(script.hashtags)}\n\n"
        "==============================\n"
        "INTERNAL (do not paste)\n"
        f"Sources (scenes as in the script `sources`):\n{sources}\n\n"
        "BEFORE PUBLISHING\n"
        "- [ ] Watched the whole thing and no scene looks off\n"
        "- [ ] All the sources above are filled in and checked\n"
        "- [ ] AI content label on (YouTube, TikTok and Instagram)\n"
    )


def render(script: Script, manifest: dict | None, music: Path | None = None, music_start: float = 0.0) -> Path:
    work = build_dir(script.slug) / "render"
    work.mkdir(exist_ok=True)
    handle_png = graphics.handle(work / "handle.png")
    manifest = manifest or {}

    videos, audios, missing, total = [], [], [], 0.0
    closing_at = None  # second of the video where the final question starts
    # Which scenes show the panel (for the fade when it disappears or returns in the neighboring scene).
    shows, stamp_before = [], None
    for scene in script.scenes:
        shows.append(_has_panel(scene, manifest.get(scene.id), stamp_before))
        stamp_before = scene.stamp or stamp_before

    last_stamp = None  # last stamp shown: origin of the number roll at the next jump
    now_since = 0.0    # second of the video where the current "NOW" stamp began (the clock continues across scenes)
    starts = {}        # scene -> (start in s, duration in s), for the sound effects
    for i, scene in enumerate(script.scenes):
        meta = manifest.get(scene.id)
        seconds = scene_duration(scene, meta)
        starts[scene.id] = (total, seconds)
        if meta and meta.get("closing_at") is not None:
            closing_at = total + meta["closing_at"]
        fade_in = i > 0 and not shows[i - 1]
        fade_out = i + 1 < len(shows) and not shows[i + 1]
        if scene.stamp != last_stamp:
            now_since = total
        v, has_clip = _scene_video(script, scene, meta, seconds, work, handle_png, last_stamp, fade_in, fade_out,
                                   clock_start=total - now_since, video_t=total)
        last_stamp = scene.stamp or last_stamp
        videos.append(v)
        audios.append(_scene_audio(meta, seconds, work, scene.id))
        if not has_clip:
            missing.append(scene.id)
        total += seconds
        print(f"  scene {scene.id}: {seconds:.1f} s{'' if has_clip else ' (placeholder card)'}")

    video = work / "video.mp4"
    narration = work / "narration.wav"
    _concat(videos, work / "videos.txt", video)
    _concat(audios, work / "audios.txt", narration)
    effects = sfx.build(script, starts, total, build_dir(script.slug) / "sfx", manifest)
    if effects:
        narration = _mix_effects(narration, effects, work / "voice_sfx.wav")

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    final = out_dir / f"{script.slug}.mp4"

    if music:
        mix_music(video, narration, music, total, final, start=music_start, fade_end=closing_at)
    else:
        run(["ffmpeg", "-y", "-i", str(video), "-i", str(narration), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(final)])

    if script.master_lufs is not None:
        _master(final, script.master_lufs)
    (out_dir / f"{script.slug}.post.txt").write_text(post_text(script), encoding="utf-8")
    cover_path = cover.make(script, handle_png)   # cover = frame 0 without the panel
    print(f"Capa: {cover_path}")
    print(f"\nPronto: {final} ({total:.1f} s)")
    if total <= MIN_TIKTOK_SECONDS:
        print(f"Warning: {total:.1f} s. TikTok only pays for videos over 1 minute; "
              "lengthen the narration or the 'min_seconds' of some scene.")
    if missing:
        print(f"Scenes still with a placeholder card: {', '.join(missing)}")
    return final
