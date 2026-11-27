# TheGentleMinh skills

Free Claude Code skills for YouTube creators, from [TheGentleMinh](https://thegentleminh.com). Instructions in Vietnamese with copy-paste commands: [thegentleminh.com/ky-nang](https://thegentleminh.com/ky-nang/).

| Skill | What it does |
|---|---|
| [dung-video](plugins/dung-video/skills/dung-video/SKILL.md) | Set up video editing with Claude Code and do basic edits with ffmpeg: trim, join, vertical Shorts, Vietnamese subtitles (.srt), loudness, export with YouTube's recommended upload settings, thumbnail frames. |
| [tach-nguoi](plugins/tach-nguoi/skills/tach-nguoi/SKILL.md) | Person cut-out effects on your own clip: big text behind the person (placed automatically so it stays readable), a freeze-frame character intro with a name card, freeze snap and comic freeze, clones from one take or two. Needs PyTorch; an NVIDIA GPU makes it fast. |
| [ban-do](plugins/ban-do/skills/ban-do/SKILL.md) | Animated map clips: zoom from a region to a country or city, highlight a country (tint, outline or spotlight), a pin with a name, a big number that counts up, a title; 9:16, 16:9, 1:1 or 4:5 MP4 with no sound. Flat map from Natural Earth (public domain), drawn on your computer with Python + ffmpeg. Maps of Vietnam always show Hoàng Sa, Trường Sa and Biển Đông. |
| [storykit-free](plugins/storykit-free/skills/studio-setup/SKILL.md) | Install Roblox Studio and connect it to Claude Code through Roblox's own Studio MCP server, step by step in Vietnamese, then check the connection ("kiểm tra kết nối"). Install and connect only; it does not make videos. Tested on Windows 10/11; macOS not tested yet. Unofficial; not affiliated with Roblox Corporation. |
| [storykit](plugins/storykit/skills/studio-story-shorts/SKILL.md) | **Needs a Blocky StoryKit Pass.** Vietnamese "Ở thế giới này…" story Shorts filmed in Roblox Studio: premise, script, shot plan, sets and cast, acting, recording, captions, music and the final 9:16 edit. This plugin is the starter (connection check, setup, download of the full skill from the Pass server). Tested on Windows 10/11; macOS not tested yet. Unofficial; not affiliated with Roblox Corporation. |

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


**tach-nguoi** runs everything on your computer. The only download is its model, once, on first use: the RVM cut-out model through PyTorch (its loader `rvm_matte.py` is GPL-3.0, the rest MIT). It has no hooks or background processes, asks before installing anything, and never changes your clips.

**ban-do** runs everything on your computer (Python, Pillow, ffmpeg). The only download is the map data from Natural Earth (about 18 MB), once, on first use. It has no hooks or background processes, asks before installing anything, and never overwrites your files.

**storykit-free** has no scripts of its own. It checks whether Roblox Studio is installed, gives you the `claude mcp add` command for Roblox's Studio MCP server (you run it, or Claude runs it after you agree), and calls the Studio MCP's `list_roblox_studios` to check the connection. It downloads nothing (Studio comes from Roblox's own page), has no hooks or background processes, and never opens or edits your published games.

**storykit** connects to the Blocky StoryKit Pass server at `https://thegentleminh.com/mcp/` and sends your Pass code with each call (Claude Code keeps the code in your system's credential store, not in the plugin's files). With a valid Pass, its one script, [`storykit_sync.py`](plugins/storykit/skills/studio-story-shorts/scripts/storykit_sync.py), downloads the skill package from a short-lived link on thegentleminh.com or its storage, checks its size and SHA-256, and unpacks it into a `.storykit` folder inside your video's folder. It accepts no other download hosts, has no hooks or background processes, asks before installing anything, and never opens or edits your published games.

## Licence

MIT. See [LICENSE](LICENSE).
