"""Hunts SHADOW and light jitter (states that alternate A-B-A between frames) and Eevee shadow buffer overflow.

Two modes, diagnostic only:

1) Video (measures what flicker.py misses):
     py tools/qa/jitter.py <video.mp4> [--timeline build/<slug>/blender/timeline.json] [--out report.md]
   Reads the video at 270x480 (gray, area scaling) and, for each pixel, looks for the pattern "goes up and returns to the same value"
   (frame t outside both neighbors, which are equal to each other): this is what a shadow that disappears and returns, tile light or shadow map page
   does with the camera STILL or moving. A camera moving over texture also reverses the sign, but does not
   return to the earlier value, so it does not count. Per frame, it records the fraction of the screen with A-B-A (flip%) and summarizes per
   second and per scene. A "bad" frame = flip% above FLIP_BAD. See also the "alternation" column: how many bad frames
   in a row/alternating there are in the 1 s window (visible tremor = many).

2) Blender scene (the most common cause in Eevee Next; runs Blender in the background):
     py tools/qa/jitter.py --blend build/<slug>/blender/scene.blend [--step 12] [--pool 512] [--blender path]
   Renders 1 of every STEP frames at full resolution with 32 samples (as the final render) and counts the messages
   "Shadow buffer full ... (N / 2048)". If it shows up, the virtual shadow map lost pages and the shadow blinks from
   frame to frame, even with everything still. Fix: scene.eevee.shadow_pool_size = "1024" (or "2048") in kit.reset_scene.
   Takes ~1 s per sampled frame.
"""

import argparse
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

W, H = 270, 480
AMP = 4.0            # minimum gray levels of each step (up and down)
RETURN = 0.35        # the value returns to within 35% of the step (a true A-B-A)
FLIP_BAD = 0.0015    # fraction of the screen with A-B-A above which the frame counts as "bad" (~0.15%)
CUT_GUARD = 2


def read_video(video: Path):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)


def flip_fraction(a):
    """flip[t] = fraction of pixels where frame t departed from t-1 and t+1 (which are similar) by >= AMP (in blocks, for memory)."""
    import numpy as np
    n = a.shape[0]
    frac = np.zeros(n, dtype=np.float32)
    for s in range(1, n - 1, 200):
        e = min(n - 1, s + 200)
        p, c, q = a[s - 1:e - 1], a[s:e], a[s + 1:e + 1]
        d1, d2 = c - p, q - c
        back = np.abs(q - p) <= RETURN * np.minimum(np.abs(d1), np.abs(d2))
        hit = (d1 * d2 < 0) & (np.abs(d1) >= AMP) & (np.abs(d2) >= AMP) & back
        frac[s:e] = hit.mean(axis=(1, 2))
    return frac


def cuts_from(timeline: Path | None):
    if not timeline or not timeline.exists():
        return set(), {}
    import json
    tl = json.loads(timeline.read_text(encoding="utf-8"))
    return {s["start"] for s in tl["scenes"]}, {s["id"]: (s["start"], s["end"]) for s in tl["scenes"]}


