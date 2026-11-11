# Viral covers (2026-10-21)

I downloaded the chosen cover (the TikTok "cover", via yt-dlp) of 8 viral videos in the niche and compared each one with frames from its own video (mean grayscale difference, 10 frames per second).

| Account (plays) | Cover | Closest frame |
| --- | --- | --- |
| Viral A (28.4M) | Poster: small "WHAT IF THE EARTH", giant "Stopped" with a warm glow, "spinning?" | None (difference 33) |
| Viral B (22.8M) | Hook frame with the question and an icon | ~2 s |
| Viral C (16.1M) | Opening frame: question, icon and a panel with a count | exactly 0 s |
| Viral C (12.3M) | Opening frame: question and panel | exactly 0 s |
| Viral D (11.6M) | End frame with the panel ("Year 2,955") | exactly 87 s |
| Viral E (8.8M) | Poster: small "WHAT IF ALL", giant golden "Humans", "disappeared?" | None (difference 15) |
| Viral F (7.8M) | Poster: small "WHAT IF", giant "Gravity", rest in italics and the channel name | None (difference 40) |
| Viral G (4.5M) | Opening frame with the panel | exactly 0 s |

Conclusions:

- **5 of 8 use a frame from the video itself, 3 of them frame 0.** So the question and the panel must be on screen already at frame 0, and a strong hook frame works as a cover (idea: keep the question prominent for a few seconds while the set moves).
- **3 of 8 are posters:** a full-screen frame (never split), a small spaced-out "WHAT IF", one huge keyword with a warm glow and the rest of the question smaller, in the top third.
- In Ifscape: `python -m ifscape cover` builds the poster with the Instrument identity (Barlow, keyword in amber). First cover: `out/humans-vanished.cover.jpg`, a 1.45 s frame (people turning into sparks and cars crashing).
- Note: in `humans-vanished` the question fades in, so frame 0 comes out without it. For a frame-based cover, pick ~0.3 s.
