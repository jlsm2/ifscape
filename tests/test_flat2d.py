"""Tests of the 2D system ('flat' field, HUD and karaoke): py -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ifscape import render, script  # noqa: E402
from ifscape.timing import Chunk  # noqa: E402


def _load(scene: dict, **extra):
    data = {"slug": "t", "title": "t", "scenes": [{"id": "01", "narration": "Then someone knocks on the glass.", **scene}],
            **extra}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
    return script.load(f.name)


class Flat(unittest.TestCase):
    def test_demo_loads(self):
        sc = script.load(ROOT / "scripts" / "flat2d-demo.json")
        self.assertEqual([s.flat["shot"] for s in sc.scenes], ["plan", "card", "close", "close", "duo", "wide", "wide"])
        self.assertFalse(sc.panel)
        self.assertEqual(sc.caption_style, "karaoke")
        self.assertEqual(sorted(sc.cast), ["hale", "man", "rosa", "sam"])
        self.assertEqual(sc.cast["rosa"]["hair_style"], "long")
        self.assertEqual(sc.cast["sam"]["accessory"], "headlamp")      # Sam keeps the headlamp


class Cast(unittest.TestCase):
    CAST = {"rosa": {"name": "ROSA", "hair": "#22170f", "hair_style": "long", "shirt": [52, 120, 118]}}

    def test_hair_forms_and_bad_values(self):
        sc = _load({"flat": {"shot": "close", "who": "rosa"}}, cast=self.CAST)
        self.assertEqual(sc.cast["rosa"]["hair"], (34, 23, 15))
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close"}}, cast={"rosa": {"accessory": "hat"}})
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close"}}, cast={"rosa": {"skin": "#12"}})

    def test_who_must_be_in_cast(self):
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close", "who": "hale"}}, cast=self.CAST)
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "duo", "who": ["sam", "sam"]}}, cast=self.CAST)
        with self.assertRaises(ValueError):            # talk needs who
            _load({"flat": {"shot": "duo", "who": ["sam", "rosa"], "events": [{"do": "talk", "word": "knocks"}]}},
                  cast=self.CAST)
        _load({"flat": {"shot": "duo", "who": ["sam", "rosa"], "counter": True,
                        "events": [{"do": "talk", "who": "rosa", "word": "then", "until_word": "knocks"}]}}, cast=self.CAST)

    def test_wide_and_plan_events(self):
        with self.assertRaises(ValueError):            # set desconhecido
            _load({"flat": {"shot": "wide", "set": "mall"}})
        with self.assertRaises(ValueError):            # bite needs a target that is another actor
            _load({"flat": {"shot": "wide", "set": "busstop", "actors": [{"id": "rosa", "at": "shelter"}],
                            "events": [{"do": "bite", "who": "rosa", "target": "rosa", "at": 0.5}]}}, cast=self.CAST)
        _load({"flat": {"shot": "plan", "place": "busstop", "actors": [{"id": "rosa", "at": "shelter"},
                                                                       {"id": "z", "kind": "infected", "at": "far"}],
                        "events": [{"do": "bite", "who": "z", "target": "rosa", "at": 0.3}]}}, cast=self.CAST)

    def test_expr_names_match(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from flat2d import acting, close, validate
        self.assertEqual(set(validate.EXPRS), set(acting.EXPRS))
        self.assertEqual(set(validate.BGS), set(close.BGS))


class Motion(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))

    def test_planted_foot_does_not_slide(self):
        from flat2d.wide import Walker
        for gait in ("walk", "run", "shuffle"):
            w = Walker(100.0, 1240.0, 1)
            w.move(0.5, 640.0, 1240.0, gait, None)
            prev = w.state(0.0)["feet"]
            for i in range(1, 30 * 12):
                cur = w.state(i / 30)["feet"]
                for a, b in zip(prev, cur):
                    if a[1] >= 1240.0 - 1e-6 and b[1] >= 1240.0 - 1e-6:     # planted on both frames
                        self.assertAlmostEqual(a[0], b[0], delta=1.0, msg=f"{gait} skated on frame {i}")
                prev = cur
            end = w.state(20.0)
            self.assertAlmostEqual(end["x"], 640.0)
            self.assertLess(abs(end["feet"][0][0] - end["feet"][1][0]), 40)  # feet together at the end

    def test_mouth_moves_only_in_talk(self):
        from flat2d.acting import Acting
        from flat2d.cast import look_for
        a = Acting(look_for({}, "sam"), 6.0)
        words = [(1.0, 1.4, "show"), (1.4, 1.7, "me"), (1.7, 2.3, "your"), (2.3, 2.8, "hand")]
        a.apply({"do": "talk", "t": 1.0, "t_end": 2.85, "_words": words})
        shapes = {a.mouth(i / 30) for i in range(30, 85)}
        self.assertTrue({1, 2, 3} & shapes and 0 in shapes)          # opens and closes within the line
        self.assertEqual({a.mouth(i / 30) for i in range(0, 29)} | {a.mouth(i / 30) for i in range(90, 180)}, {0})

    def test_close_is_a_framing_and_glass_masks_frame(self):
        from flat2d import sets
        from flat2d.engine import Clip
        from flat2d.wide import Wide
        clip = Clip({"shot": "close", "who": "sam", "bg": "door", "silhouette": True}, 3.0)
        self.assertIsInstance(clip.shot, Wide)                         # the close-up is the stage zoomed in, not another figure
        self.assertEqual(clip.shot.name, "frontdoor")
        m = sets.glass_mask("frontdoor")
        self.assertEqual(m.getpixel((540, 800)), 0)                     # middle mullion: in front of the silhouette
        self.assertEqual(m.getpixel((400, 800)), 255)                   # glass (no grille)
        self.assertEqual(clip.frame(30).size, (1080, 1920))

    def test_knock_hits_match_shake_and_bite_cues(self):
        from flat2d.engine import Clip
        from flat2d.cast import check
        cast = check({"rosa": {"name": "ROSA"}, "man": {"name": "MAN", "accessory": "bandage"}})
        flat = {"shot": "wide", "set": "busstop", "actors": [{"id": "man", "at": "shelter"}, {"id": "rosa", "at": "lamp"}],
                "events": [{"do": "knock", "who": "man", "on": "door", "at": 0.1, "times": 2},
                           {"do": "bite", "who": "man", "target": "rosa", "at": 0.5}]}
        clip = Clip(flat, 6.0, "", None, {}, cast)
        cues = clip.cues()
        hits = [c["frame"] for c in cues if c["do"] == "knock_hit"]
        self.assertEqual(len(hits), 2)
        self.assertTrue(all(f in clip.shake for f in hits))
        self.assertEqual([c["do"] for c in cues if c["do"] in ("bite_contact", "turn")], ["bite_contact", "turn"])
        img = clip.frame(round(cues[-1]["frame"]) - 5)
        self.assertEqual(img.size, (1080, 1920))
        reds = [p for p in img.resize((108, 192)).getdata() if p[0] > 150 and p[1] < 80 and p[2] < 80]
        self.assertEqual(reds, [])                                    # bite without red

    def test_unknown_event_is_error(self):
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close", "events": [{"do": "heat", "count": 2, "at": 0.5}]}})

    def test_word_must_be_in_narration(self):
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close", "events": [{"do": "knock", "word": "door"}]}})
        sc = _load({"flat": {"shot": "close", "events": [{"do": "knock", "word": "knocks"}]}})
        self.assertEqual(sc.scenes[0].flat["events"][0]["do"], "knock")

    def test_clock_null_hides_and_absent_carries(self):
        self.assertIsNone(_load({"flat": {"shot": "close"}}).scenes[0].clock)
        self.assertFalse(_load({"flat": {"shot": "close"}, "clock": None}).scenes[0].clock)
        with self.assertRaises(ValueError):
            _load({"flat": {"shot": "close"}, "clock": {"day": 0, "from": "25:00"}})

    def test_old_scripts_keep_defaults(self):
        sc = _load({})
        self.assertTrue(sc.panel)
        self.assertEqual(sc.caption_style, "default")
        self.assertIsNone(sc.scenes[0].flat)

    def test_karaoke_segments_follow_words(self):
        words = [{"word": "Then", "start": 0.2, "end": 0.5}, {"word": "someone", "start": 0.5, "end": 0.9},
                 {"word": "knocks.", "start": 1.6, "end": 2.0}]
        segs = render._karaoke_segments(Chunk("Then someone knocks.", 0.0, 2.5), words)
        self.assertEqual(segs[0][2], -1)                         # before the 1st word: no box
        active = [(round(a, 2), j) for a, _, j in segs if j >= 0]
        self.assertEqual(active, [(0.2, 0), (0.5, 1), (1.6, 2)])
        self.assertTrue(all(b > a for a, b, _ in segs))
        self.assertTrue(all(segs[i][1] == segs[i + 1][0] for i in range(len(segs) - 1)))   # no gap


if __name__ == "__main__":
    unittest.main()
