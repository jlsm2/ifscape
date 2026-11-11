---
name: weekly-analytics
description: MANUAL call (only when the owner types /weekly-analytics). Reads Ifscape's analytics and new comments on the 3 platforms (YouTube Studio, TikTok Studio, Instagram), compares them with each video's hypothesis and writes research/<date>-analytics.md.
disable-model-invocation: true
---

# Weekly analytics

**Manual:** only runs when the owner calls `/weekly-analytics`. Do not trigger on your own or suggest it as a workflow step.

Read-only. The access method has already been worked out; do not spend rounds testing tools.

## Access
- **The owner's Chrome (Windows).** `list_connected_browsers`; a Linux "Browser" that shows up by itself is NOT the owner's (never click "Create channel"). If the Windows one does not appear, ask the owner to connect the extension. Load the `mcp__claude-in-chrome__*` tools with `ToolSearch` in a single call.
- **YouTube:** channel `<channel-id>`. Overview: `https://studio.youtube.com/channel/<channel-id>/analytics/tab-content/period-default`; per video: `https://studio.youtube.com/video/<video-id>/analytics/tab-interest_viewers/period-default` (a URL with `tab=overview` errors; use the hyphen). `get_page_text` fails in Studio: use `javascript_tool` with `document.querySelector('main').innerText`. Per-second retention of new Shorts takes up to 2 days.
- **YouTube comments:** `vidiq_video_comments` (`channelId`, `order: time`, `maxResult: 50`), no browser needed.
- **TikTok:** `tiktok.com/tiktokstudio/analytics` and `.../comment` (virtual list: scroll ~350 px and join the `innerText`); the retention curve is read by dragging the chart marker (% still watching).
- **Instagram:** `instagram.com/<handle>/reels/` (views in the grid) and `/reel/<id>/` for comments. No Insights.

## What to write (`research/<YYYY-MM-DD>-analytics.md`, local)
1. **Scoreboard** per video and platform (views, likes, comments, shares, followers); reading day (day 1, 3, 5, 7 after the post).
2. **TikTok retention** of the new videos: 3 s, 10 s, 30 s, 45 s, 60 s, end, average time; compare with the curve of the previous ones and with the **hypothesis** written in the video's `build/<slug>/progress.md` ("I changed X, expected Y"). Say whether it confirmed, refuted, or whether one cannot tell (sample of 1).
3. **Comments:** new topic requests (go to `research/topic-bank.md`, "New requests", with handle and platform; credit only in the post description); factual criticisms ("source?", "wrong") become a check by `fact-check`.
4. **Posting-time test** in progress (e.g. Instagram early morning vs. TikTok and YouTube at midday), if still valid.
5. One line per video in `research/video-history.md` and the hypothesis resolved in `build/<slug>/progress.md`.

## Rules
- Rates are correlation: with a small n, write "cannot tell".
- Never click anything that publishes, replies or changes; read-only (replying to comments is the owner's job).
- If Chrome does not respond in 2 attempts, stop and ask the owner; do not explore pages outside the script above.
