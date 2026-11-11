# Procedure: Gemini Deep Research through the owner's Chrome

Use Gemini's Deep Research (the owner's Google AI Plus subscription) through the connected Chrome, **without the API**, to discover **candidate** sources. Verification remains the `fact-check` agent's job. Goal: reduce the tokens subagents spend searching; measure whether it pays off (see "Measurement").

## Rules that do not change
1. What comes back from Gemini is a **list of candidates, never a fact**. Every URL is actually opened and the literal excerpt is copied by `fact-check` ("open source" rule); a candidate whose URL does not open or whose excerpt does not exist is marked `[FALSE CANDIDATE]` and counted.
2. **Ask the owner before sending each prompt** to Gemini (it is an action on their account) and show the prompt. One search per video (the AI Plus daily quota is small).
3. Only the topic and the research questions go out; never credentials, personal data, private links, keys or unpublished script text.
4. Stop and ask the owner if a login, captcha, quota notice or unexpected page appears. Do not click "create account", "subscribe" or anything payment-related.
5. Search `docs/verified-sources.md` first: what was already verified needs no new candidate.

## Step by step (orchestrator, in the "research fronts" step of `new-video`)
1. Write the prompt (template below) with the topic, the central question and the fronts from `research-fronts.md`; show it to the owner and ask "send to Gemini?".
2. Tools: `ToolSearch` to load `mcp__claude-in-chrome__*` (a single call), `list_connected_browsers` (use the owner's Windows browser, the same one used for Studio), `tabs_context_mcp`, `tabs_create_mcp` (new tab).
3. Navigate to `https://gemini.google.com/app`; confirm from the screenshot that it is logged in as the owner (account with Google AI Plus).
4. Turn on Deep Research mode ("Tools" menu or the "Deep Research" button below the text box; labels may change: check the screenshot, not a fixed selector).
5. Paste the prompt and send. Gemini shows a **research plan** with a start button ("Start research"): if the plan strays from the request, edit or cancel; otherwise start.
6. Wait (3 to 15 min). Check with `wait` of up to 10 s at a time and a screenshot every ~2 min; do not loop. If it exceeds 20 min with no result, warn the owner.
7. Read the report from the page: `javascript_tool` with `document.querySelector('main').innerText` (or the answer container); `get_page_text` often fails on Google apps. If the text comes back truncated, scroll and join the `innerText` in steps.
8. Save the whole report in `research/<slug>/candidates.md` with the prompt used, the date, and a table: `#`, claim, cited URL, cited excerpt, front. Close the opened tab.
9. Hand `candidates.md` to the per-front `fact-check` agents (each receives only its own front's rows) with the order: "open each URL; literal excerpt; mark [FALSE CANDIDATE] if it does not open or the excerpt does not exist".
10. Record in `build/<slug>/progress.md` the line "Deep Research: N candidates, M verified, K false, fact-check tokens".

## Prompt template
```
Research task (use primary sources only: peer-reviewed papers, official agency pages, museum/institution pages, Guinness for records). Topic: <WHAT IF ... ?> (a 60-70 second science video, American audience, metric units).
Central question: <central question from premise.md>.
For each of these angles, find 4 to 8 sources and return a table with: claim, exact number with unit and scope (species/group, place, year), the exact sentence from the source (quoted), URL.
Angles: <fronts from research-fronts.md, one per line>.
Rules: do not summarize without a quote; if you cannot find the exact sentence, say "NOT FOUND"; prefer open-access pages; do not use Wikipedia as the only source; include records ("largest", "first", "only") with the source that states the record and its date; flag claims that experts disagree about.
Output: one table per angle, then a short list of "common myths" about the topic with the source that corrects each.
```

## Measurement (fill in on the next video; decides whether it becomes the default)
Record in `build/<slug>/progress.md` and in `research/video-history.md`:
- tokens spent by the research `fact-check` agents **with** candidates, against the ants video (reference: 6 fronts + consolidation ~ 600 thousand tokens);
- candidates received / verified / false (false rate > 10% = not worth it);
- sources from the `docs/verified-sources.md` bank that the research reused;
- wall-clock time until the candidates arrive.

## Known limits
- Small daily quota; the report can take a while; Google pages change labels.
- Deep Research likes Wikipedia and blogs: the "open primary source" rule cuts that out.
- Never send anything the owner has not seen first.
