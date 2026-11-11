"""Duration of each scene and the caption chunks with their times."""

from dataclasses import dataclass

from .script import Scene

TAIL_SECONDS = 0.45      # breathing room after the narration before the cut
MAX_WORDS_PER_CHUNK = 3  # the ideal; a chunk reaches 4 words when that avoids a bad break
BREAK_CHARS = ".,!?;:"
# Words that cannot close a caption chunk ("SAME WAVE AS" / "WI-FI").
WEAK_WORDS = {
    "a", "an", "the", "of", "as", "is", "are", "was", "were", "be", "to", "in", "into", "on", "at", "by",
    "for", "from", "with", "near", "like", "than", "and", "or", "but", "so", "that", "your", "my", "our",
    "their", "his", "her", "its", "this", "these", "every",
}
WEAK_END_COST = 3
ORPHAN_COST = 2
LONG_CHUNK_COST = 1
SHORT_CHUNK_COST = 1    # 2 words: acceptable, but 3 reads better


@dataclass
class Chunk:
    text: str
    start: float
    end: float


READ_BASE = 1.0         # text format: on-screen time of a sentence = base + per word (minimum READ_MIN)
READ_PER_WORD = 0.3
READ_MIN = 2.0


def line_seconds(line: str) -> float:
    return max(READ_MIN, READ_BASE + READ_PER_WORD * len(line.split()))


def scene_duration(scene: Scene, meta: dict | None) -> float:
    if scene.lines:
        return round(max(scene.min_seconds, sum(line_seconds(s) for s in scene.lines)), 3)
    spoken = meta["duration"] if meta and scene.narration else 0.0
    return round(max(scene.min_seconds, spoken + TAIL_SECONDS if spoken else 0.0), 3)


def estimated_duration(scene: Scene) -> float:
    """Estimate without generated narration (used only to suggest the clip size)."""
    if scene.lines:
        return scene_duration(scene, None)
    words = len(scene.narration.split())
    return round(max(scene.min_seconds, words * 0.42 + 0.3 + TAIL_SECONDS if words else 0.0), 1)


# Video duration (from analytics: 67 s = 15% completion, 80 s = 6 to 9%).
TARGET_SECONDS = (61.0, 70.0)
# Measured pace of the Chris voice: v2 ~3.0 words/s; v4 ~2.66 (plants-extinct: 216 words in 81.2 s of speech).
WORDS_PER_SECOND = {"eleven_v4": 2.66, "eleven_v3": 2.66}
DEFAULT_WORDS_PER_SECOND = 3.0
CLOSING_PAUSE_SECONDS = 2.0   # same as voice.CLOSING_PAUSE (here to avoid importing voice)


def estimate_total(scenes: list[Scene], model: str) -> tuple[float, int]:
    """Estimated video duration before the voice: (seconds, narrated words). Text format uses reading time."""
    wps = WORDS_PER_SECOND.get(model, DEFAULT_WORDS_PER_SECOND)
    total, words = 0.0, 0
    for scene in scenes:
        if scene.lines:
            total += scene_duration(scene, None)
            continue
        n = len(scene.narration.split())
        words += n
        total += max(scene.min_seconds, n / wps + TAIL_SECONDS if n else 0.0)
    if words:
        total += CLOSING_PAUSE_SECONDS
    return round(total, 1), words


def budget_line(seconds: float, words: int, model: str) -> str:
    """Summary of the duration against the target, with how many words to cut or add."""
    lo, hi = TARGET_SECONDS
    wps = WORDS_PER_SECOND.get(model, DEFAULT_WORDS_PER_SECOND)
    if seconds > hi:
        verdict = f"ABOVE the target: cut ~{round((seconds - hi) * wps)} words"
    elif seconds < lo:
        verdict = f"BELOW {lo:.0f} s: add ~{round((lo - seconds) * wps) + 1} words or 'min_seconds'"
    else:
        verdict = "within the target"
    return f"estimated duration {seconds:.1f} s, {words} words ({model or 'v2'}, {wps} words/s): {verdict} ({lo:.0f} to {hi:.0f} s)"


def _sentences(words: list[dict]) -> list[list[dict]]:
    """Cuts at the pauses in speech (punctuation): a caption chunk never crosses a comma or period."""
    parts, current = [], []
    for word in words:
        current.append(word)
        if word["word"][-1] in BREAK_CHARS:
            parts.append(current)
            current = []
    return parts + [current] if current else parts


def _chunk_cost(group: list[dict]) -> int:
    last = group[-1]["word"].strip(BREAK_CHARS + "\"'").lower()
    cost = WEAK_END_COST if last in WEAK_WORDS and group[-1]["word"][-1] not in BREAK_CHARS else 0
    if len(group) == 2:
        cost += SHORT_CHUNK_COST
    if len(group) == 1:
        cost += ORPHAN_COST
    if len(group) > MAX_WORDS_PER_CHUNK:
        cost += LONG_CHUNK_COST
    return cost


def _split(words: list[dict]) -> list[list[dict]]:
    """Splits a chunk without a pause into groups of up to 4 words, avoiding ending on "the", "of", "is"…"""
    n = len(words)
    best: list[tuple[int, list[list[dict]]]] = [(0, [])] + [(10**9, [])] * n
    for end in range(1, n + 1):
        for size in range(1, min(MAX_WORDS_PER_CHUNK + 1, end) + 1):
            prev_cost, prev_groups = best[end - size]
            group = words[end - size:end]
            cost = prev_cost + _chunk_cost(group)
            if cost < best[end][0]:
                best[end] = (cost, prev_groups + [group])
    return best[n][1]


def _manual_groups(captions: tuple[str, ...], words: list[dict]) -> list[list[dict]] | None:
    """Uses the breaks written in the script; if they do not match the narrated words, goes back to automatic."""
    sizes = [len(c.split()) for c in captions]
    if not sizes or sum(sizes) != len(words):
        return None
    groups, i = [], 0
    for size in sizes:
        groups.append(words[i:i + size])
        i += size
    return groups


def chunks(scene: Scene, meta: dict | None, total: float) -> list[Chunk]:
    if scene.lines and not scene.on_screen:
        result, t = [], 0.0
        # Scene slack (min_seconds greater than the reading time): goes to the sentence before the final question, which keeps the
        # normal card duration (gravity-doubled); without a final question, the slack stays on the last sentence.
        hold = max(0.0, total - sum(line_seconds(s) for s in scene.lines))
        closing = len(scene.lines) > 1 and "what should i imagine next" in scene.lines[-1].lower()
        for i, line in enumerate(scene.lines):
            end = total if i == len(scene.lines) - 1 else t + line_seconds(line) + (hold if closing and i == len(scene.lines) - 2 else 0.0)
            result.append(Chunk(line, round(t, 3), round(end, 3)))
            t = end
        return result
    if scene.on_screen or not meta or not meta.get("words"):
        return [Chunk(scene.caption_text, 0.0, total)]

    groups = _manual_groups(scene.captions, meta["words"]) or [
        g for part in _sentences(meta["words"]) for g in _split(part)]
    result = []
    for i, group in enumerate(groups):
        start = 0.0 if i == 0 else group[0]["start"]
        end = groups[i + 1][0]["start"] if i + 1 < len(groups) else total
        result.append(Chunk(" ".join(w["word"] for w in group), round(start, 3), round(end, 3)))
    return result
