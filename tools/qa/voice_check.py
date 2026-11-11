"""Checks the generated voice against the script: transcribes each scene with faster-whisper
(local, free) and points out swapped, swallowed or extra words.

    py tools/qa/voice_check.py scripts/<slug>.json [--scenes 04,07] [--model small]

Catches a misread number, an eaten or swapped word. It does not judge tone or emotion:
that stays by ear.
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


# Whisper writes the unit abbreviated even when the voice says the whole word
ABBREV = {"cm": "centimeters", "km": "kilometers", "m": "meters", "kg": "kilograms"}


def spell(n):
    """Whole number in words (up to millions), to compare '60' with 'sixty'."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    for size, name in ((10**6, "million"), (1000, "thousand"), (100, "hundred")):
        if n >= size:
            rest = n % size
            return spell(n // size) + " " + name + ("" if rest == 0 else " " + spell(rest))
    return str(n)


def norm(text):
    text = text.lower().replace("’", "'")
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    text = re.sub(r"\d+", lambda m: spell(int(m.group())), text)
    text = re.sub(r"[^a-z' ]+", " ", text.replace("-", " "))
    return [ABBREV.get(w, w) for w in text.split()]


def load_audio(path):
    """Decodes with FFmpeg (16 kHz mono) instead of faster-whisper's PyAV."""
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--scenes", help="comma-separated ids (default: all)")
    ap.add_argument("--model", default="small", help="tiny, base, small, medium (default small)")
    args = ap.parse_args()

    data = json.loads(Path(args.script).read_text(encoding="utf-8"))
    voice_dir = ROOT / "build" / data["slug"] / "voice"
    wanted = set(args.scenes.split(",")) if args.scenes else None

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    problems = 0
    for scene in data["scenes"]:
        sid, expected = scene["id"], scene.get("narration")
        if not expected or (wanted and sid not in wanted):
            continue
        meta = voice_dir / f"{sid}.json"   # the audio may have been trimmed (e.g. 03_cut.wav)
        audio = Path(json.loads(meta.read_text())["audio"]) if meta.exists() else voice_dir / f"{sid}.mp3"
        if not audio.exists():
            print(f"{sid}  NO AUDIO ({audio.name})")
            problems += 1
            continue
        segments, _ = model.transcribe(load_audio(audio), language="en", beam_size=5)
        heard = " ".join(s.text.strip() for s in segments)
        a, b = norm(expected), norm(heard)
        diffs = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            # "wet line" x "wetline": only Whisper's spelling, not the speech
            if op == "equal" or "".join(a[i1:i2]) == "".join(b[j1:j2]):
                continue
            diffs.append(f"{op}: script '{' '.join(a[i1:i2])}' → heard '{' '.join(b[j1:j2])}'")
        if diffs:
            problems += 1
            print(f"{sid}  DIFERENTE")
            print(f"     ouvido: {heard}")
            for d in diffs:
                print(f"     - {d}")
        else:
            print(f"{sid}  ok")
    print(f"\n{problems} scene(s) to listen to." if problems else "\nEverything matches the script.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
