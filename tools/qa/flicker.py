"""Hunts flicker in an animation: brightness that blinks and objects that pop outside the cuts.

Usage: py tools/qa/flicker.py <video.mp4> [--timeline build/<slug>/blender/timeline.json] [--out folder] [--top 12]

Measures, frame by frame, on a small grayscale copy (180x320):
- mean brightness of the whole screen and of each region of a 4x6 grid (light blinking on part of the screen);
- mean difference between neighboring frames (an object or shadow that appears and disappears, overlapping faces fighting).
Ignores 2 frames around each scene cut (the cut is intentional). Writes a report and, for the worst
cases, the frames t-1, t, t+1 at review size (432x768) in the output folder.
"""

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

W, H = 180, 320
COLS, ROWS = 4, 6
CUT_GUARD = 2


def read_frames(video: Path):
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = W * H
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        yield buf
    proc.wait()


def tile_means(buf: bytes) -> list[float]:
    tw, th = W // COLS, H // ROWS
    out = []
    for r in range(ROWS):
        for c in range(COLS):
            total = 0
            for y in range(r * th, (r + 1) * th):
                start = y * W + c * tw
                total += sum(buf[start:start + tw])
            out.append(total / (tw * th))
    return out


def mean_abs_diff(a: bytes, b: bytes) -> float:
    # samples 1 of every 3 pixels: fast enough and still catches objects of a few pixels in the small copy
    return sum(abs(x - y) for x, y in zip(a[::3], b[::3])) / (len(a) // 3)


def cuts_from_timeline(path: Path | None, fps: float) -> tuple[set[int], dict]:
    if not path or not path.exists():
        return set(), {}
    tl = json.loads(path.read_text(encoding="utf-8"))
    starts = {s["start"]: s["id"] for s in tl["scenes"]}
    return set(starts), {s["id"]: (s["start"], s["end"]) for s in tl["scenes"]}


def scene_of(frame: int, spans: dict) -> str:
    for sid, (a, b) in spans.items():
        if a <= frame < b:
            return sid
    return "?"


def near_cut(frame: int, cuts: set[int]) -> bool:
    return any(abs(frame - c) <= CUT_GUARD for c in cuts)


def analyze(video: Path, timeline: Path | None):
    fps = 30.0
    cuts, spans = cuts_from_timeline(timeline, fps)
    luma, tiles, diffs = [], [], [0.0]
    prev = None
    for buf in read_frames(video):
        luma.append(sum(buf) / len(buf))
        tiles.append(tile_means(buf))
        if prev is not None:
            diffs.append(mean_abs_diff(prev, buf))
        prev = buf
    if not luma:
        raise SystemExit("No frame read (did ffmpeg fail?).")
    if not cuts:                                    # without a timeline: cuts = huge jumps in difference
        med = statistics.median(diffs[1:]) if len(diffs) > 1 else 0
        cuts = {i for i, d in enumerate(diffs) if d > max(12.0, 8 * med)}
    findings = []
    n = len(luma)
    for t in range(1, n - 1):
        if near_cut(t, cuts):
            continue
        # blinking light: the frame departs from both neighbors to the same side (up and down)
        g = luma[t] - (luma[t - 1] + luma[t + 1]) / 2
        if abs(g) > 1.0 and (luma[t] - luma[t - 1]) * (luma[t + 1] - luma[t]) < 0:
            findings.append((abs(g) * 2, t, "light flashing (whole screen)", f"brightness {luma[t-1]:.1f} → {luma[t]:.1f} → {luma[t+1]:.1f}"))
        for k in range(COLS * ROWS):
            a, b, c = tiles[t - 1][k], tiles[t][k], tiles[t + 1][k]
            spike = b - (a + c) / 2
            if abs(spike) > 6.0 and (b - a) * (c - b) < 0:
                where = f"region row {k // COLS + 1}/{ROWS}, column {k % COLS + 1}/{COLS}"
                findings.append((abs(spike), t, "local blink (light, shadow or fighting faces)",
                                 f"{where}: {a:.1f} → {b:.1f} → {c:.1f}"))
        # pop: difference from the previous frame well above the normal motion around it
        window = [diffs[i] for i in range(max(1, t - 15), min(n, t + 16)) if i != t and not near_cut(i, cuts)]
        if len(window) >= 8:
            base = statistics.median(window)
            if diffs[t] > 3 * base + 1.5:
                findings.append(((diffs[t] - base) * 1.5, t, "pop (something appears/disappears or jumps)",
                                 f"difference {diffs[t]:.2f} against {base:.2f} around"))
    findings.sort(reverse=True)
    return findings, luma, diffs, spans, cuts


PW, PH = 54, 96       # fine grid: each cell ≈ 20x20 px of the 1080x1920 frame (a building window)
TREMOR_WIN = 9        # window of frames in which to count the reversals
TREMOR_AMP = 2.0      # minimum variation (gray levels) of each step to count
TREMOR_FLIPS = 4      # up-down-up-down: 4 reversals in the window = trembling light, not a moving camera


def read_cells(video: Path):
    """Means of 20x20 px cells straight from ffmpeg (area scaling = mean of each cell)."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={PW}:{PH}:flags=area,format=gray",
           "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while True:
        buf = proc.stdout.read(PW * PH)
        if len(buf) < PW * PH:
            break
        yield buf
    proc.wait()


def tremor(video: Path, cuts: set[int]) -> list[tuple]:
    """Trembling local light (shadow or Eevee lighting varying between frames, blinking window): the mean of a small
    cell goes up and down several times in a row. The mean screen brightness and the 4x6 grid do not catch it (the
    report said 0 suspects on the facades while the house lights were visibly blinking)."""
    import numpy as np                              # already in the environment; pure Python would take minutes here
    v = np.frombuffer(b"".join(read_cells(video)), dtype=np.uint8).reshape(-1, PW * PH).astype(np.int16)
    d = np.diff(v, axis=0)                          # d[t-1] = frame t minus t-1
    big = np.abs(d) >= TREMOR_AMP
    # flip[i]: reversal between steps i and i+1 RETURNING to the same brightness (A-B-A). A camera moving over texture also
    # reverses the sign, but does not return to the earlier value; blinking light does.
    back = np.abs(v[2:] - v[:-2]) < 0.5 * np.minimum(np.abs(d[:-1]), np.abs(d[1:]))
    flip = (d[:-1] * d[1:] < 0) & big[:-1] & big[1:] & back
    csum = np.vstack([np.zeros((1, flip.shape[1]), np.int32), np.cumsum(flip, axis=0, dtype=np.int32)])
    hits = {}
    for t in range(TREMOR_WIN, v.shape[0]):
        if any(t - TREMOR_WIN - CUT_GUARD <= c <= t + CUT_GUARD for c in cuts):
            continue
        # reversals between the steps inside the window [t-WIN, t]
        flips = csum[t - 1] - csum[t - TREMOR_WIN]
        ks = np.nonzero(flips >= TREMOR_FLIPS)[0]
        if ks.size:
            amp = np.abs(d[t - TREMOR_WIN:t, ks]).mean(axis=0)
            hits.setdefault(t // 15, []).extend((int(k), int(flips[k]), float(a), t) for k, a in zip(ks, amp))
    out = []
    for block, cells_hit in hits.items():
        xs = [k % PW for k, *_ in cells_hit]
        ys = [k // PW for k, *_ in cells_hit]
        t = max(cells_hit, key=lambda h: h[2])[3]
        amp = max(h[2] for h in cells_hit)
        box = f"x {min(xs) * 20}–{max(xs) * 20 + 20}, y {min(ys) * 20}–{max(ys) * 20 + 20} px"
        out.append((len(cells_hit) * amp, t, len(cells_hit), amp, box))
    out.sort(reverse=True)
    return out


def dump_frames(video: Path, frames: list[int], out: Path):
    out.mkdir(parents=True, exist_ok=True)
    for t in frames:
        for k in (t - 1, t, t + 1):
            dst = out / f"f{k:05d}.png"
            if dst.exists():
                continue
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                            f"select=eq(n\\,{k}),scale=432:768", "-frames:v", "1", str(dst)], check=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")       # the Windows console (cp1252) does not print "→"
    findings, luma, diffs, spans, cuts = analyze(args.video, args.timeline)
    unique = []
    for _, t, _, _ in findings:
        if not any(abs(t - s) <= 2 for s in unique):
            unique.append(t)
    lines = [f"# Flicker in {args.video.name}", "",
             f"{len(luma)} frames; {len(cuts)} cuts ignored (±{CUT_GUARD} frames); "
             f"{len(unique)} suspect moments ({len(findings)} measures).", ""]
    if spans:
        lines.append("Mean brightness per scene (a big jump inside the scene = light changing without a cut):")
        for sid, (a, b) in spans.items():
            seg = luma[a:b]
            if seg:
                lines.append(f"- scene {sid}: {min(seg):.1f} to {max(seg):.1f} (mean {statistics.mean(seg):.1f})")
        lines.append("")
    lines.append("| # | Frame | Time | Scene | Type | Measure |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    seen = []
    for score, t, kind, detail in findings:
        if any(abs(t - s) <= 2 for s in seen):
            continue
        seen.append(t)
        lines.append(f"| {len(seen)} | {t} | {t / 30:.2f} s | {scene_of(t, spans)} | {kind} | {detail} |")
        if len(seen) >= args.top * 3:
            break
    shakes = tremor(args.video, cuts)
    lines += ["", "## Trembling local light (20x20 px cells that go up and down several times in a row)", ""]
    if not shakes:
        lines.append("None.")
    else:
        lines.append(f"{len(shakes)} 0.5 s stretches with tremor. The worst:")
        lines += ["", "| Frame | Time | Scene | Cells | Max variation | Where (on the 1080x1920 frame) |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for _, t, n, amp, box in shakes[:args.top]:
            lines.append(f"| {t} | {t / 30:.2f} s | {scene_of(t, spans)} | {n} | {amp:.1f} | {box} |")
    report = "\n".join(lines)
    print(report)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "flicker.md").write_text(report, encoding="utf-8")
        dump_frames(args.video, seen[:args.top], args.out / "frames")
        print(f"\nFrames t-1, t, t+1 of the {min(args.top, len(seen))} worst in {args.out / 'frames'}")


if __name__ == "__main__":
    sys.exit(main())