def video_mode(args):
    import numpy as np
    sys.stdout.reconfigure(encoding="utf-8")
    a = read_video(args.video)
    frac = flip_fraction(a)
    cuts, spans = cuts_from(args.timeline)
    for c in cuts:                                     # the cut is intentional
        frac[max(0, c - CUT_GUARD):c + CUT_GUARD + 1] = 0
    bad = frac > FLIP_BAD
    n = len(frac)
    lines = [f"# Jitter (A-B-A) in {args.video.name}", "",
             f"{n} frames; flip% = fraction of the screen (270x480) where the frame departs from both neighbors and they are equal. "
             f"Bad frame: flip% > {FLIP_BAD * 100:.2f}. Total bad frames: {int(bad.sum())} ({bad.mean() * 100:.0f}%).", "",
             "| Window | Bad frames of 30 | mean flip% | worst flip% | Verdict |", "| --- | --- | --- | --- | --- |"]
    verdict_any = False
    for s in range(0, n, 30):
        seg = frac[s:s + 30]
        nb = int(bad[s:s + 30].sum())
        v = "TREMOR" if nb >= 5 else ("suspect" if nb >= 2 else "ok")
        verdict_any |= v == "TREMOR"
        if v != "ok":
            lines.append(f"| {s / 30:.0f}-{(s + 30) / 30:.0f} s (q{s}) | {nb} | {seg.mean() * 100:.2f} | {seg.max() * 100:.2f} | {v} |")
    if spans:
        lines += ["", "By scene:", "", "| Scene | Bad frames | % of scene |", "| --- | --- | --- |"]
        for sid, (x, y) in spans.items():
            seg = bad[x:y]
            if len(seg):
                lines.append(f"| {sid} | {int(seg.sum())} | {seg.mean() * 100:.0f}% |")
    lines += ["", "Check on a pair of cropped frames before classifying: a fast camera over fine grass or light that "
              "blinks on purpose also count. If 'bad' is ~half the frames in a still-camera scene, it is "
              "the shadow buffer (--blend mode)."]
    out = "\n".join(lines)
    print(out)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    return 1 if verdict_any else 0


BLEND_SCRIPT = r'''
import bpy, os, sys
sc = bpy.context.scene
a = sys.argv[sys.argv.index("--") + 1:]
step, pool, f0, f1 = int(a[0]), a[1], int(a[2]), int(a[3])
sc.render.resolution_percentage = 100
sc.eevee.taa_render_samples = 32
if pool != "-":
    sc.eevee.shadow_pool_size = pool
sc.render.filepath = os.path.join(os.environ.get("TEMP", "."), "jitter_dummy.png")
f1 = min(f1, sc.frame_end)
for f in range(f0, f1 + 1, step):
    sc.frame_set(f)
    print("@@FRAME", f, flush=True)
    bpy.ops.render.render(write_still=True)
    sys.stdout.flush()
'''


def blend_mode(args):
    sys.stdout.reconfigure(encoding="utf-8")
    blender = args.blender or r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "jitter_scan.py"
        script.write_text(BLEND_SCRIPT, encoding="utf-8")
        cmd = [blender, "-b", str(args.blend), "-P", str(script), "--", str(args.step), args.pool or "-",
               str(args.first), str(args.last)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="ignore")
    cur, peak, seen = None, {}, []
    for line in proc.stdout.splitlines():
        m = re.search(r"@@FRAME (\d+)", line)
        if m:
            cur = int(m.group(1))
            seen.append(cur)
            peak[cur] = 0
            continue
        m = re.search(r"Shadow buffer full.*\((\d+) / (\d+)\)", line)
        if m and cur is not None:
            peak[cur] = max(peak[cur], int(m.group(1)))
    bad = [f for f in seen if peak[f]]
    print(f"{len(seen)} frames sampled (1 of every {args.step}); {len(bad)} with shadow buffer overflow.")
    runs = []
    for f in bad:
        if runs and f - runs[-1][1] <= 2 * args.step:
            runs[-1][1], runs[-1][2] = f, max(runs[-1][2], peak[f])
        else:
            runs.append([f, f, peak[f]])
    for x, y, p in runs:
        print(f"- frames {x}-{y} ({x / 30:.1f}-{y / 30:.1f} s): peak {p} pages (limit 2048 with pool 512)")
    if not bad:
        print("Shadow stable (on the buffer side).")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", type=Path)
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--blend", type=Path)
    ap.add_argument("--step", type=int, default=12)
    ap.add_argument("--pool", default=None, help="forces eevee.shadow_pool_size in the test (ex.: 1024)")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=100000)
    ap.add_argument("--blender")
    args = ap.parse_args(argv)
    if args.blend:
        return blend_mode(args)
    if not args.video:
        ap.error("provide the video or --blend scene.blend")
    return video_mode(args)


if __name__ == "__main__":
    sys.exit(main())
