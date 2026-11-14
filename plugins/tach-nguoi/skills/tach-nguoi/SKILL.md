---
name: tach-nguoi
description: Person cut-out effects on your own clip - big text BEHIND the person (chữ sau lưng người), a freeze-frame character intro with a name card, freeze snap / comic freeze, and clones (phân thân, one take or two). Vietnamese text done right, placed automatically so it stays readable, inside each app's safe area, 9:16 or 16:9. Use when the user wants "text behind me", "chữ sau lưng", "chữ xuyên người", "giới thiệu nhân vật", "dừng hình", "freeze frame", "phân thân", "clone", or other cut-out effects on their own video.
license: MIT (scripts/rvm_matte.py is GPL-3.0)
metadata:
  author: TheGentleMinh
  version: 0.1.0
  status: release candidate - tested on Windows 10 with an RTX 4080
  homepage: https://thegentleminh.com/ky-nang/tach-nguoi/
---

# Hiệu ứng tách người (person cut-out effects)

You help a creator put effects around the person in their own video. Many users are Vietnamese: if they write in Vietnamese, answer in plain, spoken Vietnamese.

Scripts are in this skill's `scripts/` folder. Run them by their full path (or from the skill's folder) while working in the user's own folder: the settings file and every output land in the user's folder, never in the skill.

## Requirements and limits

Tell the user these before installing anything, and whenever a request needs something that is missing.
`python scripts/tn.py check` shows what is there.

- **Needs:** a paid Claude plan with Claude Code; ffmpeg; Python 3.10+ with `numpy`, `opencv-python`, `pillow`.
  The cut-out needs **PyTorch** (about 2-3 GB, best in its own Python environment) and the RVM model, which
  PyTorch downloads once from GitHub on the first cut-out (about 15-100 MB).
- **GPU:** an NVIDIA card is strongly recommended. With one, the cut-out runs at about 35-50 frames a second; on the
  CPU it is roughly 20-50× slower (a 30-second clip can take 10-20 minutes). Every effect works either way.
- **Speed (tested, RTX 4080):** stills in seconds; full renders at 1080p run 18-27 fps for text behind and clones and
  9-19 fps for freeze effects (a 20-second clip in about 1-2 minutes, after the one-time cut-out).
- **OS tested:** Windows 10 (every command). macOS: not tested yet (no NVIDIA GPU there, so the cut-out is slow).
- **Limits:** works best with one or two people and room above or beside the head. Tight vertical close-ups get small
  text. Fast motion, hair against a busy background and see-through objects make rough edges. Clones need a tripod
  or a nearly still camera. Two-take clones need both takes from the same spot.
- **What turns off without it:** without PyTorch, no effect can run (every effect needs the cut-out). Say so and offer
  the install (ask first).
- **Privacy:** everything runs on the user's computer; the only download is the RVM model, once.

### Installing PyTorch (ask first; say it is about 2-3 GB)

In a separate environment, so it can't break other Python tools:
```
python -m venv tach-nguoi-env
tach-nguoi-env/Scripts/python -m pip install numpy opencv-python pillow      (macOS/Linux: tach-nguoi-env/bin/python)
tach-nguoi-env/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cu126   (NVIDIA GPU)
tach-nguoi-env/Scripts/python -m pip install torch                                                     (no NVIDIA GPU)
```
Then run every `tn.py` command with that Python (`tach-nguoi-env/Scripts/python scripts/tn.py ...`).

## Rules (always)

1. **Never change the user's original clips.** Read them; write every result as a new file next to the plan (or where the user says). Nothing is overwritten: pick a new name.
2. **Ask before installing anything** (say what, why, how big, the exact command).
3. **Stills first, then a low-res preview, then the full render.** Show the stills and say what the checks found before spending time on a full render.
4. Read the checks the script prints (hidden %, contrast, NOT READABLE notes; also saved in `checks.json` next to the stills) and tell the user in one plain sentence each. Freeze effects print which frame they froze on: look at the stills.

## Setup (first time only)

Before the first effect, run `python scripts/tn.py settings`. If it says **NOT saved yet**, ask the setup questions below, **one at a time**, in the user's language (Vietnamese wording given); if it says **NOT finished**, ask only the ones it lists. Every question offers its options plus two more:

