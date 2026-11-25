# TheGentleMinh skills

Free Claude Code skills for YouTube creators, from [TheGentleMinh](https://thegentleminh.com). Instructions in Vietnamese with copy-paste commands: [thegentleminh.com/ky-nang](https://thegentleminh.com/ky-nang/).

| Skill | What it does |
|---|---|
| [dung-video](plugins/dung-video/skills/dung-video/SKILL.md) | Set up video editing with Claude Code and do basic edits with ffmpeg: trim, join, vertical Shorts, Vietnamese subtitles (.srt), loudness, export with YouTube's recommended upload settings, thumbnail frames. |
| [tach-nguoi](plugins/tach-nguoi/skills/tach-nguoi/SKILL.md) | Person cut-out effects on your own clip: big text behind the person (placed automatically so it stays readable), a freeze-frame character intro with a name card, freeze snap and comic freeze, clones from one take or two. Needs PyTorch; an NVIDIA GPU makes it fast. |
| [anh-thanh-video](plugins/anh-thanh-video/skills/anh-thanh-video/SKILL.md) | Turn photos into a video: photos changing on the beat of your own song, a gentle photo album, or a 2.5D "3D zoom". Faces kept in frame, Vietnamese titles and captions, 9:16 / 16:9 / 1:1 / 4:5. |
| [ban-do](plugins/ban-do/skills/ban-do/SKILL.md) | Animated map clips: zoom from a region to a country or city, highlight a country (tint, outline or spotlight), a pin with a name, a big number that counts up, a title; 9:16, 16:9, 1:1 or 4:5 MP4 with no sound. Flat map from Natural Earth (public domain), drawn on your computer with Python + ffmpeg. Maps of Vietnam always show Hoàng Sa, Trường Sa and Biển Đông. |

## Install (inside Claude Code)

```
/plugin marketplace add thegentleminh/thegentleminh-skills
/plugin install dung-video@thegentleminh
```

Or from a terminal:

```
claude plugin marketplace add thegentleminh/thegentleminh-skills
claude plugin install dung-video@thegentleminh
```

Update: `claude plugin marketplace update thegentleminh` then `claude plugin update dung-video@thegentleminh`.
Remove: `claude plugin uninstall dung-video@thegentleminh`.

## Before you install

Skills and plugins act on your computer with your permissions. Read [SKILL.md](plugins/dung-video/skills/dung-video/SKILL.md) and the [script](plugins/dung-video/skills/dung-video/scripts/phu_de.py) first. This skill has no hooks, no background processes and no network calls of its own; it runs ffmpeg (and, for subtitles, faster-whisper) on your files, asks before installing anything, and never changes your original files.


**tach-nguoi** and **anh-thanh-video** run everything on your computer. The only downloads are their models, once, on first use: the RVM cut-out model through PyTorch (tach-nguoi; its loader `rvm_matte.py` is GPL-3.0, the rest MIT), and a face model plus an optional depth model (anh-thanh-video). They have no hooks or background processes, ask before installing anything, and never change your clips, photos or music.

**ban-do** runs everything on your computer (Python, Pillow, ffmpeg). The only download is the map data from Natural Earth (about 18 MB), once, on first use. It has no hooks or background processes, asks before installing anything, and never overwrites your files.

## Licence

MIT. See [LICENSE](LICENSE).
