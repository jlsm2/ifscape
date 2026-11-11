"""Narration: ElevenLabs (with the time of each word) or a test mode without the API."""

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .script import Script
from .timing import TARGET_SECONDS, budget_line, estimate_total
from .util import build_dir, duration, run

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128"
DUMMY_SECONDS_PER_WORD = 0.42
# models that do not read direction tags: they would be spoken aloud (v3 and v4 understand them; tested on v4)
TAGLESS_MODELS = {"eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_flash_v2"}
# Question that closes every video; it gets a silence before it, and the music finishes its fade there.
CLOSING_LINE = "What should I imagine next?"
CLOSING_PAUSE = 2.0          # 1 s was too little to mark the end


def _fingerprint(text: str, voice_id: str, model: str, direction: str = "", stability: float | None = None) -> str:
    # without own direction or stability the fingerprint is the usual one: the cache of old videos stays valid
    key = f"{voice_id}|{model}|{text}"
    if direction:
        key += f"|{direction}"
    if stability is not None:
        key += f"|stab={stability}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _words_from_alignment(alignment: dict) -> list[dict]:
    """Words with time from the per-character alignment; what is between [brackets] (direction tag) is left out."""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    words, current, w_start, w_end, depth = [], "", None, None, 0
    for ch, s, e in zip(chars, starts, ends):
        if ch == "[":
            depth += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if ch.isspace():
            if current:
                words.append({"word": current, "start": w_start, "end": w_end})
            current, w_start = "", None
            continue
        if w_start is None:
            w_start = s
        current += ch
        w_end = e
    if current:
        words.append({"word": current, "start": w_start, "end": w_end})
    return words


def _elevenlabs(text: str, voice_id: str, model: str, api_key: str, direction: str = "",
                stability: float = 0.5) -> tuple[bytes, list[dict]]:
    body = json.dumps({
        "text": f"{direction} {text}" if direction else text,
        "model_id": model,
        "voice_settings": {"stability": stability, "similarity_boost": 0.75},
    }).encode()
    req = urllib.request.Request(
        API.format(voice_id=voice_id), data=body, method="POST",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"ElevenLabs respondeu {err.code}: {err.read().decode(errors='ignore')[:300]}")
    return base64.b64decode(data["audio_base64"]), _words_from_alignment(data["alignment"])


def _dummy(text: str, out: Path) -> list[dict]:
    """Silent audio with words spread evenly: useful for testing the assembly."""
    tokens = text.split()
    total = len(tokens) * DUMMY_SECONDS_PER_WORD + 0.3
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{total:.3f}", str(out)])
    return [{"word": w, "start": i * DUMMY_SECONDS_PER_WORD, "end": (i + 1) * DUMMY_SECONDS_PER_WORD}
            for i, w in enumerate(tokens)]


def _rebase(meta: dict, voice_dir: Path) -> dict:
    """The meta stores the absolute path of the audio; if the repository was moved, the file with the same name next to
    the meta is the same audio (before, moving the folder regenerated every line and spent credit)."""
    audio = meta.get("audio")
    if audio and not Path(audio).exists() and (voice_dir / Path(audio).name).exists():
        return {**meta, "audio": str(voice_dir / Path(audio).name)}
    return meta


def _cached(meta_path: Path, fp: str) -> dict | None:
    if not meta_path.exists():
        return None
    meta = _rebase(json.loads(meta_path.read_text()), meta_path.parent)
    return meta if meta.get("fingerprint") == fp and Path(meta["audio"]).exists() else None


