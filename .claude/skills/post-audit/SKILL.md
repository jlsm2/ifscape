---
name: post-audit
description: MANUAL call (only when the owner types /post-audit). Audits the facts of an already published Ifscape video (or several) with the viral-study rules and writes research/<date>-audit/<slug>.md; also serves to recheck sources that did not open.
disable-model-invocation: true
---

# Post-publication audit

**Manual:** only runs when the owner calls `/post-audit`. Do not trigger on your own or suggest it as a workflow step.

It was done by hand on the first 8 published videos (local research notes) and found a deadline stamp without a source in 4 of the 8. Here is the procedure to repeat it. A published video is only corrected for CRITICAL or on the owner's order; the rest becomes a line in `.claude/agents/lessons.md`.

## Steps
1. **Lint first (free):** `py -m ifscape lint scripts/<slug>.json`. The HIGHs already go into the report.
2. **One `fact-check` agent per video, in parallel, in a single message** (`Agent` with `subagent_type: "fact-check"`, `run_in_background`). Prompt: include the script, `facts.md` and `factcheck.md` if they exist, the 4-item test (group, place, year, magnitude) on every sentence with a number, stamps with a source that states the deadline, the post description, `post.txt` without internal notes, a primary source really opened (Chrome if blocked) and output only in `research/<date>-audit/<slug>.md`. Do not edit the script.
3. **Recheck in Chrome** the sources marked NOT OPENED (`fact-check` now has `ToolSearch` and the Chrome tools; if the owner's Chrome is not connected, the pages stay NOT OPENED and go to the owner).
4. **Summary** in `research/<date>-audit/SUMMARY.md`: a table per video (items, confirmed, partial, exaggerated, no source, maximum severity, public correction?), recurring patterns, pending items.
5. **Public correction** only for CRITICAL or if the owner orders it; the cheapest is the post description (the verb stronger than the video's) and, on TikTok/YouTube, a pinned comment. The owner edits the platforms.
6. **Lessons:** every new failure becomes a line in `lessons.md` (failure, who should have caught it, rule, bad → good) and the rule goes into the responsible agent.

## Cost and limit
- One `fact-check` per video costs ~70 to 100 thousand tokens (Sonnet); 8 videos in parallel took ~5 min.
- It is not a step of any video: only when the owner asks.