- **"Mình chưa chắc, giải thích giúp mình"**: explain in one or two plain sentences what the choice changes, then ask again.
- **"Cho mình xem hết để so sánh"**: run `python scripts/tn.py sample <kind> <their clip> --out <project>/tach-nguoi-mau/<kind>.mp4 --text "<a word from their video>"`, show the file, then ask again. It takes 5-40 s (say so); it uses their own clip, low resolution, every option side by side, labelled.

Save each answer right away: `python scripts/tn.py settings set <key>=<value>`. The answers live in `tach-nguoi.settings.json` in their project folder, so setup never runs again unless they ask ("làm lại phần cài đặt" → `tn.py settings reset`, then ask again). Plans can still override any setting for one video.

| # | Question (Vietnamese) | Options → value | key | sample kind |
|---|---|---|---|---|
| 1 | Video của bạn đăng ở đâu nhiều nhất? | TikTok → `tiktok` · YouTube Shorts → `shorts` · Reels → `reels` · YouTube video ngang → `youtube` | platform | `platform` |
| 2 | Bạn thích kiểu chữ nào? | Chữ cao, gọn → `cao` · Chữ đậm → `dam` · Đậm vừa → `dam-vua` | font | `font` |
| 3 | Chữ màu gì? | Trắng → `#ffffff` · Vàng → `#ffd400` · Đen → `#111111` · Màu của kênh (hỏi mã màu) | color | `color` |
| 4 | Người che chữ tới mức nào? | Ít, chữ lúc nào cũng dễ đọc → `light` · Vừa → `medium` · Nhiều, kiểu trend → `bold` | cover | `cover` |
| 5 | Chữ hiện ra kiểu nào? | Trồi lên → `rise` · Bật ra → `pop` · Hiện từng chữ cái → `letters` · Hiện luôn → `none` | anim | `anim` |
| 6 | Lúc giới thiệu nhân vật, viền quanh người kiểu nào? | Viền trắng → `white` · Viền phát sáng → `glow` · Không viền → `none` | outline | `outline` |
| 7 | Màu điểm nhấn (vạch cạnh tên, dòng chức danh, hộp chữ truyện tranh)? | Vàng → `#ffd400` · Màu của kênh (hỏi mã màu) | accent | (show `outline`) |
| 8 | Có thêm tiếng động không? | Có → `on` · Không → `off` | sfx | `sfx` (plays each sound) |

Explanations to give for "chưa chắc":
1. Mỗi app che một phần màn hình (nút bấm bên phải, phần mô tả bên dưới). Mình đặt chữ và bảng tên tránh mấy chỗ đó.
2. Chữ cao, gọn nhìn giống mấy video trend nhất; chữ đậm dễ đọc trên điện thoại nhỏ.
3. Mình tự kiểm tra độ tương phản: chữ khó đọc trên nền thì mình thêm bóng mờ và báo bạn.
4. "Ít" thì đầu chỉ chạm nhẹ vào chữ. "Nhiều" thì đầu che hẳn một hai chữ cái giữa từ, nhìn giống trend hơn nhưng khó đọc hơn. Chữ cái đầu và cuối mỗi từ luôn được giữ lại.
5. Chỉ là cách chữ xuất hiện trong nửa giây đầu.
6. Viền giúp người nổi lên khỏi nền tối khi video dừng hình.
8. Tiếng động được tạo mới hoàn toàn, không dính bản quyền.

Don't ask about things the clip already answers (its shape, its length). If the user says "cứ làm đi" or "mặc định", run `python scripts/tn.py settings defaults` (`tiktok`, `cao`, white, `medium`, `rise`, `white`, yellow accent, sound on) and move on.

## Commands

All commands run with the Python that has the packages (see `python scripts/tn.py check`).

```
python scripts/tn.py check                                   # what is installed, GPU, RVM model
python scripts/tn.py behind plan.json --out out/clip.mp4 --stills    # 4 stills per text + checks (fast)
python scripts/tn.py behind plan.json --out out/clip.mp4 --preview   # half size, text's range only -> out/clip.preview.mp4
python scripts/tn.py behind plan.json --out out/clip.mp4             # full render, original audio kept
```

The first run on a clip cuts the person out of the whole clip (about 50 fps on an RTX 4080) and caches it in `_tach-nguoi-work/` next to the output.

## Plan file (you write it)

