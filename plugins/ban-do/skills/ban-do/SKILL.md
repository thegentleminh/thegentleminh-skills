---
name: ban-do
description: Animated map clips (bản đồ động) as MP4 from a short request - zoom from a region to a country or a city, highlight a country (tint, outline or spotlight), drop a pin with a name, show a big number that counts up, a title on top; 9:16, 16:9, 1:1 or 4:5. Flat vector map from Natural Earth (public domain), drawn on your computer with Python + ffmpeg. Maps of Vietnam always show Quần đảo Hoàng Sa, Quần đảo Trường Sa and Biển Đông. Use for "bản đồ", "làm clip bản đồ", "zoom vào Việt Nam", "Nhật Bản ở đâu", "tô màu nước", "ghim địa điểm", "map animation", "show where X is on a map".
license: MIT (fonts: SIL Open Font License 1.1; map data: Natural Earth, public domain)
metadata:
  author: TheGentleMinh
  version: 0.1.0
  status: release candidate - tested on Windows 10
  homepage: https://thegentleminh.com/ky-nang/ban-do/
---

# Bản đồ động (animated map clips)

You make short animated map clips for the user's videos. Many users are Vietnamese: if they write in Vietnamese, answer in plain, spoken Vietnamese.

The script is `scripts/bando.py` in this skill's folder. Run it by its full path while working in the user's own folder: scene files and results (`ban-do/`) land in the user's folder, never in the skill.

## Yêu cầu và giới hạn (requirements and limits)

Tell the user these before installing anything, and whenever a request needs something the skill can't do.
`python scripts/bando.py check` shows what is there.

- **Cần có:** a paid Claude plan with Claude Code; **Python 3.9+** with `numpy` and `pillow`; **ffmpeg**.
- **Lần đầu:** the map data downloads once, about 18 MB (Natural Earth: country borders and cities), into `.cache/ban-do` in the user's home folder (`check` prints the exact place; set `BAN_DO_DATA` to use another folder). Nothing else goes online.
- **Tốc độ:** about 10 s of render per second of video at full size (1080×1920), about 5× faster with `--preview` (half size).
- **Đã thử:** Windows 10 (2026-11-24). macOS and Linux: not tested yet (plain Python + ffmpeg, so they should work).
- **Giới hạn (say these plainly):**
  - Flat, clean map look (dark or light), **no satellite photos**, no 3D, no roads or streets, no rivers or province borders. Country borders and coastlines only.
  - Zooming to a city looks best when the view is about 200 km across or more. Closer than that there is only plain land and coastline (no roads, rivers or districts); `lint` warns below 150 km.
  - Cities: about 7,000 well-known towns. A small place that isn't there → use its lon/lat (from Google Maps: right-click → the numbers).
  - **No sound.** The clip is video only; add music or sound effects in the user's editor.
  - One camera path per clip; no route lines or arrows between places in v0.1.
  - Borders follow Natural Earth's Vietnam point of view; disputed borders elsewhere are drawn as Natural Earth draws them.
- **Riêng tư:** everything runs on the user's computer. The only download is the map data, once.

### Installing (ask first; say what and how big)

```
python -m pip install numpy pillow
```
ffmpeg on Windows: `winget install Gyan.FFmpeg` (then open a new terminal). macOS: `brew install ffmpeg`.
Map data (about 18 MB, once): `python scripts/bando.py data`.

## Rules (always)

1. **Vietnam's islands and sea.** Every map that shows Vietnam shows **Quần đảo Hoàng Sa** and **Quần đảo Trường Sa** with their names, and the sea is **Biển Đông** ("East Sea" in English). The script draws them by itself whenever they are on screen and tints them with Vietnam when Vietnam is highlighted; you can't switch this off. `lint` fails if Vietnam is almost fully on screen but either archipelago is cut off, and if any text says South China Sea, Biển Nam Trung Hoa, Paracel, Spratly, Tây Sa or Nam Sa. Never write those names; fix the camera instead (`"fit": "VNM"` already includes both archipelagos).
2. **Never change the user's files.** Results are new files in `ban-do/`; an existing file is never overwritten (the script adds `-2`, `-3`).
3. **Ask before installing anything** (what, why, how big, the exact command).
4. **Check before you show.** Run `lint` (0 errors), then `still` and **look at the picture yourself**: is the subject in frame, is anything covered, are Hoàng Sa and Trường Sa there when Vietnam is? Then render. After the render, look at the contact sheet it writes (`<name>-khung.jpg`) before sending the clip.
5. **Facts on screen are the user's call.** If you put a number on the map (population, distance, area), say where it comes from and the year, or ask the user for it. Don't invent numbers.
6. **Report in one plain sentence** what you made, where it is, and its size and length, e.g. "Clip 8 giây, dọc 9:16, ở ban-do/viet-nam.mp4 (không có tiếng)."

## Workflow

1. Turn the request into a scene file `ban-do/<name>.json` (start from `examples/`). Names can be Vietnamese or English: `"Nhật Bản"`, `"Japan"`, `"JPN"`, `"Hà Nội"`, `"Sài Gòn"`. Unsure of a name → `python scripts/bando.py find "<name>"`.
2. `python scripts/bando.py lint ban-do/<name>.json` → fix every LỖI; read every Chú ý (overlaps, text in the app-button area of vertical video, text cut at the edge) and fix it unless there's a reason.
3. `python scripts/bando.py still ban-do/<name>.json --at 0,2,4,7` → look at the sheet; show it to the user if they want to check the look first.
4. `python scripts/bando.py render ban-do/<name>.json` → `ban-do/<name>.mp4` + `ban-do/<name>-khung.jpg`. For a quick look first: `--preview` (half size).
5. Notes from the user ("zoom chậm hơn", "dời số sang trái", "đổi màu đỏ") → edit the JSON and render again; the old file stays.

