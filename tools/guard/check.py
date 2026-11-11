"""Cheap guard validations: agent frontmatter and script loading.

Uso:
  py tools/guard/check.py            # checks everything (agents and scripts)
  py tools/guard/check.py --hook     # reads the PostToolUse hook JSON on stdin and checks only the edited file

In hook mode, an error exits with code 2 and a message on stderr (Claude Code returns it to the model).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

AGENT_KEYS = ("name", "description", "tools")


def check_agent(path: Path) -> list[str]:
    import yaml
    if path.name == "lessons.md":  # training notebook, not an agent
        return []
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return [f"{path.name}: no '---' frontmatter at the start"]
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return [f"{path.name}: invalid YAML in the frontmatter ({str(e).splitlines()[0]}). "
                "Text with ': ' or '#' needs quotes."]
    if not isinstance(meta, dict):
        return [f"{path.name}: frontmatter is not a mapping"]
    errs = [f"{path.name}: missing '{k}'" for k in AGENT_KEYS if not meta.get(k)]
    if meta.get("name") and meta["name"] != path.stem:
        errs.append(f"{path.name}: name '{meta['name']}' differs from the file name")
    return errs


def check_script(path: Path, captions: bool = False) -> list[str]:
    from ifscape import script
    try:
        loaded = script.load(path)
    except Exception as e:  # noqa: BLE001 - any loader failure counts as a warning
        return [f"{path.name}: {e}"]
    return check_captions(loaded, path.name) if captions else []


def check_captions(loaded, name: str) -> list[str]:
    """Caption chunks of up to 4 words (the final call is an exception). Only applies in the hook: old scripts have larger chunks."""
    errs = []
    for sc in loaded.scenes:
        for cap in sc.captions:
            n = len(cap.split())
            if n > 4 and "imagine next" not in cap:
                errs.append(f"{name}: scene {sc.id}: caption with {n} words ('{cap}'); maximum 4")
    return errs


def check_file(path: Path) -> list[str]:
    path = path.resolve()
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        return []
    if re.fullmatch(r"\.claude/agents/[^/]+\.md", rel):
        return check_agent(path)
    if re.fullmatch(r"scripts/[^/]+\.json", rel):
        return check_script(path, captions=True)
    return []


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    if "--hook" in sys.argv:
        try:
            data = json.load(sys.stdin)
            file_path = (data.get("tool_input") or {}).get("file_path")
        except (ValueError, AttributeError):
            return 0
        errs = check_file(Path(file_path)) if file_path else []
    else:
        errs = []
        for p in sorted((ROOT / ".claude" / "agents").glob("*.md")):
            errs += check_agent(p)
        for p in sorted((ROOT / "scripts").glob("*.json")):
            errs += check_script(p)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 2
    if "--hook" not in sys.argv:
        print("ok: valid agents and scripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
