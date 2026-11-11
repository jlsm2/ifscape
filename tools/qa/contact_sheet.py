"""Contact sheet per scene (step 6 of the production order), for any video.

  py tools/qa/contact_sheet.py scripts/<slug>.json --list   # frames to render: paste into 'blender --stills'
  py tools/qa/contact_sheet.py scripts/<slug>.json          # builds build/<slug>/blender/keyframes/scene_XX.png

Keyframes: build/<slug>/blender/keyframes.json, {"02": [[125, "bush"], [167, "grass"]], ...}, written by the
blender-specialist (one per voice trigger and one per cut). Without that file, it uses 5 frames per scene (start, 25%,
50%, 75% and the last). The screen zones (title, panel, caption, buttons on the right) come from ifscape/brand.py.
Replaces tools/blender/plants_keyframes_sheet.py, which had hard-coded plants-extinct paths.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ifscape import brand, script  # noqa: E402

TW, TH = 360, 640
S = TW / 1080
AMBER, WHITE, BG = (245, 165, 36), (244, 246, 248), (11, 15, 23)


def keyframes(slug: str, timeline: dict) -> dict[str, list[tuple[int, str]]]:
    path = ROOT / "build" / slug / "blender" / "keyframes.json"
    if path.exists():
        return {sid: [(int(f), str(label)) for f, label in rows]
                for sid, rows in json.loads(path.read_text(encoding="utf-8")).items()}
    out = {}
    for sc in timeline["scenes"]:
        a, b = sc["start"] + 1, sc["end"]      # Blender frames: start at 1; the JSON end is exclusive
        marks = sorted({a, a + (b - a) // 4, a + (b - a) // 2, a + 3 * (b - a) // 4, b})
        out[sc["id"]] = [(f, f"{round(100 * (f - a) / max(b - a, 1))}%") for f in marks]
    return out


def zones(img: Image.Image, show_panel: bool, first: bool) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    if first:
        d.rectangle([0, 470 * S, TW - 1, 700 * S], outline=(*AMBER, 230), width=2)          # title question
    if show_panel:
        x, y = brand.STAMP_XY
        d.rectangle([x * S, y * S, 520 * S, (y + 240) * S], outline=(255, 255, 255, 230), width=2)   # live panel
    c = brand.CAPTION_CENTER_Y
    d.rectangle([0, (c - 70) * S, TW - 1, (c + 70) * S], outline=(80, 200, 255, 200), width=1)       # legenda
    d.line([930 * S, 0, 930 * S, TH], fill=(255, 60, 60, 200), width=1)                          # platform buttons


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path)
    ap.add_argument("--list", action="store_true", help="only prints the frames to render")
    args = ap.parse_args()

    sc = script.load(args.script)
    blender_dir = ROOT / "build" / sc.slug / "blender"
    timeline = json.loads((blender_dir / "timeline.json").read_text(encoding="utf-8"))
    rows = keyframes(sc.slug, timeline)
    wanted = sorted({f for items in rows.values() for f, _ in items})
    if args.list:
        print(",".join(str(f) for f in wanted))
        return

    missing = [f for f in wanted if not (blender_dir / f"still_{f:04d}.png").exists()]
    if missing:
        raise SystemExit(f"{len(missing)} stills missing in {blender_dir}: render with\n"
                         f"  py -m ifscape blender {args.script} --stills {','.join(map(str, missing))}")
    font = ImageFont.truetype(str(ROOT / "fonts" / "Barlow-SemiBold.ttf"), 26)
    small = ImageFont.truetype(str(ROOT / "fonts" / "Barlow-Medium.ttf"), 20)
    out_dir = blender_dir / "keyframes"
    out_dir.mkdir(exist_ok=True)
    scenes = {s.id: s for s in sc.scenes}
    for sid, items in rows.items():
        scene = scenes.get(sid)
        has_panel = bool(scene and (scene.stamp or scene.counter or scene.panel_label))
        sheet = Image.new("RGB", (len(items) * (TW + 8) + 8, TH + 60), BG)
        d = ImageDraw.Draw(sheet)
        for k, (f, label) in enumerate(items):
            im = Image.open(blender_dir / f"still_{f:04d}.png").convert("RGB").resize((TW, TH), Image.LANCZOS)
            zones(im, has_panel, first=sid == sc.scenes[0].id)
            x = 8 + k * (TW + 8)
            sheet.paste(im, (x, 52))
            d.text((x, 4), f"q{f}", font=font, fill=AMBER)
            d.text((x + 80, 9), label, font=small, fill=WHITE)
        sheet.save(out_dir / f"scene_{sid}.png")
    print(f"{len(rows)} sheets in {out_dir}")


if __name__ == "__main__":
    main()
