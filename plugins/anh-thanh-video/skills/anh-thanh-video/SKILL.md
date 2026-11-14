---
name: anh-thanh-video
description: Turn photos into a video - a beat-synced photo edit (photos change on the beat with flash, pop, shake and snap-and-ease camera moves, like the "2 ảnh / 3 ảnh" templates but with any song the user owns and any number of photos), a gentle photo album (slow push toward faces, soft crossfades, title and captions), or a 2.5D "3D zoom" where near things move more than far things. Faces stay in frame, Vietnamese text done right, 9:16 / 16:9 / 1:1 / 4:5. Use for "biến ảnh thành video", "ghép ảnh thành video", "video ảnh theo nhạc", "photo slideshow", "mẫu capcut nhiều ảnh", "video kỷ niệm", "album ảnh cưới/gia đình", "ảnh 3D", product photo videos.
license: MIT
metadata:
  author: TheGentleMinh
  version: 0.1.0
  status: release candidate - tested on Windows 10
  homepage: https://thegentleminh.com/ky-nang/anh-thanh-video/
---

# Ảnh thành video (photos into a video)

You turn a folder of the user's photos into a video. Many users are Vietnamese: if they write in Vietnamese,
answer in plain, spoken Vietnamese. Scripts are in `scripts/`; run them with `python scripts/atv.py ...` from
this skill's folder (or give the full path). Everything the user makes goes in their own folder.

## Requirements and limits

Tell the user these before installing anything, and whenever a request needs something that is missing.
`python scripts/atv.py check` shows what is there.

- **Needs:** a paid Claude plan with Claude Code; ffmpeg; Python 3.10+ with `numpy`, `opencv-python`, `pillow`.
  The face model (OpenCV YuNet, MIT, about 230 KB) downloads once on first use; without internet, framing uses the
  middle of each photo.
- **3D move (optional):** `onnxruntime` (pip, about 15 MB) and the depth model (Depth Anything V2 Small, Apache-2.0,
  about 50 MB, downloaded once on first use).
- **GPU:** not needed. Everything runs on the CPU.
- **Speed (tested, 12-core desktop):** beat and album videos render at 22-35 frames a second at 1080p (a 30-second
  video in about 30-45 s); the 3D move is slower, 7-9 fps (a 30-second video in about 2 minutes). Stills take seconds.
- **OS tested:** Windows 10 (every command). macOS: not tested yet.
- **Limits:** photos only (no video clips). The beat finder needs a clear beat; ambient or free-tempo songs give
  uneven cuts (use album mode). Side-on or tiny faces may be missed by the face finder. The 3D move works best on
  photos with a clear foreground; busy group shots get a gentle depth push instead of a cut-out.
- **What turns off without it:** no onnxruntime → no 3D move (everything else works); no music → album mode with
  even timing and no sound.
- **Privacy:** everything runs on the user's computer; the only downloads are the two small models, once.

## Rules (always)

1. **Never change or move the user's photos or music.** Read them; write the video as a new file.
2. **Music must be theirs to use** (their own, bought, or from a library they pay for). Never download a trending
   song for them; if they ask, say why and suggest their own library or a royalty-free one.
3. **Stills first, then a low-res preview, then the full render.**
4. Ask before installing anything.

## Setup (first time only)

Run `python scripts/atv.py settings`. If it says **NOT saved yet**, ask these questions **one at a time**, in the
user's language; if it says **NOT finished**, ask only the ones it lists. Every question offers its options plus two more:
- **"Mình chưa chắc, giải thích giúp mình"** → explain in one or two plain sentences, then ask again.
- **"Cho mình xem hết để so sánh"** → `python scripts/atv.py sample <kind> <their photo folder> --music <their song>
  --out <their folder>/anh-thanh-video-mau/<kind>.mp4` (about 15-20 s per option; say so; the 3D option is slower).
  It uses their first 4 photos, low resolution, every option side by side, labelled. Show it, then ask again.

Save each answer right away: `python scripts/atv.py settings set <key>=<value>`. The answers live in
`anh-thanh-video.settings.json` in their folder, so setup never runs again unless they ask ("làm lại phần cài đặt"
→ `atv.py settings reset`, then ask again). A plan can still change anything for one video.

