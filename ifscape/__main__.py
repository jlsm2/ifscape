"""Ifscape command line.

  python -m ifscape voice   scripts/x.json [--dummy] [--force]
  python -m ifscape prompts scripts/x.json
  python -m ifscape flat2d  scripts/x.json [--stills 30,900] [--force]   # 2D set ('flat' field) -> clips/
  python -m ifscape upscale scripts/x.json [--force]   # upscales the clips 2x with AI before the render
  python -m ifscape blender scripts/x.json [--stills 30,300] [--frames 1-1640] [--force]   # continuous 3D set -> clips/
  python -m ifscape render  scripts/x.json [--music track.mp3 [--music-start 10]]
  python -m ifscape all     scripts/x.json [--dummy] [--music track.mp3]
  python -m ifscape cover   scripts/x.json   # cover = frame 0 without the panel (the render already writes it)
  python -m ifscape qa      scripts/x.json   # final gate on out/<slug>.mp4 (the render already runs it)
  python -m ifscape status  scripts/x.json   # video state read from disk, stage by stage
  python -m ifscape lint    scripts/x.json   # unsourced stamp, imperial unit, absolute word, numbers in the voice, post.txt
  python -m ifscape metrics scripts/x.json   # writes build/<slug>/metrics.json (rounds, hours, duration, render)
"""

import argparse
import os
from pathlib import Path

from . import blender, cover, flat2d, lint, metrics, prompts, qa, render, script, status, timing, upscale, voice
from .util import load_env, require_ffmpeg


def main() -> None:
    parser = argparse.ArgumentParser(prog="ifscape", description="Builds Ifscape videos from a JSON script.")
    parser.add_argument("command", choices=["voice", "prompts", "upscale", "blender", "flat2d", "render", "all", "cover", "qa", "status", "metrics", "lint"])
    parser.add_argument("--stills", help="blender/flat2d: only these frames, e.g. 30,300 (quick review)")
    parser.add_argument("--fresh", action="store_true", help="blender: redo all frames instead of resuming")
    parser.add_argument("--frames", help="blender: redo only this range, e.g. 1-1640, and reuse the rest of the previous render")
    parser.add_argument("script", type=Path, help="path to the .json script")
    parser.add_argument("--dummy", action="store_true", help="silent narration, without spending the API (for testing)")
    parser.add_argument("--force", action="store_true", help="regenerate the narration even if it already exists")
    parser.add_argument("--allow-long", action="store_true",
                        help="voice: write even with the script above the duration target (61 to 70 s)")
    parser.add_argument("--music", type=Path, help="background track (kept low under the narration)")
    parser.add_argument("--music-start", type=float, default=0.0,
                        help="second of the track where the video starts (skips a very quiet intro)")
    args = parser.parse_args()

    load_env()
    require_ffmpeg()
    sc = script.load(args.script)
    print(f"{sc.title} · {len(sc.scenes)} scenes")

    if args.command == "status":
        status.show(sc, args.script)
        return

    if args.command == "lint":
        raise SystemExit(lint.show(sc))

    if args.command == "metrics":
        print(f"\nMetrics: {metrics.write(sc, Path(args.script))}")
        return

    if args.command == "cover":
        out = cover.make(sc)
        print(f"\nCapa: {out}")
        return

    text_only = sc.format == "text"
    if args.command == "voice" and text_only:
        raise SystemExit("This script is text-only (format: text); there is no narration to generate.")
    if args.command in ("voice", "all") and not text_only:
        print("\nNarration")
        voice.generate(sc, dummy=args.dummy, force=args.force, allow_long=args.allow_long)

    manifest = {} if text_only else voice.load_manifest(sc)

    if args.command == "qa":
        result = qa.check(sc, manifest)
        raise SystemExit(0 if result["ok"] else 1)

    if args.command in ("prompts", "all"):
        if not text_only:
            model = sc.voice_model or os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
            print("  " + timing.budget_line(*timing.estimate_total(sc.scenes, model), model))
            for problem in status.claim_problems(sc):
                print(f"  fichas: {problem}")
        path = prompts.write(sc, manifest)
        print(f"\nPrompts for the video generator: {path}")
        batch = prompts.write_flow_batch(sc)
        if batch:
            print(f"Batch for the Flow agent (2 messages): {batch}")

    if args.command == "blender":
        print("\n3D set (Blender)")
        blender.render(sc, manifest, stills=args.stills, force=args.force, fresh=args.fresh, frames=args.frames)

    if args.command == "flat2d" or (args.command == "all" and flat2d.uses_flat(sc)):
        print("\n2D set (flat2d)")
        flat2d.render(sc, manifest, stills=args.stills, force=args.force)

    if args.command == "upscale":
        print("\nAmpliando clipes (Real-ESRGAN)")
        upscale.upscale(sc, force=args.force)

    if args.command in ("render", "all"):
        if manifest is None:
            raise SystemExit("Run 'voice' before 'render' (or 'all').")
        if args.music and not args.music.exists():
            raise SystemExit(f"Track not found: {args.music}")
        print("\nMontagem")
        if args.music_start < 0:
            raise SystemExit("--music-start must be 0 or more.")
        render.render(sc, manifest, music=args.music, music_start=args.music_start)
        qa.check(sc, manifest)


if __name__ == "__main__":
    main()
