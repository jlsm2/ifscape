"""Checks a generated sound effect BEFORE registering it in sfx/library.json (lesson: an
ElevenLabs effect came out silent and was only discovered afterwards).

Usage: py tools/qa/sfx_check.py <file.wav|mp3> [...]
Prints duration, RMS, peak and % of silence (< -50 dBFS per 50 ms window).
Exits with error 1 if any file is silent (RMS < -60 dBFS) or almost silent (> 90% silence).
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np

SILENCE_DB = -50.0
MUTE_RMS_DB = -60.0
RATE = 22050


def decode(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, dtype=np.float32)


def db(x: float) -> float:
    return 20 * np.log10(max(float(x), 1e-9))


def check(path: str) -> bool:
    x = decode(path)
    if x.size == 0:
        print(f"{path}: ERROR could not decode")
        return False
    rms, peak = db(np.sqrt(np.mean(x ** 2))), db(np.max(np.abs(x)))
    win = RATE // 20
    frames = x[: x.size // win * win].reshape(-1, win) if x.size >= win else x.reshape(1, -1)
    levels = 20 * np.log10(np.maximum(np.sqrt(np.mean(frames ** 2, axis=1)), 1e-9))
    silent = float(np.mean(levels < SILENCE_DB)) * 100
    verdict = "OK"
    ok = True
    if rms < MUTE_RMS_DB:
        verdict, ok = "ERROR silent", False
    elif silent > 90:
        verdict, ok = "ERROR almost silent", False
    elif silent > 50:
        verdict = "WARNING too much silence"
    print(f"{path}: {x.size / RATE:.2f} s | RMS {rms:.1f} dBFS | peak {peak:.1f} dBFS | silence {silent:.0f}% | {verdict}")
    return ok


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    results = [check(p) for p in sys.argv[1:]]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