| # | Question (Vietnamese) | Options → value | key | sample kind |
|---|---|---|---|---|
| 1 | Video đăng ở đâu nhiều nhất? | TikTok / Reels / Shorts → `9:16` · YouTube ngang → `16:9` · Bài đăng vuông → `1:1` · Facebook/Instagram dọc → `4:5` | shape | `shape` |
| 2 | Bạn thích kiểu nào? | Ảnh đổi theo nhịp nhạc → `beat` · Album nhẹ nhàng → `album` | mode | `mode` |
| 3 | Máy quay chuyển động thế nào? | Tự chọn theo kiểu (giật theo nhịp / đẩy chậm) → `auto` · Giật theo nhịp → `snap` · Đẩy chậm → `kenburns` · 3D chiều sâu → `parallax` · Đứng yên → `none` | move | `move` |
| 4 | Mỗi lần đổi ảnh "đập" mạnh cỡ nào? (kiểu theo nhịp) | Mạnh (chớp, nảy, rung, nhiễu) → `manh` · Vừa → `vua` · Nhẹ → `nhe` · Không → `khong` | hits | `hits` |
| 5 | Chữ tiêu đề kiểu nào? | Chữ cao, gọn → `cao` · Chữ đậm → `dam` · Đậm vừa → `dam-vua` | font | `font` |
| 6 | Ảnh không vừa khung thì sao? | Tự động (cắt khi giữ được mặt mọi người) → `auto` · Luôn lấp đầy → `crop` · Luôn giữ cả ảnh, nền mờ → `blur` | fit | `fit` |

Explanations to give for "chưa chắc":
1. Mỗi nơi đăng có khung khác nhau; mình làm đúng khung và giữ chữ tránh chỗ nút bấm của app.
2. "Theo nhịp" hợp video vui, nhanh (đi chơi, sinh nhật); "album" hợp kỷ niệm, đám cưới, gia đình.
3. "3D chiều sâu" làm cảnh gần di chuyển nhiều hơn cảnh xa, như quay bằng máy thật, nhưng làm lâu hơn.
4. Chỉ áp dụng cho kiểu theo nhịp: chớp sáng, ảnh nảy lên, rung nhẹ, nhiễu màu ở mỗi lần đổi ảnh.
6. Ảnh ngang trong video dọc: "tự động" chỉ cắt khi mặt mọi người vẫn nằm trọn trong khung.

Sample notes: `move` shows snap, slow push, 3D and still; `auto` means snap in beat mode and slow push in album mode.
Text colour isn't part of setup: the first time the user asks for a title or captions, ask the colour (white is the
default) and save it with `settings set color=#ffd400`. If the user says "cứ làm đi" or "mặc định", run
`python scripts/atv.py settings defaults` and move on.

## Commands

```
python scripts/atv.py check                                   # what's installed
python scripts/atv.py beats song.mp3                          # tempo + beat times
python scripts/atv.py make plan.json --out out/video.mp4 --stills     # writes out/video.stills.png
python scripts/atv.py make plan.json --out out/video.mp4 --preview    # writes out/video.preview.mp4 (half size)
python scripts/atv.py make plan.json --out out/video.mp4              # full render
```
For a revision, give the new render a new name (`out/video-v2.mp4`) so the old one is kept.

## Plan file (you write it)

```json
{"photos": "photos/", "music": "music/song.mp3", "music_start": 0,
 "beats_per_photo": 2, "title": "Mùa hè 2026",
 "captions": {"IMG_0412.jpg": "Đà Lạt, tháng 6"}}
```

Fields left out come from the saved settings (`shape`, `mode`, `move`, `hits`, `font`, `color`, `fit`).

- `photos`: a folder (sorted by file name) or a list of files in the order you want. Phone photos are turned the
  right way up.
- `mode`:
  - `beat`: a cut every `beats_per_photo` beats (1 = fast, 2 = default, 4 = calm). On every cut: `hits` from
    `flash`, `pop`, `shake`, `glitch` (RGB split + harder shake, the "giật lag" look), or a preset name `manh` /
    `vua` / `nhe` / `khong` (`manh` = flash, pop, shake, glitch; `vua` = flash, pop, shake; `nhe` = pop;
    `khong` = none). To drop one effect, write the list without it (no shake: `"hits": ["flash", "pop"]`). Strong
    beats hit harder. `move`: `snap` (the camera snaps to a new framing on every beat,
    then glides: 运镜卡点), `kenburns` (slow push), `parallax`, `none`. Photos are cropped to fill the screen
    whenever every face fits.
  - `album`: `per_photo` seconds each (default 3.5), soft `crossfade` (0.6 s), slow push toward the faces; cuts are
    nudged onto the music's beats. A photo that doesn't fit the shape is shown whole over a blurred copy.