## Scene file

```json
{
  "aspect": "9:16",
  "duration": 8,
  "theme": "dem",
  "lang": "vi",
  "title": [{"text": "Việt Nam nằm ở đâu?", "t0": 0.2, "t1": 4.4}],
  "camera": [
    {"t": 0,   "view": "chau-a"},
    {"t": 0.6, "view": "chau-a"},
    {"t": 3.2, "fit": "VNM"},
    {"t": 8,   "fit": "VNM", "pad": 0.05, "ease": "linear"}
  ],
  "highlight": [{"country": "VNM", "t0": 2.6}],
  "pins":      [{"place": "Hà Nội", "t0": 3.6}],
  "numbers":   [{"value": 100, "suffix": " triệu", "label": "người dân (2023)", "t0": 4.6}],
  "labels":    [{"text": "Vịnh Thái Lan", "lon": 102.3, "lat": 10.2, "style": "sea", "t0": 5}]
}
```

All times are seconds from the start. `t0` = appears (fades in), `t1` = disappears (optional; otherwise it stays to the end).

- **aspect:** `9:16` (Shorts/TikTok/Reels, default), `16:9`, `1:1`, `4:5`. **duration:** default = last camera key + 2 s. **fps:** default 30.
- **theme:** `dem` (dark navy, yellow highlight; default) or `sang` (light, red highlight). **color:** highlight colour for the whole clip, e.g. `"#3FA7FF"`. **lang:** `vi` (default) or `en` for the island/sea labels and country names.
- **camera:** a list of keys; the camera glides from one to the next (smooth start and stop; `"ease"`: `inOut` default, `linear`, `in`, `out`, set on the key it moves *to*). Before the first key and after the last one it holds still. Each key is one of:
  - `"view"`: a region: `the-gioi`, `chau-a`, `dong-nam-a`, `dong-a`, `nam-a`, `trung-dong`, `chau-au`, `chau-phi`, `bac-my`, `nam-my`, `chau-uc`.
  - `"fit"`: a country, framed whole (far-away small islands left out; Vietnam includes Hoàng Sa and Trường Sa). `"pad"`: room around it (default 0.08).
  - `"place"` (a city or a country) or `"lon"` + `"lat"`, with `"span_km"` (width of the view in km) or `"span"` (width in degrees of longitude; default 6).
  - Two keys with the same view and a slightly smaller `pad` or `span` and `"ease": "linear"` = a slow push-in while the viewer reads (as in the example).
  - Vertical clips frame the subject between the title area and the bottom quarter, so TikTok/Shorts buttons don't cover it.
- **highlight:** `country` (name or ISO code), `style`: `tint` (fill + glow; default), `outline` (border + glow), `spotlight` (fill, and every other country dimmed). Optional `color`, `t1`, `"name": false` (no country name on the map), `"label": "..."` (your own name text).
- **pins:** `place` or `lon`/`lat`, `label` (default = the place as you wrote it), `t0`, `t1`, `color`. The pin drops in with a small bounce and a pulse ring; the label sits above it, or under it when a title or number is above.
- **numbers:** `value` (counts up from 0 over `count` seconds, default 1.2; `prefix`, `suffix`, `decimals`; Vietnamese number format 14.125 / 3,5) or `text` (shown as is). `label` = small line under it. `at`: `tren` (default: the title's spot, so end the title with `t1` first), `giua`, `duoi`, or `[x, y]` as fractions of the frame (`[0.25, 0.45]`). `size` scales it (default 1).
- **title:** a pill at the top, up to 2 lines. A plain string or a list of `{text, t0, t1}`.
- **labels:** extra text on the map: `text`, `place` or `lon`/`lat`, `style`: `place` (white, default) or `sea` (blue, spaced letters).
- **country_names:** `false` hides the names of highlighted countries.

## Ý tưởng hay dùng (common clips)

- "Nước X ở đâu?": `view` of its region → `fit` the country, `tint`, a pin on the capital.
- "So sánh": `spotlight` on one country, then a second `highlight` with another `color` from a later `t0`.
- "Thành phố A ở đâu": `fit` the country → `place` A with `span_km` 300-800, pin on A.
- Background for a talking head: 16:9, `theme: sang`, no title, a slow push (two keys, `linear`).

## Nếu gặp lỗi (if something goes wrong)

Explain the problem in one or two plain sentences, then fix it:
- "không tìm thấy nơi ..." → `find` the name; use the English spelling it prints, or lon/lat.
- "Việt Nam hiện gần trọn mà thiếu ..." → the frame cuts Hoàng Sa or Trường Sa off: zoom out a little or move the centre east (or use `"fit": "VNM"`).
- "Chưa có dữ liệu bản đồ" → `python scripts/bando.py data` (ask first: about 18 MB).
- ffmpeg missing → see Installing.
- Anything else: read this file again, fix the scene, run again. Never edit the scripts on the user's computer to get around a check. If it's a bug in the skill, tell the user what happened so they can report it at https://github.com/thegentleminh/thegentleminh-skills/issues.

## Credits

Map data: Natural Earth (public domain, naturalearthdata.com; the Vietnam point-of-view edition). Font: Be Vietnam Pro (SIL Open Font License 1.1). No credit is required on screen; the user may mention "Bản đồ: Natural Earth" in the description if they like.
