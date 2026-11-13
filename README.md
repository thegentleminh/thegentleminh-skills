# TheGentleMinh skills

Free Claude Code skills for YouTube creators, from [TheGentleMinh](https://thegentleminh.com). Instructions in Vietnamese with copy-paste commands: [thegentleminh.com/ky-nang](https://thegentleminh.com/ky-nang/).

| Skill | What it does |
|---|---|
| [dung-video](plugins/dung-video/skills/dung-video/SKILL.md) | Set up video editing with Claude Code and do basic edits with ffmpeg: trim, join, vertical Shorts, Vietnamese subtitles (.srt), loudness, export with YouTube's recommended upload settings, thumbnail frames. |

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

## Licence

MIT. See [LICENSE](LICENSE).
