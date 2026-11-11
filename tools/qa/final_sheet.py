"""Final sheet of the finished video: frames at fixed times with the time written, plus the audio peaks per second.

Usage: py tools/qa/final_sheet.py out/<slug>.mp4 [--times 0.3,2.5,5,...] [--out-dir build/<slug>/final]
Writes <out-dir>/final_sheet.jpg (default build/<slug>/final/) and prints the seconds with peak > -3 dBFS and the
silences > 2 s (ffmpeg astats / silencedetect). Look at the sheet before delivering: opening, event, cards and end.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMES = [0.3, 2.5, 5, 9, 14, 20, 27, 35, 45, 53, 58, 62, 64, 65.8]
THUMB_W = 270
COLS = 7


def ffprobe_duration(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    return float(out)


def grab(video: Path, t: float) -> Image.Image | None:
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL)
    if not p.stdout:
        return None
    import io
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def audio_report(video: Path) -> None:
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-vn", "-af",
                          "asetnsamples=n=48000:p=0,astats=metadata=1:reset=1,"
                          "ametadata=print:key=lavfi.astats.Overall.Peak_level:file=-,"
                          "silencedetect=n=-50dB:d=2", "-f", "null", "-"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL)
    peaks = [(float(m.group(1)), float(m.group(2))) for m in
             re.finditer(r"pts_time:([\d.]+)\s*\nlavfi\.astats\.Overall\.Peak_level=(-?[\d.inf]+)", out.stdout.replace("\r", ""))
             if m.group(2) not in ("-inf", "inf")]
    print("\nAudio peaks per second (dBFS):")
    if not peaks:
        print("  (could not read the peaks)")
    else:
        hot = [(t, p) for t, p in peaks if p > -3.0]
        print(f"  maximum {max(p for _, p in peaks):.1f} dBFS in {len(peaks)} s measured; seconds with peak > -3 dBFS: "
              + (", ".join(f"{t:.0f}s ({p:.1f})" for t, p in hot) if hot else "nenhum"))
    sil = re.findall(r"silence_start: ([\d.]+)|silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", out.stderr)
    starts = [float(a) for a, _, _ in sil if a]
    ends = [(float(b), float(c)) for _, b, c in sil if b]
    print("Silences > 2 s: " + ("; ".join(f"{e - d:.1f}-{e:.1f}s ({d:.1f} s)" for e, d in ends) if ends else "none"))
    if len(starts) > len(ends):
        print(f"  silence open from {starts[-1]:.1f} s to the end")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--times", help="times in seconds, comma-separated")
    ap.add_argument("--out-dir", help="output folder (default build/<slug>/final)")
    a = ap.parse_args()
    video = Path(a.video)
    if not video.exists():
        print(f"Could not find {video}")
        return 2
    dur = ffprobe_duration(video)
    times = [float(x) for x in a.times.split(",")] if a.times else DEFAULT_TIMES
    times = [min(t, max(dur - 0.1, 0)) for t in times]
    slug = video.name.split(".")[0]
    out_dir = Path(a.out_dir) if a.out_dir else ROOT / "build" / slug / "final"
    out_dir.mkdir(parents=True, exist_ok=True)

    font_path = ROOT / "fonts" / "Barlow-SemiBold.ttf"
    font = ImageFont.truetype(str(font_path), 22) if font_path.exists() else ImageFont.load_default()
    frames = []
    for t in times:
        im = grab(video, t)
        if im is None:
            continue
        im = im.resize((THUMB_W, int(im.height * THUMB_W / im.width)))
        d = ImageDraw.Draw(im)
        label = f"{t:.1f} s"
        w = d.textlength(label, font=font)
        d.rectangle([0, 0, w + 14, 30], fill=(0, 0, 0))
        d.text((7, 2), label, fill=(245, 165, 36), font=font)
        frames.append(im)
    if not frames:
        print("No frame extracted.")
        return 1
    rows = (len(frames) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * (THUMB_W + 6) + 6, rows * (frames[0].height + 6) + 6), (20, 20, 24))
    for i, im in enumerate(frames):
        sheet.paste(im, (6 + (i % COLS) * (THUMB_W + 6), 6 + (i // COLS) * (frames[0].height + 6)))
    target = out_dir / "final_sheet.jpg"
    sheet.save(target, quality=88)
    print(f"{len(frames)} frames ({dur:.1f} s of video) -> {target}")
    audio_report(video)
    return 0


if __name__ == "__main__":
    sys.exit(main())
