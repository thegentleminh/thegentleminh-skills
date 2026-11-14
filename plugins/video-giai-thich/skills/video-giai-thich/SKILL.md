---
name: video-giai-thich
description: Make a Vietnamese animated explainer video (9:16, TikTok / Reels / Shorts) from a topic or a question - "vì sao bầu trời màu xanh?", "lãi kép là gì?" - with a spoken-Vietnamese script, a voice (ElevenLabs, your own recording, or none), on-screen words that appear as they are spoken, and pictures animated in code and timed to the words. Five looks (riso print, chalkboard, newsprint, blueprint, poster). Use for "làm video giải thích", "video kiến thức", "video khoa học", "giải thích bằng hoạt hình", "explainer video in Vietnamese", "vibe coding animation", "video kiểu Vibe知识".
license: MIT
metadata:
  author: TheGentleMinh
  version: 0.1.0
  status: release candidate - tested on Windows 10 (install from a clean copy, fresh-user run)
  homepage: https://thegentleminh.com/ky-nang/video-giai-thich/
  renders-with: HyperFrames (Apache-2.0, https://github.com/heygen-com/hyperframes)
---

# Video giải thích (Vietnamese animated explainers)

You make short explainer videos in Vietnamese: a script, a voice, and animated pictures written as code
and rendered with HyperFrames. Answer in plain, spoken Vietnamese when the user writes in Vietnamese.

Scripts live in `scripts/`; run them with `python scripts/<file>.py` from this skill's folder
(or give the full path). The user's videos go in their own folder, never inside the skill.

## Requirements and limits

Tell the user these before installing anything, and whenever a request needs something that is missing.
`python scripts/vgt.py doctor` checks all of it.

- **Needs:** a paid Claude plan with Claude Code; Python 3.10+ with `fonttools`; ffmpeg; Node.js 20+. The first
  render downloads HyperFrames and a headless Chrome (a few hundred MB, once). Internet is needed while rendering
  (the animation library loads from a CDN).
- **Voice (optional):** an ElevenLabs account and API key (paid, about 1 credit per character; a 45-second script is
  about 700 credits), or the user's own recording plus `faster-whisper` (free, a few hundred MB once), or no voice.
- **GPU:** not needed. An NVIDIA card makes Whisper (own-recording timing) faster.
- **Speed (tested):** a 48-second video renders in about 1 minute on a desktop (12-core CPU, RTX 4080); expect 2-4×
  longer on a laptop. The five-look comparison takes about 3 minutes.
- **OS tested:** Windows 10 (every command). macOS: not tested yet.
- **Limits:** 9:16 only for now (no 16:9). Pictures are drawn in code by Claude for each video (shapes, diagrams,
  icons), not photos or stock footage, so check the stills. ElevenLabs voices can drift in accent on some words:
  listen before rendering. Whisper mishears Southern accents (sóng → sống), but timing is matched to the script, so
  the words on screen are always the script's.
- **What turns off without it:** no ElevenLabs key → own recording or no voice; no faster-whisper → ElevenLabs or no
  voice; no music file → no music.
- **Privacy:** HyperFrames sends anonymous usage counts; turn them off with `npx hyperframes telemetry disable`.
  ElevenLabs receives the script text. Nothing else leaves the computer.

## Rules (always)

1. **Facts first.** Check every claim in the script; if you aren't sure of a number, say so or leave it out.
   Show your sources to the user with the script.
2. **Spoken Vietnamese, not translated English.** Short sentences, everyday words, the way people talk.
   Before any voice is made, show the user the lines that might sound translated and offer a plainer version.
3. **Numbers:** write `{6|sáu}` so the screen shows "6" and the voice says "sáu".
4. **Music and voices must be theirs to use**: their own, bought, or royalty-free. Never download a trending song.
5. **Stills first, then the full render.** Never send a render you haven't looked at.
6. **ElevenLabs costs credits.** Say roughly how many (about 1 per character) before every voice take or audition.
7. Ask before installing anything.

## Setup (first time only)

Run `python scripts/vgt.py settings`. If it says **NOT saved yet**, ask these questions **one at a time**,
in the user's language. Every question offers its options plus:
- **"Mình chưa rõ, giải thích giúp"** → explain each option in a sentence or two, then ask again.
- **"Cho xem hết để so sánh"** → show the comparison listed in the table, then ask again.

Save each answer right away: `python scripts/vgt.py settings set <key>=<value>`. Answers live in
`video-giai-thich.settings.json` in the user's folder, so setup never runs again unless they ask
("làm lại phần cài đặt" → `vgt.py settings reset`, then ask again). They can still change anything for one video.

| # | Ask (Vietnamese) | Options → saved value | "Cho xem hết" shows |
|---|---|---|---|
| 1 | Bạn muốn video theo kiểu nào? | In riso `in-riso` · Bảng phấn `bang-phan` · Báo giấy `bao-giay` · Bản vẽ `ban-ve` · Poster `poster` | `vgt.py sample` of a demo project: the same 8 s in all five looks, side by side |
| 2 | Ai đọc lời? | Giọng ElevenLabs `elevenlabs` · Bạn tự thu `own` · Không giọng, chỉ có chữ `none` (nhạc tuỳ câu 4; không nhạc thì video im lặng) | for ElevenLabs: `vgt_voice.py audition` of 2-3 Vietnamese voices (ask about credits first) |
| 3 | Chữ hiện ra thế nào? | Từng chữ theo giọng `word` · Cả câu một lúc `sentence` | `vgt.py sample --var reveal --values word,sentence` |
| 4 | Có nhạc nền không? | Không `none` · Nhạc của bạn `own` (+ `music_file=<path>`) | explain: music sits about 16 dB under the voice and dips further while it speaks |
| 5 | Video thường dài bao nhiêu? | Ngắn 30-60 giây `short` · Dài 1-3 phút `long` | explain: short = one idea for TikTok/Reels/Shorts; long = a full explanation (Douyin and YouTube favour longer videos) |
| 6 | Giọng văn thế nào? | Thân mật `than-mat` · Chuẩn mực `chuan` · Vui nhộn `vui` | write the same two opening lines in all three tones |
| 7 | Có hiện tên kênh nhỏ ở trên không? | Không (empty) · Có → `handle=@tenkenh` | a still with and without |

For ElevenLabs also save `voice_id` (default: Triệu Dương `UsgbMVmY3U59ijwK5mdh`, a Southern voice from the
public library). The user needs their own key in the `ELEVENLABS_API_KEY` environment variable.

## Making a video

1. **Script.** Agree the topic and the one question the video answers. Write `script.txt` (format below) in the
   saved tone and length: hook in the first sentence, one idea per scene, the answer at the end. Show it with sources
   and the possibly-translated lines; wait for their OK.
2. **Project.** `python scripts/vgt.py new <folder>` (copies the looks and runtime; uses the saved settings), then put
   the agreed `script.txt` in it.
3. **Voice / timing** (writes `voice/voice.json`, and `voice/voice.wav` when there is a voice):
   - ElevenLabs: `python scripts/vgt_voice.py tts <folder>/script.txt --voice <voice_id> --out <folder>/voice`
   - Own recording: they record the script (phone is fine); `python scripts/vgt_voice.py align <folder>/script.txt <recording> --out <folder>/voice`
   - No voice: `python scripts/vgt_voice.py silent <folder>/script.txt --out <folder>/voice`
4. **Sync.** `python scripts/vgt.py sync <folder>`: sets every scene's start and length from the voice and writes the
   word timings the pictures use.
5. **Scenes.** In `<folder>/index.html`, one `<section id="sN" class="scene clip">` per script line (same ids as
   `script.txt`). Draw each picture inside a `<div class="art">` or `<svg class="art" viewBox="0 0 1080 680">`: the
   box sits at y 600-1280 of the frame, and coordinates inside it are local (0-1080 × 0-680). The sentence band at the
   top is filled automatically from the script. Animate inside the template's
   `vgtStart((tl) => { ...your tweens... }, (tl) => { window.__timelines["main"] = tl; ... })` (keep the second
   function as the template has it), timing every move to the words: `W("s2", "cầu")` = when "cầu" is said in scene
   s2 (`W("s6", "không", 2)` = the second time); `T("s2", 0.5)` = 0.5 s into scene s2. Colours and fonts only through
   the look tokens (`var(--ink)`, `var(--c1)`, `var(--accent)`; see `looks/README.md`), so every look works.
6. **Check.** `python scripts/vgt.py check <folder>` (HyperFrames' own check at the pinned version; it hides the
   warnings every project of this skill gets) must show 0 errors. Then `python scripts/vgt.py stills <folder> --at <times>`
   (one time per scene, in the project's look) and look at every frame, especially the longest sentence.
7. **Render.** `python scripts/vgt.py render <folder> --out <folder>/out/video.mp4 [--music <file>]` (add
   `--look <look>` to render another look): the final audio is mono at -14 LUFS (YouTube/TikTok loudness). With no
   voice and no music the video is silent; the command says so.

## Script format

```
[s1] Ánh nắng mặt trời là ánh sáng *trắng.* / Vậy sao bầu trời lại màu *xanh?*
[s4] Màu xanh bị dội gần *gấp {6|sáu} lần* màu đỏ, mất dọc_đường.
```
- `[id]` starts a scene (one picture idea). ` / ` splits it into sentences shown one after another.
- `*words*` = highlighted words; a highlighted phrase never breaks across lines. Punctuation may sit inside or
  outside the closing star (`*diệp_lục,*` or `*diệp_lục*,`).
- `dọc_đường` = keep words together on one line (Vietnamese compounds read badly when split).
- `{shown|spoken}` = different text on screen and in the voice (numbers, abbreviations).

## Scene rules

- Frames must be reproducible: no `Math.random()` (use a seeded generator), no clocks, no network.
- Never tween `visibility`/`display` of a `.clip`; animate its children.
- An SVG `<g>` (or shape) that already has a `transform` attribute loses it when you tween `x`, `y`, `scale` or
  `rotation` on it: wrap it in another `<g>` and tween the wrapper.
- Keep key content out of the bottom third (the apps' buttons and caption sit there) and inside x 54-918.
- Give each scene a picture that moves on its key word; avoid generic floating shapes (viewers call that "AI look").

## Example prompts

Copy-paste prompts (more with notes in `examples/prompts.md`):

- **One-line starter:** "Làm cho mình một video giải thích ngắn: Vì sao bầu trời màu xanh?"
  → setup questions (first time), a script with sources to approve, then a 40-50 s 9:16 video.
- **Detailed brief:** "Làm video giải thích 45 giây về lãi kép cho người mới đi làm. Giọng thân mật, kiểu Bảng phấn,
  giọng đọc ElevenLabs Triệu Dương. Mở bằng một câu hỏi bất ngờ, có một ví dụ bằng tiền thật (gửi 1 triệu mỗi tháng),
  kết bằng một câu dễ nhớ."
  → a script built around one worked example, a chalkboard video with a growing bar chart timed to the voice.
- **No voice:** "Làm video chỉ có chữ và nhạc (nhạc của mình ở D:/nhac/nhe-nhang.mp3) giải thích vì sao lá cây đổi màu."
  → sentences timed for reading, your music under it, levelled for TikTok.
- **Own voice:** "Mình đã thu giọng đọc kịch bản ở D:/thu-am/la-cay.m4a, làm video theo giọng này."
  → timings matched from your recording; the words on screen follow the script.
- **Compare looks:** "Cho mình xem video này ở cả 5 kiểu để chọn." → an 8-second side-by-side of all five looks.
- **Revision notes:** "Cảnh 3 chữ to quá, đổi 'sóng' thành 'bước sóng', cầu vồng hiện chậm lại, và đổi sang kiểu Poster."
  → only those changes; new stills to check, then a new render (the old one is kept).

## If something goes wrong

This skill was built with Claude Code, so it may have bugs, and every computer is different. When a step fails, or
the user says the video came out wrong:
1. **Explain it plainly, in Vietnamese:** what failed and why, in one or two sentences. No raw stack traces unless asked.
2. **Read this skill and the script or file involved** (`scripts/`, `runtime/vgt-runtime.js`, the project's
   `index.html`). Run `python scripts/vgt.py doctor` if something may be missing.
3. **Fix it and re-run.** Write new files (a new render name); never touch the user's recordings, music or photos.
4. If the cause was in this skill itself, say so and suggest reporting it so it's fixed for everyone:
   https://github.com/thegentleminh/thegentleminh-skills/issues

### Common failures

- **Every frame is frozen at the start, no error:** a scene threw an error or the timeline never registered. Look for
  "video-giai-thich: scene code failed" (open `index.html` in a browser, check the console). `W()` throws when a word
  isn't in that scene: check the spelling against `script.txt`. Never return the GSAP timeline from a promise
  (it is "thenable"); use `vgtStart(scenes, register)` as in the template.
- **`voice.json doesn't match script.txt`:** the script changed after the voice was made. Re-run the voice step
  (or `silent`), then `sync`.
- **Words appear early or late:** re-run `sync` after any voice change; with your own recording, check the
  "Whisper matched N %" line (under 80 % means the recording differs from the script).
- **A letter looks different from the rest:** the font lacks it. `python scripts/vgt_fonts.py <font.ttf>`.
- **Accents of two lines touch:** in all-capitals looks raise `--say-lh` (see `looks/README.md`).
- **`ElevenLabs said 401`:** the key is wrong or missing; `ElevenLabs said 402/quota`: out of credits.
- **`HyperFrames failed: render`:** run `python scripts/vgt.py check <folder>`; fix the first error it lists.
- **A shape jumps to the corner when it starts moving:** it had a `transform` attribute; tween a wrapping `<g>` instead.
- **The rest of a sentence is highlighted:** a `*` is missing; every highlight needs an opening and a closing star.
- **No sound:** the video had no voice and no `--music`; or the `<audio id="vgt-voice">` tag was removed (re-run `sync`).

## Credits

- Rendering: [HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0), run through `npx`; not bundled.
- Animation: [GSAP](https://gsap.com) (free "no charge" licence), loaded from a CDN; not bundled.
- Fonts (SIL Open Font License 1.1, licence files in `looks/fonts/`): Be Vietnam Pro, Anton, Pangolin, Playfair Display,
  Chakra Petch, Space Mono.
- Optional: [ElevenLabs](https://elevenlabs.io) voices (the user's own account), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT).