```json
{"clip": "raw/my-clip.mp4",
 "items": [{"text": "Thành công", "start": 1.0, "end": 7.0,
            "font": "cao", "color": "#ffffff", "anim": "rise", "cover": "medium"}]}
```

- `text`: Vietnamese is fine (any input form; it is normalised). Shown in capitals unless `"upper": false`. A `\n` forces two lines; otherwise the script also tries a two-line layout and keeps the better one.
- `start` / `end`: seconds. At least 0.5 s.
- `font`: `cao` (tall condensed, the classic look), `dam` (heavy), `dam-vua` (extra bold), or a path to a .ttf.
- `anim`: `rise`, `pop`, `letters` (one letter at a time), `none`. Every text also fades out over 0.25 s and pushes in 3 % over its life (`"drift": 0` turns that off).
- `cover`: how much the person may cover the text. `light` (always easy to read), `medium` (default), `bold` (the heavy trend look).
- Optional: `x`, `y` (0-1 centre, to place it by hand), `width` (share of frame width), `shadow` (0-1 glow; set automatically from the contrast check).

Placement is automatic: the biggest size and position where the text sits behind the head and the first and last letters of every word stay visible, inside the platform's safe areas (9:16 keeps clear of the top bar, the right-hand buttons and the caption area at the bottom).

## Freeze-frame effects

```
python scripts/tn.py freeze plan.json --out out/clip.mp4 --stills    # key stills per freeze (fast)
python scripts/tn.py freeze plan.json --out out/clip.mp4 --preview   # half size -> out/clip.preview.mp4
python scripts/tn.py freeze plan.json --out out/clip.mp4             # full render
```

```json
{"clip": "raw/my-clip.mp4",
 "items": [
  {"effect": "intro", "at": 2.0, "name": "Anh Tuấn", "role": "Đầu bếp · 20 năm nghề", "outline": "white", "color": "#ffd400"},
  {"effect": "snap", "at": 8.5},
  {"effect": "comic", "at": 13.2, "caption": "Ủa, thiệt hả?!"}
 ]}
```

- The video **pauses** on one frame for `hold` seconds (defaults: intro 2.4, snap 1.6, comic 1.8), then carries on. The clip gets longer by the holds; the original sound pauses too, and the effect's own sounds play (made from scratch, no licences; `"sfx": false` turns them off, `"sfx_gain"` scales them).
- `at` is a time in the source clip. The script freezes on the **sharpest frame within ±0.25 s** (no motion blur); `"exact": true` keeps the exact frame. Pick moments where the person's face is clear: when their name is said, a big reaction, a pose.
- `intro`: background goes dark and grey, the person pops forward 6 % with an outline (`white`, `glow` in `color`, or `none`), and the name card slides in on the side away from them. `name` is shown in capitals, `role` in `color`.
- `snap`: white flash + shutter, the frame shrinks into a tilted printed photo over a blurred copy.
- `comic`: flat colours, ink lines, halftone dots, flickering speed lines behind the person, optional `caption` box (`color` sets the box colour).

## Clones (phân thân)

```
python scripts/tn.py clone plan.json --out out/clip.mp4 --stills | --preview | (full)
```

```json
{"clip": "raw/walk.mp4",
 "items": [{"effect": "trail", "start": 6.3, "end": 13.0, "every": 0.8, "style": "fade", "fade": 0.6}]}
```

