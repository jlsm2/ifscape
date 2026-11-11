"""Script lint tests: py -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ifscape import lint, script  # noqa: E402


def _load(scenes: list[dict], sources: list[dict], **extra):
    data = {"slug": "t", "title": "T", "description": "A test.", "sources": sources, "hashtags": [],
            "scenes": scenes, **extra}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return script.load(p)


def _scene(i: str, narration: str, **kw):
    return {"id": i, "prompt": "x", "narration": narration, "highlight": [], **kw}


class LintRules(unittest.TestCase):
    def messages(self, sc):
        return [(sev, msg) for sev, msg in lint.lint(sc, post_path=Path("does-not-exist.txt"))]

    def test_stamp_without_source_is_alto(self):
        sc = _load([_scene("01", "Hello.", stamp="6 MONTHS")], [{"claim": "Water boils at 100 degrees", "url": "u"}])
        self.assertTrue(any(s == "HIGH" and "6 MONTHS" in m for s, m in self.messages(sc)))

    def test_too_many_numbers_on_one_screen_is_alto(self):
        busy = _scene("01", "", text=["You've heard ants lift 50 times their weight."],
                      counter={"label": "WEIGHT", "start": 1, "end": 4900000, "unit": "x", "change_at": 1.0},
                      panel_rows=[["LEGS", "X 28,900"], ["CARRIED", "ABOUT 9X"]],
                      fact={"value": "33 TIMES", "text": "longer than a queen"})
        sc = _load([busy], [], format="text", panel_style="hud")
        self.assertTrue(any(s == "HIGH" and "pieces with a number" in m for s, m in self.messages(sc)))

    def test_three_numbers_on_screen_pass(self):
        calm = _scene("01", "", text=["Her legs would give way."],
                      counter={"label": "WEIGHT", "start": 1, "end": 4900000, "unit": "x", "change_at": 1.0},
                      panel_rows=[["LEGS", "X 28,900"]], fact={"value": "33 TIMES", "text": "longer than a queen"})
        sc = _load([calm], [], format="text", panel_style="hud")
        self.assertFalse(any("pieces with a number" in m for _, m in self.messages(sc)))

    def test_stamp_with_source_passes(self):
        sc = _load([_scene("01", "Hello.", stamp="6 MONTHS")], [{"claim": "Crops fail within 6 months", "url": "u"}])
        self.assertFalse(any("6 MONTHS" in m for _, m in self.messages(sc)))

    def test_stamp_number_must_match_source(self):
        sc = _load([_scene("01", "Hello.", stamp="100,000 YEARS")], [{"claim": "Tilt changes over 41,000 years", "url": "u"}])
        self.assertTrue(any(s == "HIGH" and "100,000 YEARS" in m for s, m in self.messages(sc)))

    def test_stamp_one_year_accepts_a_year(self):
        sc = _load([_scene("01", "Hello.", stamp="1 YEAR")], [{"claim": "The surface freezes within a year", "url": "u"}])
        self.assertFalse(any("1 YEAR" in m for _, m in self.messages(sc)))

    def test_stamp_with_estimate_source_is_alto(self):
        sc = _load([_scene("01", "Hello.", stamp="1 WEEK")], [{"claim": "week estimate UNVERIFIED", "url": "u"}])
        self.assertTrue(any(s == "HIGH" and "1 WEEK" in m for s, m in self.messages(sc)))

    def test_now_is_not_a_deadline(self):
        sc = _load([_scene("01", "Hello.", stamp="NOW")], [])
        self.assertFalse(any("stamp" in m for _, m in self.messages(sc)))

    def test_soon_and_later_are_high(self):
        # a stamp only with important information; SOON/LATER tell nothing (stamp: null)
        sc = _load([_scene("01", "Hello.", stamp="NOW"), _scene("02", "Bye.", stamp="SOON"),
                    _scene("03", "Later.", stamp="LATER")], [])
        msgs = self.messages(sc)
        for stamp in ("SOON", "LATER"):
            self.assertTrue(any(s == "HIGH" and f"'{stamp}'" in m for s, m in msgs))

    def test_imperial_flagged_metric_not(self):
        bad = _load([_scene("01", "Pumps drained 13 million gallons a day.")], [])
        good = _load([_scene("01", "Pumps drained about 49 million liters a day.")], [])
        self.assertTrue(any(s == "HIGH" and "gallons" in m for s, m in self.messages(bad)))
        self.assertFalse(any("imperial" in m for _, m in self.messages(good)))

    def test_numbers_in_voice(self):
        sc = _load([_scene("01", "It takes 100 days."), _scene("02", "Then 60 more."), _scene("03", "And 4 years.")], [])
        self.assertTrue(any(s == "MEDIUM" and "numbers in the voice" in m for s, m in self.messages(sc)))

    def test_absolute_word_is_warning(self):
        sc = _load([_scene("01", "Every crop fails.")], [])
        self.assertTrue(any(s == "WARNING" and "every" in m.lower() for s, m in self.messages(sc)))

    def test_duration_gate(self):
        short = _load([_scene("01", "Hello there.")], [], voice_model="eleven_v4")
        self.assertTrue(any(s == "HIGH" and "estimated duration" in m for s, m in self.messages(short)))
        long_text = " ".join(["word"] * 300)
        longer = _load([_scene("01", long_text)], [], voice_model="eleven_v4")
        self.assertTrue(any(s == "HIGH" and "estimated duration" in m for s, m in self.messages(longer)))

    def test_internal_note_in_post(self):
        sc = _load([_scene("01", "Hello.")], [])
        with tempfile.TemporaryDirectory() as d:
            post = Path(d) / "t.post.txt"
            post.write_text("Sources:\n- x: [SOURCE PENDING]\n", encoding="utf-8")
            found = lint.lint(sc, post_path=post)
        self.assertTrue(any(s == "HIGH" and "SOURCE PENDING" in m for s, m in found))


if __name__ == "__main__":
    unittest.main()