- `music_start`: where in the song to start (seconds). The video ends on a beat (beat mode) or fades out (album);
  the music is levelled to -14 LUFS (YouTube/TikTok loudness) with a two-pass measurement.
- `length` (seconds): loop the photos to fill this length.
- `title`: big text over the first 3 s, kept off faces, in capitals (`"title_upper": false` keeps it as typed);
  `captions`: one line per photo by file name, in a readable bold (`"caption_font"` to change it).
- `move: "parallax"` (2.5D / "3D zoom"): the depth of each photo is estimated and near things move more than far
  things. People get their own layer when they separate cleanly from the background (the background behind them is
  filled in); scenery, food and crowded shots get a smooth push where every pixel zooms by its depth.

## Example prompts

Copy-paste prompts (more with notes in `examples/prompts.md`):

- **One-line starter:** "Làm video từ ảnh trong thư mục anh/da-lat với bài nhac/vui.mp3."
  → setup questions (first time), stills, then a video where photos change on the beat.
- **Detailed brief:** "Làm video kỷ niệm đám cưới 60 giây từ thư mục anh-cuoi, kiểu album nhẹ nhàng, khung 16:9 cho
  YouTube, nhạc nhac/piano.mp3 từ giây 12, tiêu đề 'Lan & Huy · 2026', mỗi ảnh có chú thích theo tên địa điểm."
  → a gentle album with slow pushes toward faces, crossfades on the beat, the title kept off faces.
- **3D zoom:** "Làm 8 ảnh phong cảnh này thành video 3D chiều sâu, dọc cho TikTok." → each photo moves in depth.
- **Fast template look:** "Ảnh đổi mỗi nhịp, giật mạnh kiểu glitch, như mẫu CapCut 3 ảnh."
- **Compare:** "Cho mình xem các kiểu chuyển động để so sánh." → your own photos in every camera move, side by side.
- **Revision notes:** "Đổi ảnh chậm lại (4 nhịp một ảnh), bỏ hiệu ứng rung, tiêu đề màu vàng, bỏ ảnh số 5."
  → only those changes; new stills, then a new render (the old one is kept).

## If something goes wrong

This skill was built with Claude Code, so it may have bugs, and every computer is different. When a step fails,
or the user says the video came out wrong:
1. **Explain it plainly, in Vietnamese:** what failed and why, in one or two sentences. No raw stack traces unless asked.
2. **Read this skill and the script involved** (`scripts/atv.py` and the `atv_*.py` file). Run
   `python scripts/atv.py check` if something may be missing.
3. **Fix it and re-run**, writing a new output file. Never touch or move the user's photos or music, even while fixing.
4. If the cause was in this skill itself, say so and suggest reporting it so it's fixed for everyone:
   https://github.com/thegentleminh/thegentleminh-skills/issues

### Common failures

- **`No module named 'cv2'`:** `pip install opencv-python` (ask first).
- **Cuts don't follow the music:** the song has no clear beat (`atv.py beats song.mp3` shows the tempo); try
  `beats_per_photo` 4 or album mode.
- **Someone's head is cut off:** the face finder missed a side-on face; set `"fit": "blur"` for that video, or put the
  photo in a list with a better crop.
- **Title sits on a face:** shorter title, or a photo with more sky/space first.
- **3D move: a person looks torn or doubled:** a busy group photo; use `kenburns` for that video.
- **The face or depth model won't download:** no internet or a blocked site; framing falls back to the middle
  (faces), and the 3D move is off until the model can download.
- **No sound:** no `music` in the plan.

## Credits

- Face finding: [OpenCV YuNet](https://github.com/opencv/opencv_zoo) (MIT), downloaded on first use.
- Depth (3D move): [Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small) (Apache-2.0),
  ONNX build from onnx-community, downloaded on first use; run with [onnxruntime](https://onnxruntime.ai) (MIT).
- Fonts (SIL Open Font License 1.1, licence files in `fonts/`): Be Vietnam Pro, Anton.
- The beat finder is written from scratch in numpy (no extra library).
