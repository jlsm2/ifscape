"""HUD panel (panel_style "hud"): panel_rows validation and drawing."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ifscape import brand, panel, script  # noqa: E402

BASE = {"slug": "t", "title": "T", "panel_style": "hud", "panel_label": "TIME", "scenes": [
    {"id": "01", "on_screen": "What if?", "narration": "What if?", "stamp": "NOW",
     "panel_rows": [["Colds", "0"], ["Source", "Suttle 2007", 0.5]]},
    {"id": "02", "narration": "Next.", "panel_rows": [["A", "1"], ["B", "2"], ["C", "3"]]}]}


def load(data):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return script.load(p)


class PanelRows(unittest.TestCase):
    def test_good(self):
        s = load(BASE)
        self.assertEqual(s.panel_style, "hud")
        self.assertEqual(s.scenes[0].panel_rows, (("Colds", "0", 0.0), ("Source", "Suttle 2007", 0.5)))
        self.assertEqual(len(s.scenes[1].panel_rows), 3)

    def test_default_style_is_side(self):
        data = copy.deepcopy(BASE)
        data.pop("panel_style")
        for sc in data["scenes"]:
            sc.pop("panel_rows")
        self.assertEqual(load(data).panel_style, "side")

    def test_rows_need_hud_style(self):
        data = copy.deepcopy(BASE)
        data["panel_style"] = "side"
        with self.assertRaises(ValueError):
            load(data)

    def test_hook_scene_allows_only_two_rows(self):
        data = copy.deepcopy(BASE)
        data["scenes"][0]["panel_rows"] = [["A", "1"], ["B", "2"], ["C", "3"]]
        with self.assertRaises(ValueError) as cm:
            load(data)
        self.assertIn("at most 2", str(cm.exception))

    def test_long_label_rejected(self):
        data = copy.deepcopy(BASE)
        data["scenes"][1]["panel_rows"] = [["x" * 27, "1"]]
        with self.assertRaises(ValueError):
            load(data)

    def test_unknown_style(self):
        data = copy.deepcopy(BASE)
        data["panel_style"] = "big"
        with self.assertRaises(ValueError):
            load(data)


class HudDraw(unittest.TestCase):
    def test_fixed_canvas_and_rows_visible(self):
        with tempfile.TemporaryDirectory() as d:
            from PIL import Image
            a = panel.draw_hud("TIME", "00:01.00", (), Path(d) / "a.png", slots=3)
            b = panel.draw_hud("TIME", "00:01.00", (("Colds", "0"),), Path(d) / "b.png", slots=3)
            ia, ib = Image.open(a), Image.open(b)
            self.assertEqual(ia.size, (brand.HUD_W, brand.HUD_H))
            self.assertEqual(ib.size, ia.size)
            self.assertNotEqual(ia.tobytes(), ib.tobytes())

    def test_hud_stays_clear_of_the_buttons_and_the_title(self):
        self.assertLess(brand.HUD_XY[0] + brand.HUD_W, 930)           # platform button strip
        rows_bottom = brand.HUD_XY[1] + int(brand.HUD_LABEL_SIZE * 1.4) + 6 + int(brand.HUD_VALUE_SIZE * 1.12) + 10 \
            + brand.HUD_MAX_ROWS_WITH_HOOK * brand.HUD_ROW_H
        self.assertLess(rows_bottom, 470)                              # the opening question starts at y = 470


if __name__ == "__main__":
    unittest.main()
