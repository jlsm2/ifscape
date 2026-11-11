"""Guard tests: py -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "guard"))

import check  # noqa: E402
from ifscape import voice  # noqa: E402


class AgentsLoad(unittest.TestCase):
    def test_frontmatter_valid(self):
        for p in sorted((ROOT / ".claude" / "agents").glob("*.md")):
            with self.subTest(agent=p.name):
                self.assertEqual(check.check_agent(p), [])


class ScriptsLoad(unittest.TestCase):
    def test_all_scripts_load(self):
        for p in sorted((ROOT / "scripts").glob("*.json")):
            with self.subTest(script=p.name):
                self.assertEqual(check.check_script(p), [])


class VoiceCache(unittest.TestCase):
    def test_fingerprint_stable_and_sensitive(self):
        a = voice._fingerprint("Hello.", "v", "eleven_multilingual_v2")
        self.assertEqual(a, voice._fingerprint("Hello.", "v", "eleven_multilingual_v2"))
        self.assertNotEqual(a, voice._fingerprint("Hello!", "v", "eleven_multilingual_v2"))
        self.assertNotEqual(a, voice._fingerprint("Hello.", "v", "eleven_v4"))


def _scene(sid: str, words: int):
    from ifscape.script import Scene
    return Scene(id=sid, prompt="", style="", narration=" ".join(["word"] * words), on_screen="",
                 stamp=None, highlight=[], min_seconds=2.0)


class DurationBudget(unittest.TestCase):
    def test_estimate_matches_v4_rate(self):
        from ifscape import timing
        # 12 scenes of 13 words on v4: 156/2.66 + 12 x 0.45 + 2 s pause = ~66.0 s, within the target
        seconds, words = timing.estimate_total([_scene(f"{i:02d}", 13) for i in range(12)], "eleven_v4")
        self.assertEqual(words, 156)
        self.assertAlmostEqual(seconds, 156 / 2.66 + 12 * 0.45 + 2.0, delta=0.1)
        self.assertIn("within the target", timing.budget_line(seconds, words, "eleven_v4"))

    def test_budget_line_says_how_much_to_cut(self):
        from ifscape import timing
        self.assertIn("cut ~53 words", timing.budget_line(89.8, 216, "eleven_v4"))
        self.assertIn("BELOW", timing.budget_line(55.0, 140, "eleven_v4"))

    def test_voice_refuses_long_script_before_spending(self):
        import os
        import shutil
        from ifscape import util, voice
        from ifscape.script import Script
        slug = "_test_voice_guard"
        sc = Script(slug=slug, channel="ifscape", title="t", description="", sources=[], hashtags=[],
                    scenes=[_scene(f"{i:02d}", 20) for i in range(12)], voice_model="eleven_v4")
        old = {k: os.environ.get(k) for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID")}
        os.environ.update(ELEVENLABS_API_KEY="fake", ELEVENLABS_VOICE_ID="fake")
        try:
            with self.assertRaises(SystemExit) as ctx:
                voice.generate(sc)            # 240 words on v4 ~ 98 s: stops before calling the API
            self.assertIn("--allow-long", str(ctx.exception))
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
            shutil.rmtree(util.ROOT / "build" / slug, ignore_errors=True)


class SoundAndMaster(unittest.TestCase):
    def test_sfx_word_anchor_follows_voice(self):
        from ifscape import sfx
        starts = {"05": (20.0, 6.0)}
        manifest = {"05": {"words": [{"word": "Both", "start": 0.1}, {"word": "billions,", "start": 1.4},
                                      {"word": "billions", "start": 3.0}]}}
        self.assertAlmostEqual(sfx._anchor(starts, manifest, "05", "billions"), 21.4)
        self.assertAlmostEqual(sfx._anchor(starts, manifest, "05", "billions#2", 0.2), 23.2)
        self.assertAlmostEqual(sfx._anchor(starts, manifest, "05", 0.5), 23.0)   # fraction still applies
        with self.assertRaises(ValueError):
            sfx._anchor(starts, manifest, "05", "trees")

    def test_master_lufs_default_by_format(self):
        from ifscape.script import _master_lufs
        self.assertEqual(_master_lufs({}, "voice"), -16.0)
        self.assertIsNone(_master_lufs({}, "text"))
        self.assertIsNone(_master_lufs({"master_lufs": False}, "voice"))
        self.assertEqual(_master_lufs({"master_lufs": -14}, "text"), -14.0)


class BlenderDigest(unittest.TestCase):
    def test_digest_covers_lib_but_not_examples(self):
        from ifscape import blender
        rel = {p.relative_to(ROOT / "tools" / "blender").parts[0] for p in blender._source_files()}
        self.assertIn("lib", rel)
        self.assertNotIn("examples", rel)


class KitBlenderSource(unittest.TestCase):
    """The kit runs inside Blender (bpy); here only the text is checked: the path guard and the exported checks."""

    def test_kit_exposes_voice_anchor_and_checks(self):
        src = (ROOT / "tools" / "blender" / "kit.py").read_text(encoding="utf-8")
        for name in ("def W(", "def word_start(", "def require_reach(", "def require_grounded(",
                     "def require_in_frame(", "def fail_if_problems("):
            self.assertIn(name, src)
        self.assertIn("fail_if_problems()", src.split("def run(")[1])      # run() fails the build
        self.assertIn("is_absolute()", src)                                 # a relative --out writes to C:\build


class ContactSheet(unittest.TestCase):
    def test_default_keyframes_cover_each_scene(self):
        sys.path.insert(0, str(ROOT / "tools" / "qa"))
        import contact_sheet
        tl = {"scenes": [{"id": "01", "start": 0, "end": 100}, {"id": "02", "start": 100, "end": 180}]}
        rows = contact_sheet.keyframes("_slug_no_file", tl)
        self.assertEqual([f for f, _ in rows["01"]][0], 1)
        self.assertEqual([f for f, _ in rows["01"]][-1], 100)
        self.assertEqual([f for f, _ in rows["02"]][0], 101)
        self.assertEqual([f for f, _ in rows["02"]][-1], 180)


class Metrics(unittest.TestCase):
    def test_collect_reads_disk_without_voice(self):
        import shutil
        from ifscape import metrics, util
        from ifscape.script import Script
        slug = "_test_metrics"
        d = util.ROOT / "build" / slug
        (d / "voice").mkdir(parents=True, exist_ok=True)
        try:
            (d / "review.md").write_text("x", encoding="utf-8")
            (d / "factcheck-2.md").write_text("x", encoding="utf-8")
            sc = Script(slug=slug, channel="ifscape", title="t", description="", sources=[], hashtags=[],
                        scenes=[_scene("01", 10)], voice_model="eleven_v4")
            data = metrics.collect(sc)
            self.assertEqual(data["review_rounds"]["script_review"], 1)
            self.assertEqual(data["review_rounds"]["factcheck"], 1)
            self.assertIn("estimated_seconds", data["duration"])
            self.assertNotIn("actual_seconds", data["duration"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ScriptStrictKeys(unittest.TestCase):
    def test_unknown_field_is_rejected_with_hint(self):
        import json
        import tempfile
        from ifscape import script
        base = {"slug": "x", "title": "t", "scenes": [{"id": "01", "narration": "Hi.", "direcion": "[calm]"}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.json"
            path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                script.load(path)
            self.assertIn("direction", str(ctx.exception))
            base["scenes"][0] = {"id": "01", "narration": "Hi.", "_nota": "livre"}
            path.write_text(json.dumps(base), encoding="utf-8")
            self.assertEqual(script.load(path).scenes[0].id, "01")


class VoiceMovedRepo(unittest.TestCase):
    def test_cache_survives_moved_folder(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            vdir = Path(d)
            (vdir / "01.mp3").write_bytes(b"x")
            meta = {"audio": r"C:\pasta\antiga\voice\01.mp3", "fingerprint": "fp", "duration": 1.0, "words": []}
            (vdir / "01.json").write_text(json.dumps(meta), encoding="utf-8")
            got = voice._cached(vdir / "01.json", "fp")
            self.assertEqual(Path(got["audio"]), vdir / "01.mp3")
            self.assertIsNone(voice._cached(vdir / "01.json", "outro"))


if __name__ == "__main__":
    unittest.main()
