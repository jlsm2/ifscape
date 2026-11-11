# Sound effects: diagnosis and plan (2026-10-21)

Request: the video needs immersive sound effects, like the viral ones. The first version (pure synthesis in FFmpeg, `ifscape/sfx.py`) came out "strange and out of place". This file keeps the plan for redoing it. **Not yet implemented at the time of writing.**

## What the viral videos do

Per-band energy analysis of the 8 downloaded videos (see `docs/covers.md` for the same set). The clearest pattern is in three of them (Viral C, Viral B and Viral G):

1. Before the event: full city ambience (high mids and highs: traffic, voices).
2. At the event: **low boom** and **cut to near silence**. That contrast is the main effect.
3. After: a few spot sounds at the strong moments and an era ambience rising (wind, rain, low hum).

## Why the synthesized version failed

The video QA measured the audio on 2026-10-21:

- **Bug:** in FFmpeg, `bandpass=f=...:w=...` reads `w` as a Q factor, not as a width in Hz. `w=900` became a band of nearly zero width. That is why wind, whoosh, crackles, city, water and the hit noise came out as **pure tones** at -55 to -50 dBFS (nearly inaudible). The fix would be `width_type=h`.
- **Only lows:** boom, drone, hum, powerdown, impact and rumble all sit below 150 Hz. On a phone speaker the video is nearly mute.
- **Too much sound:** there were 99 cues, with a tick on every number change. The viral videos use few sounds.
- **Out of time:**
  - the powerdown played 2.5 s before the visible blackout;
  - the water played 3 s before the stairs appeared;
  - the collapse boom came 0.2 s before the street gave way.
- The hits had a bell-like "ding" timbre.

Conclusion: pure synthesis does not come close to recorded or AI-generated sound. Change the source of the sounds.

## Chosen plan: Mixkit + ElevenLabs

| Source | For what | Cost | License |
| --- | --- | --- | --- |
| **Mixkit** (recorded sound) | The generic: city ambience, wind, stream, whoosh | Free | Commercial use without attribution, including in social media video ([Mixkit FAQ](https://mixkit.co/llm-info/)) |
| **ElevenLabs Sound Effects** (`POST /v1/sound-generation`, same key as the voice) | The specific, described in text: car hits, vanishing boom, blackout, water in the subway, collapse, tick | ~20 credits per second with a set duration; about 15 sounds of 1 to 4 s come to around 1,000 credits, once only (cached by text fingerprint, like the voice) ([cost](https://help.elevenlabs.io/hc/en-us/articles/25735337678481)) | Commercial use only on the paid plan (Starter or above): **confirm the plan first** |

Technical details already gathered:

- Mixkit files live at `https://assets.mixkit.co/active_storage/sfx/<id>/<id>-preview.mp3`. The id appears in the category page HTML (`data-audio-player-item-id-value`). Useful pages: `/free-sound-effects/city/`, `/wind/`, `/water/`, `/whoosh/`.
- In the city category there are candidates such as "Urban city ambience at night" (2:06), "City traffic background ambience" (1:07) and "Walking crowd at subway station loop".
- Keep the sounds in a library folder (e.g. `sfx/`) with a `library.json`: name -> source (Mixkit URL + license, or ElevenLabs prompt and duration). `sfx.py` loads files instead of synthesizing. The script cues (`sfx`, `ambience`, `sfx_traffic`) stay the same.

## New sound design (about 25 sounds instead of 99)

| Moment | Sound | Source |
| --- | --- | --- |
| 0 to 0.77 s | City at night (traffic, voices) | Mixkit |
| Vanishing (0.77 s) | Deep cinematic boom with a tail, and the ambience cuts | ElevenLabs |
| Hits (1.2 / 1.5 / 1.67 / 2.77 / 3.07 / 3.83 / 5.0 s) | Car hitting metal, at a distance, empty city | ElevenLabs (2 or 3 variations) |
| Population drop | Fast ticks (only here) | ElevenLabs or Mixkit (interface) |
| Time jumps (6) | Soft whoosh | Mixkit |
| Blackout (scene 04, `at` ~ 0.54, when the light drops) | Power grid shutting down | ElevenLabs |
| Subway flooding (scene 05, ~0.5 to 0.95, when the stairs appear) | Water rising and bubbling in a tunnel | ElevenLabs |
| Collapse (scene 07: rumble at 0.5, boom at ~0.61) | Asphalt and concrete crumbling | ElevenLabs |
| Stream (scene 08) | Calm stream | Mixkit |
| 500 and 10,000 years | Soft wind in the forest | Mixkit |
| End card | Short rise and low impact | ElevenLabs |

Rules to avoid repeating the mistakes:

- Every sound needs energy between 200 Hz and 4 kHz (phone without bass).
- Check peak and band of each file before mixing.
- Mix in batches (a single `amix` with ~100 inputs hangs FFmpeg 9).
- Panel ticks only on the `counter`, never on the scrolls.
- Final volume: -20 LUFS if the platform's music goes on top; -16 if the video is posted without music.

## Other adjustments from the same QA (text, not sound)

- On the end card, the panel and the old phrase stay ~0.4 s on top of the card: erase them before the card enters.
- The panel at y = 860 covers the pot (scene 09) and touches the statue's face at the end (scene 12): hide it in those stretches or change its position per scene.
- The scene 10 sentence enters ~0.8 s before the forest appears.

## Review of 2026-10-21 (afternoon): volume, silences and music of the viral videos

Measurement (EBU R128) of `out/humans-vanished.mp4` and the 8 downloaded viral videos:

| Video | LUFS | LRA |
| --- | --- | --- |
| humans-vanished (before) | -24.2 | 16.4 |
| Viral D | -12.9 | 16.7 |
| Viral A | -14.0 | 18.3 |
| Viral G | -14.3 | 12.5 |
| Viral E | -14.7 | 4.6 |
| Viral B | -16.2 | 5.9 |
| Viral C (16.1M) | -16.6 | 13.4 |
| Viral C (12.3M) | -18.5 | 17.5 |
| Viral F | -23.1 | 9.1 |

- **Music:** all 8 use "original sound" on TikTok (yt-dlp metadata), meaning the audio comes ready in the file, with no platform library music. The spectrograms show almost no melody: what exists is a **continuous background** (rain, wind, birds, city) and, in Viral C and Viral F, a **sustained low drone**. None is in total silence.
- **Problems with ours:**
  - digital silence at 6 to 8.7 s, 10.6 to 15.5 s and 17 to 18.7 s, with the city still lit;
  - hits about 19 dB above the background, so impacts sounded loud even with the video quiet overall;
  - scene 06 cracks with no sound;
  - subway water entering 3 s after it starts rising.
- **Fix:**
  - continuous drone (Mixkit 2510, "Cinematic suspense ambience", repeated with a 3 s crossfade) from the vanishing to the end card;
  - hum of the powered city (ElevenLabs) from the vanishing to the blackout, dying with the lights;
  - cracks (ElevenLabs) at 06 0.16 and 06 0.5;
  - water at 05 0.3;
  - bus compression, two-pass volume to -16 LUFS and a limiter at 4x the rate (true peak -1.8 dBFS after AAC).
- **Result:** -16.1 LUFS, LRA 5.1 and no silent stretch. Post **without platform music**, like the viral videos. If music is wanted, keep it very low in the app.
