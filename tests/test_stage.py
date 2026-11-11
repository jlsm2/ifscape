"""Data-driven stage (tools/stage): validation of the 'stage' field and the digest of the old videos."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "stage"))

import validate  # noqa: E402

GOOD = {"set": "meadow", "light": "noon",
        "props": [{"id": "trex", "name": "rex", "at": [0, 18], "len": 12},
                  {"id": "zebra", "name": "herd", "layout": "herd", "n": 5, "at": [0, 30]}],
        "camera": {"preset": "dolly_in", "at": [0, -2], "look": "rex"},
        "cues": [{"t": 1.0, "do": "shake"}, {"word": "run", "do": "vanish", "target": "herd"}]}


class StageValidate(unittest.TestCase):
    def bad(self, edit, text):
        stage = copy.deepcopy(GOOD)
        edit(stage)
        with self.assertRaises(ValueError) as cm:
            validate.check("01", stage)
        self.assertIn(text, str(cm.exception))

    def test_good(self):
        validate.check("01", GOOD)

    def test_typo_in_set_suggests(self):
        self.bad(lambda s: s.update(set="meadw"), "meadow")

    def test_unknown_catalog_id(self):
        self.bad(lambda s: s["props"][0].update(id="trexx"), "trex")

    def test_camera_look_must_be_a_prop(self):
        self.bad(lambda s: s["camera"].update(look="nobody"), "look")

    def test_group_member_is_a_valid_target(self):
        stage = copy.deepcopy(GOOD)
        stage["camera"]["look"] = "herd3"
        validate.check("01", stage)

    def test_cue_needs_when(self):
        self.bad(lambda s: s["cues"].append({"do": "pop", "target": "rex"}), "when")

    def test_unknown_prop_field(self):
        self.bad(lambda s: s["props"][0].update(lenght=3), "len")

    def test_duplicate_names(self):
        self.bad(lambda s: s["props"].append({"id": "man", "name": "rex"}), "in use")


class StageContinuous(unittest.TestCase):
    PATH = {"preset": "path", "path": [{"t": 0, "prev": True}, {"t": 4, "at": [3, 4], "look": "rex"}]}

    def test_path_camera_and_same_set(self):
        stage = copy.deepcopy(GOOD)
        stage.pop("light"); stage["set"] = "same"; stage["camera"] = copy.deepcopy(self.PATH)
        validate.check("02", stage)

    def test_same_set_accepts_light_change_at_cut(self):
        # with set 'same', 'light' switches the light state at the cut (time jump)
        stage = copy.deepcopy(GOOD)
        stage["set"] = "same"
        validate.check("02", stage)

    def test_same_set_rejects_unknown_light(self):
        stage = copy.deepcopy(GOOD)
        stage["set"] = "same"
        stage["light"] = "sunset"
        with self.assertRaises(ValueError) as cm:
            validate.check("02", stage)
        self.assertIn("light", str(cm.exception))

    def test_path_needs_two_points_and_a_time(self):
        for bad, text in (([{"t": 0, "at": [0, 0], "look": "rex"}], "2 points"),
                          ([{"at": [0, 0], "look": "rex"}, {"t": 1, "prev": True}], "when")):
            stage = copy.deepcopy(GOOD)
            stage["camera"] = {"preset": "path", "path": bad}
            with self.assertRaises(ValueError) as cm:
                validate.check("01", stage)
            self.assertIn(text, str(cm.exception))

    def test_light_and_grow_cues(self):
        stage = copy.deepcopy(GOOD)
        stage["cues"] += [{"t": 1, "do": "light", "light": "dusk", "dur": 5},
                          {"t": 1, "do": "grow", "target": "herd", "from": 0.1, "stagger": 2}]
        validate.check("01", stage)
        stage["cues"][-2]["light"] = "dusky"
        with self.assertRaises(ValueError) as cm:
            validate.check("01", stage)
        self.assertIn("dusk", str(cm.exception))


class StageDigest(unittest.TestCase):
    def test_legacy_digest_ignores_stage_code(self):
        from ifscape import blender
        files = {p.relative_to(ROOT).as_posix() for p in blender._source_files()}
        self.assertFalse(any(f.startswith("tools/stage/") for f in files))

    def test_stage_digest_ignores_other_videos(self):
        from ifscape import blender
        files = {p.relative_to(ROOT).as_posix() for p in blender._stage_files()}
        self.assertIn("tools/stage/build.py", files)
        self.assertIn("tools/stage/catalog.json", files)
        self.assertNotIn("tools/blender/viruses_set.py", files)

    def test_catalog_has_the_pilot_dinosaurs(self):
        ids = {i["id"] for i in json.loads((ROOT / "tools" / "stage" / "catalog.json").read_text(encoding="utf-8"))["items"]}
        self.assertTrue({"trex", "triceratops", "velociraptor", "apatosaurus"} <= ids)



class StageSound(unittest.TestCase):
    def test_closing_sound(self):
        from types import SimpleNamespace as NS
        from ifscape import sfx
        lib = sfx.library()
        a = NS(id="01", lines=("One two three.", "What should I imagine next?"),
               stage={"set": "meadow", "light": "noon", "props": [], "cues": []})
        script = NS(scenes=[a], show_end_card=True)
        cues = sfx._stage_cues(script, {"01": (0.0, 8.0)}, lib)
        close = 1 + 0.3 * 3                                          # 1 s + 0.3 s per word, minimum 2 s
        self.assertAlmostEqual(sfx._closing_time(script, {"01": (0.0, 8.0)}), max(2.0, close))
        self.assertTrue(any(c.sound == "boom" for c in cues))        # impact when the end card comes in
        under = [c for c in cues if c.sound == "drone"]
        self.assertEqual(len(under), 1)                              # only the low drone stays under the question
        self.assertTrue(all(c.start + c.seconds <= 2.0 + 1e-6 for c in cues if c.sound == "leaves_breeze"))   # ambiente acaba

    def test_bed_changes_with_light(self):
        from types import SimpleNamespace as NS
        from ifscape import sfx
        lib = sfx.library()
        a = NS(id="01", stage={"set": "meadow", "light": "dawn", "props": [], "cues": []})
        b = NS(id="02", stage={"set": "same", "props": [], "cues": [{"t": 0.0, "do": "light", "light": "dusk", "dur": 10}]})
        cues = sfx._stage_cues(NS(scenes=[a, b]), {"01": (0.0, 6.0), "02": (6.0, 6.0)}, lib)
        spans = {(c.sound, c.start, c.start + c.seconds) for c in cues if c.sound != "light_sweep"}
        self.assertIn(("birds_small", 0.0, 6.0), spans)               # dawn: birds
        self.assertIn(("crickets", 6.0, 12.0), spans)                 # dusk: crickets
        self.assertIn(("leaves_breeze", 0.0, 6.0), spans)             # the wind continues in both scenes (gain changes: 2 layers)
        self.assertIn(("leaves_breeze", 6.0, 12.0), spans)

    def test_sound_by_rule(self):
        from types import SimpleNamespace as NS
        from ifscape import sfx
        lib = sfx.library()
        a = NS(id="01", stage={"set": "savanna", "light": "dusk",
                               "props": [{"id": "zebra", "to": [1, 1]}, {"id": "trex"}],
                               "cues": [{"t": 1.0, "do": "shake"}, {"t": 2.0, "do": "light", "light": "night", "dur": 8}]})
        b = NS(id="02", stage={"set": "same", "props": [{"id": "trex", "path": [[0, 0], [3, 3]]}], "cues": []})
        starts = {"01": (0.0, 6.0), "02": (6.0, 6.0)}
        cues = sfx._stage_cues(NS(scenes=[a, b]), starts, lib)
        by = {(c.sound, c.start) for c in cues}
        self.assertIn(("crickets", 0.0), by)                          # the light turns night before the middle of scene 1
        self.assertEqual(sum(1 for c in cues if c.sound == "crickets"), 1)   # scene 2 equal: a single layer
        self.assertEqual(max(c.start + c.seconds for c in cues if c.sound == "crickets"), 12.0)
        self.assertFalse(any(c.sound == "savanna_wind" for c in cues))
        self.assertIn(("hooves", 0.0), by)                            # zebra walks in scene 1
        self.assertIn(("rumble", 6.0), by)                            # trex walks in scene 2
        self.assertTrue(any(c.sound == "hit" for c in cues))
        self.assertTrue(any(c.sound == "light_sweep" and c.start == 2.0 for c in cues))


if __name__ == "__main__":
    unittest.main()
