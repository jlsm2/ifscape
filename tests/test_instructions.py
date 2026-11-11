"""Instruction guard: an old rule that already caused trouble does not come back into the active agents, skills and docs.

Each pattern is a revoked instruction. A line passes if it says itself that the rule is historical
("replaced", "Was:", "forbidden", "never", "old process", "rejected", "removed in"). py -m unittest discover tests
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FILES = ([ROOT / "CLAUDE.md", ROOT / "docs" / "script-rules.md", ROOT / "docs" / "review-gates.md",
          ROOT / "docs" / "briefing-template.md"]
         + sorted((ROOT / ".claude" / "agents").glob("*.md"))
         + sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")))

STALE = {
    r'(replace with|suggestion is|becomes) "?SOON"?\s*/\s*"?LATER': "SOON/LATER are forbidden: use `stamp: null`",
    r'becomes "Nobody has tested': "the 'nobody tested it' crutch is forbidden on screen",
    r"will have to say it on screen": "'nobody tested it' does not go on screen",
    r"Recipe of the ants park": "PRESET-PARK.md was rejected",
    r"facts-final\.md": "file that only exists in moon-disappeared",
    r"10 to 12 scenes, swap": "lean mode: 5 to 6 scenes",
    r"alternate the format between videos": "voice or text is asked in the briefing",
    r"image physics belongs to the `director`": "image physics belongs to the script-review",
}
HISTORIC = re.compile(r"replaced|\bWas:|\bwas:|forbidden|never|old process|rejected|removed in", re.I)


class StaleInstructions(unittest.TestCase):
    def test_no_revoked_rule_in_active_instructions(self):
        found = []
        for path in FILES:
            if not path.exists():
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if HISTORIC.search(line):
                    continue
                for pat, why in STALE.items():
                    if re.search(pat, line):
                        found.append(f"{path.relative_to(ROOT)}:{n}: '{pat}' ({why})")
        self.assertEqual(found, [], "revoked rule in an active instruction:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