def generate(script: Script, dummy: bool = False, force: bool = False, allow_long: bool = False) -> dict:
    """Generates the narration of each scene and writes build/<slug>/voice/<id>.{mp3|wav,json}.

    Before spending credit, it estimates the duration: if it exceeds the target (timing.TARGET_SECONDS), it stops, unless
    allow_long. Cut the text before the voice, not after (plants-extinct: 216 words became 89.8 s)."""
    out_dir = build_dir(script.slug) / "voice"
    out_dir.mkdir(exist_ok=True)

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
    model = script.voice_model or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not dummy and (not voice_id or not api_key):
        raise SystemExit("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env, or use --dummy to test.")
    stability = script.voice_stability

    seconds, words = estimate_total(script.scenes, model)
    print(f"  {budget_line(seconds, words, model)}")
    pending = [s.id for s in script.scenes if s.narration and (force or not _cached(
        out_dir / f"{s.id}.json",
        _fingerprint(s.narration, voice_id if not dummy else "dummy", model,
                     script.voice_direction if s.direction is None else s.direction, stability)))]
    # the estimate is off by up to ~7% on v2 (bacteria: 72.1 s estimated, 67.7 s actual); the guard only stops with 5% slack
    if pending and not dummy and not allow_long and seconds > TARGET_SECONDS[1] * 1.05:
        raise SystemExit(f"Script above the target of {TARGET_SECONDS[1]:.0f} s: cut the text before spending credit "
                         f"(scenes to generate: {', '.join(pending)}). To record anyway, use --allow-long.")

    manifest = {}
    for scene in script.scenes:
        meta_path = out_dir / f"{scene.id}.json"
        if not scene.narration:
            manifest[scene.id] = {"audio": None, "duration": 0.0, "words": []}
            continue

        # direction tag (v3/v4 only): the scene's takes precedence over the script's; "" in the scene turns it off
        direction = script.voice_direction if scene.direction is None else scene.direction
        if direction and model in TAGLESS_MODELS:
            raise SystemExit(f"Scene {scene.id}: model {model} does not understand direction tags and would read '{direction}' aloud. "
                             "Use voice_model eleven_v4 in the script or remove the direction.")

        mode = "dummy" if dummy else "elevenlabs"
        fp = _fingerprint(scene.narration, voice_id if not dummy else "dummy", model, direction, stability)
        meta = None if force else _cached(meta_path, fp)
        if meta:
            manifest[scene.id] = meta
            print(f"  scene {scene.id}: narration already exists, kept")
            continue

        if dummy:
            audio = out_dir / f"{scene.id}.wav"
            words = _dummy(scene.narration, audio)
        else:
            audio = out_dir / f"{scene.id}.mp3"
            data, words = _elevenlabs(scene.narration, voice_id, model, api_key, direction,
                                      0.5 if stability is None else stability)
            audio.write_bytes(data)

        meta = {"audio": str(audio), "duration": duration(audio), "words": words,
                "fingerprint": fp, "mode": mode}
        meta_path.write_text(json.dumps(meta, indent=2))
        manifest[scene.id] = meta
        billed = len(scene.narration) + (len(direction) + 1 if direction else 0)
        cost = "" if dummy else f", {billed} caracteres cobrados ({model})"
        print(f"  scene {scene.id}: {meta['duration']:.1f} s of narration ({mode}{cost})")

    (build_dir(script.slug) / "voice.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _norm(word: str) -> str:
    return word.strip(".,!?;:\"'").lower()


def with_closing_pause(meta: dict, line: str = CLOSING_LINE) -> dict:
    """Opens a silence before the final question, without regenerating the narration.

    Returns a new meta: words of the question shifted, longer duration, "pause_at"/"pause"
    for the render to insert the silence in the audio and "closing_at" (start of the question in the scene).
    """
    words = meta.get("words") or []
    target = [_norm(w) for w in line.split()]
    norms = [_norm(w["word"]) for w in words]
    n = len(target)
    starts = [i for i in range(1, len(words) - n + 1) if norms[i:i + n] == target]
    if not starts:
        return meta
    i = starts[-1]
    cut = (words[i - 1]["end"] + words[i]["start"]) / 2
    shifted = [w if k < i else {**w, "start": w["start"] + CLOSING_PAUSE, "end": w["end"] + CLOSING_PAUSE}
               for k, w in enumerate(words)]
    return {**meta, "words": shifted, "duration": meta["duration"] + CLOSING_PAUSE,
            "pause_at": round(cut, 3), "pause": CLOSING_PAUSE,
            "closing_at": round(words[i]["start"] + CLOSING_PAUSE, 3)}


def with_closing_take(meta: dict, sid: str, voice_dir: Path, line: str = CLOSING_LINE) -> dict:
    """Replaces the final question with a separate recording, if voice/<id>_closing.mp3 exists (+ .json with the
    alignment from ElevenLabs). Lets you add emotion to the question alone without regenerating the scene (the question
    sounded neutral). The spliced audio stays in voice/<id>_spliced.wav."""
    take, align = voice_dir / f"{sid}_closing.mp3", voice_dir / f"{sid}_closing.json"
    words = meta.get("words") or []
    target = [_norm(w) for w in line.split()]
    norms = [_norm(w["word"]) for w in words]
    hits = [i for i in range(1, len(words) - len(target) + 1) if norms[i:i + len(target)] == target]
    if not (take.exists() and align.exists() and meta.get("audio") and hits):
        return meta
    i = hits[-1]
    cut = (words[i - 1]["end"] + words[i]["start"]) / 2
    spliced = voice_dir / f"{sid}_spliced.wav"
    # redoes the splice if the take OR the scene's line is newer (a re-recorded scene left the old splice)
    newest = max(take.stat().st_mtime, Path(meta["audio"]).stat().st_mtime)
    if not spliced.exists() or spliced.stat().st_mtime < newest:
        run(["ffmpeg", "-y", "-v", "error", "-i", meta["audio"], "-i", str(take), "-filter_complex",
             f"[0:a]atrim=0:{cut:.3f},aresample=44100,aformat=channel_layouts=stereo[a];"
             "[1:a]aresample=44100,aformat=channel_layouts=stereo[b];[a][b]concat=n=2:v=0:a=1[out]",
             "-map", "[out]", "-c:a", "pcm_s16le", str(spliced)])
    new_words = _words_from_alignment(json.loads(align.read_text())["alignment"])
    shifted = [{**w, "start": w["start"] + cut, "end": w["end"] + cut} for w in new_words]
    return {**meta, "audio": str(spliced), "duration": duration(spliced), "words": words[:i] + shifted}


def load_manifest(script: Script) -> dict | None:
    path = build_dir(script.slug) / "voice.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    voice_dir = build_dir(script.slug) / "voice"
    line = script.closing or CLOSING_LINE
    manifest = {sid: with_closing_pause(with_closing_take(_rebase(meta, voice_dir), sid, voice_dir, line), line)
                for sid, meta in raw.items()}
    if any(m.get("words") for m in manifest.values()) and not any(m.get("pause") for m in manifest.values()):
        # the 2 s pause vanishes into silence if the final sentence does not match the narration word for word
        print(f"  Warning: the final sentence '{line}' was not found in the narration (it must come after another line "
              "in the same scene); the video comes out WITHOUT the 2 s pause.")
    return manifest
