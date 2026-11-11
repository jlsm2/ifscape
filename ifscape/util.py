"""Small utilities: .env, ffmpeg and paths."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Reads KEY=value from .env without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"'{tool}' not found. Install FFmpeg and try again.")


def run(cmd: list[str]) -> None:
    # stdin closed: running in the background, FFmpeg sometimes hung waiting for a key on stdin
    # (the effects mix hung twice).
    proc = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"Comando falhou: {' '.join(cmd[:6])} ...\n{tail}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def build_dir(slug: str) -> Path:
    d = ROOT / "build" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def clips_dir(slug: str) -> Path:
    return ROOT / "clips" / slug


def refs_dir(slug: str) -> Path:
    """First-frame images (Nano Banana) that the owner approves before animating."""
    return ROOT / "refs" / slug