- `trail` (one take): while the person moves, a copy is left every `every` seconds between `start` and `end` and stays, then all copies fade out over `fade` seconds. Only the person who **moves** is copied (someone standing still is left alone). `style`: `fade` (older copies fainter), `solid`, `ghost` (see-through, half grey). A soft flash sound plays as each copy appears (`"sfx": false` at the top of the plan turns it off).
- `two` (two takes, one person in two roles): `{"effect": "two", "second": "raw/take2.mp4", "start": 0, "end": 10, "b_start": 0, "mode": "overlay"}`. `overlay` cuts the person out of take 2 and lays them over take 1 (`"front": "a"` keeps take 1's person in front where they cross); `split` joins the two takes along the emptiest column, with a soft seam.
- Both line every frame up with the background first, so a slightly drifting camera still works (the command prints how far the camera moved). A tripod is still best: a moving, panning or handheld camera with big moves will not line up.

## Known limits

- Works best when there is room above or beside the head. In a tight close-up where the face fills a vertical frame, the text ends up small above the head; say so and suggest a wider shot or `cover: bold`.
- Whole-video cut-out needs PyTorch and the RVM model (GPL-3.0, downloaded by the user's machine on first use); an NVIDIA GPU makes it fast.

## Example prompts

Copy-paste prompts (more with notes in `examples/prompts.md`):

- **One-line starter:** "Làm chữ 'THÀNH CÔNG' sau lưng mình trong clip raw/clip.mp4."
  → setup questions (first time), 4 stills with the readability check, then the full clip with the text behind you.
- **Detailed brief:** "Clip raw/phong-van.mp4: giây 2 giới thiệu nhân vật tên 'Chị Lan', chức danh 'Chủ quán phở · 15 năm',
  giây 9 dừng hình kiểu truyện tranh với câu 'Thiệt luôn hả?!', giây 14 chụp ảnh dừng hình. Có tiếng động."
  → one render with a name-card intro, a comic freeze with a speech box and a photo snap, each with its own sound.
- **Text behind, trend look:** "Chữ 'ĐÀ LẠT' sau lưng mình, cho đầu che nhiều như trend, chữ vàng, hiện từng chữ cái."
- **Clones:** "Clip raw/di-bo.mp4 mình đi ngang qua: để lại bóng mình mỗi 0,8 giây rồi mờ dần."
  → copies of you left along your path, fading out together.
- **Two takes:** "Mình quay 2 lần cùng chỗ (raw/vai-a.mp4, raw/vai-b.mp4), ghép thành 2 người nói chuyện với nhau."
- **Compare:** "Cho mình xem các kiểu chữ để so sánh." → a labelled side-by-side on your own clip.
- **Revision notes:** "Chữ to hơn chút, dời lên trên, dừng hình lâu hơn 1 giây, bỏ tiếng chụp ảnh."
  → only those changes; new stills, then a new render (the old one is kept).

## If something goes wrong

This skill was built with Claude Code, so it may have bugs, and every computer is different. When a step fails, or
the user says the result looks wrong:
1. **Explain it plainly, in Vietnamese:** what failed and why, in one or two sentences. No raw stack traces unless asked.
2. **Read this skill and the script involved** (`scripts/tn.py` and the `tn_*.py` file for the effect). Run
   `python scripts/tn.py check` if something may be missing.
3. **Fix it and re-run**, writing a new output file. Never touch or overwrite the user's clips, even while fixing.
4. If the cause was in this skill itself, say so and suggest reporting it so it's fixed for everyone:
   https://github.com/thegentleminh/thegentleminh-skills/issues

### Common failures

- **`No module named 'torch'`:** PyTorch isn't installed in the Python that ran the command; use the
  `tach-nguoi-env` Python (see Installing PyTorch).
- **Very slow cut-out:** no NVIDIA GPU, or the CPU build of PyTorch on a machine that has one (`tn.py check` says
  "GPU: none"); reinstall with the CUDA command above.
- **`CUDA out of memory`:** close other GPU apps, or set the environment variable `TACH_NGUOI_MATTE_WIDTH=960`
  (the cut-out runs at 1280 wide by default) and run again.
- **The text is small or sits above the head:** the person fills the frame; suggest a wider shot, `cover: bold`, or
  place it by hand with `x`, `y`.
- **"NOT READABLE" in the checks:** the person covers too much of a word. Shorter text, `cover: light`, or another moment.
- **Rough edges around hair or hands:** a limit of the cut-out; a plainer background or a slower moment helps.
- **Clones drift or double:** the camera moved too much (the command prints how far); use a tripod.
- **A stale cut-out after editing the clip:** delete `_tach-nguoi-work/` next to the output and run again.

## Credits

- Cut-out: [Robust Video Matting](https://github.com/PeterL1n/RobustVideoMatting) (GPL-3.0), loaded by
  `scripts/rvm_matte.py` (GPL-3.0, licence text in `scripts/LICENSE-GPL-3.0.txt`); the model downloads to the
  user's machine and is not bundled. Everything else in this skill is MIT.
- Fonts (SIL Open Font License 1.1, licence files in `fonts/`): Be Vietnam Pro, Anton.
- Sound effects are generated by the scripts (no samples, no licences).
