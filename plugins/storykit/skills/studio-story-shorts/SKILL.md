---
name: studio-story-shorts
description: Blocky StoryKit - make a Vietnamese "Ở thế giới này… / Ở thị trấn này…" story Short (9:16, 2-2.5 min) from a topic, filmed inside Roblox Studio through its MCP server - premise, script, shot plan, scene build, acting, recording in Studio, captions, music and the final edit. Needs a Blocky StoryKit Pass. Use for "make a Short about X", "Ở thế giới này ___ thì sao", "story Short in Studio", "film this script in Studio", notes on a draft ("this shot is too tight", "he should walk faster"), or the Blocky StoryKit connection check ("kiểm tra kết nối", "check the Blocky StoryKit connection", "Pass còn hạn không").
---

# Blocky StoryKit: Studio Story Shorts

Unofficial tool for Roblox Studio creators. **Không liên kết với Roblox Corporation.** We sell the workflow and the craft, never assets: every model, clothing item, sky, decal and animation is a free or catalogue item loaded **by ID inside your own Studio**. Nothing is downloaded out of Roblox or re-uploaded.

This plugin is the **starter**. The full method (the steps, references, tools and Studio modules) comes from the **Blocky StoryKit Pass** server and is saved in the project at `<project>/.storykit/method/`. Every run: connection check → sync → read `.storykit/method/METHOD.md` and follow it.

Talk to the user in Vietnamese. `<project>` is the folder of the current video (ask once if it isn't clear; a new video gets a new folder).

## Two connections

- **Roblox Studio's MCP** (Roblox's own, local): `list_roblox_studios`, `execute_luau`, `video_capture`… builds and films inside the user's Studio.
- **Blocky StoryKit Pass** (`mcp__plugin_storykit_storykit-pass__*`, declared in this plugin's `.mcp.json`): Claude Code asks for the Pass code when the plugin is enabled and keeps it in the system's secure credential store, never in these files.

## 1. Connection check (start of every run, and whenever the user types "kiểm tra kết nối")

Call `list_roblox_studios`, then `pass_status`, then check the machine: `python --version` (3.10+), `ffmpeg -version`, and `python -c "import numpy, cv2, faster_whisper"`. Report in Vietnamese, one line per connection.

The Pass server never answers a wrong, missing or expired code with an auth error: `pass_status` always returns `{valid, valid_until, plan, content_version, message_vi}`. Show `message_vi` as the server wrote it.

- **Both OK** (`valid: true`): "Đã kết nối Roblox Studio (<tên place>) · Đã kết nối Blocky StoryKit Pass · Pass còn hạn đến <valid_until, D/M/YYYY>."
- **Studio not connected** (tool missing or error): "Chưa kết nối được Roblox Studio. Hãy mở Roblox Studio, mở một place, bật MCP server trong Studio rồi gõ lại 'kiểm tra kết nối'." Then help with setup step B below.
- **Missing or wrong code** (`valid: false`, no `valid_until`; the message starts "Chưa có mã Pass" or "Mã Pass không đúng"): "<message_vi>"
- **Pass expired** (`valid: false` with a `valid_until`; "Pass hết hạn ngày…"): "<message_vi>" then: "Các video và file bạn đã làm vẫn là của bạn." Do not run the method (section 3).
- **Pass tools missing** (no `storykit-pass` tools, or `/mcp` shows it failed / "Needs authentication"): "Chưa kết nối Blocky StoryKit Pass. Gõ /plugin, kiểm tra plugin storykit đang bật và đã nhập mã Pass, rồi gõ /mcp để kết nối lại."
- **Server not answering** (timeout, 5xx, "Failed to connect"): "Máy chủ Blocky StoryKit Pass đang không phản hồi (không phải lỗi của bạn)." Then section 3's offline rule.
- **Machine:** anything missing → one more line, "Máy còn thiếu: <items>", with the fix (Windows: `winget install -e --id Python.Python.3.12`, `winget install -e --id Gyan.FFmpeg`, then `python -m pip install numpy opencv-python faster-whisper`). Ask before installing anything.

## 2. First-run setup (connections)

- **A. Roblox Studio installed?** *(Windows path)* `%LOCALAPPDATA%\Roblox\Versions\*\RobloxStudioBeta.exe`. If missing: "Tải Roblox Studio (miễn phí) từ trang chính thức https://create.roblox.com/docs/studio/setup (Download Studio), cài, đăng nhập, rồi quay lại đây." Never download or hand over an installer yourself.
- **B. Studio's MCP.** If `list_roblox_studios` isn't available, give the *(Windows)* command `claude mcp add --transport stdio Roblox_Studio -- cmd.exe /c "cd /d %LOCALAPPDATA%\Roblox && .\mcp.bat"` and the switch: in Studio, **MCP** at the bottom right → **Assistant Settings** → **MCP Servers** → turn on **Enable Studio as MCP server** (handbook images 1-2). **Then warn plainly and recommend turning Data access off** (same page, image 3; on by default): when on, Studio adds hooks to the user-level `~/.claude/settings.json` (`StudioMCPHook.bat roblox-data-access claude_code prompt|tool|stop`); the UserPromptSubmit and Stop hooks have no matcher, so every prompt in every Claude Code project is passed to Roblox, not only Roblox work. After the user turns it off, offer to check settings.json for hooks calling StudioMCPHook.bat and, with their OK, back the file up and remove them. Restart Claude Code, then call `list_roblox_studios` until it lists the open place.
- **C. Blocky StoryKit Pass:** the code is typed into Claude Code when the plugin is installed, or with `/plugin configure storykit@thegentleminh`; `pass_status` must say `valid: true`.

## 3. Sync the method

`SYNC` = `python "<this skill's folder>/scripts/storykit_sync.py"` (the folder Claude Code shows as this skill's base directory).

1. `SYNC status --project <project>` → the cached `content_version`, `valid_until`, `intact`.
2. **Pass valid:**
   - Cache missing, `intact` false, or its `content_version` differs from `pass_status.content_version` → call `get_bundle` and run `SYNC fetch --project <project> --url "<url>" --sha256 <sha256> --bytes <bytes> --version <content_version> --valid-until <valid_until>`. Say one line: "Đã tải phương pháp Blocky StoryKit bản <content_version>." The url expires in 15 minutes: fetch right away; if it expired, call `get_bundle` again.
   - Cache current → `SYNC touch --project <project> --valid-until <valid_until>` and go on.
3. **Pass expired or code wrong:** don't sync and don't follow the cached method; for an expired Pass run `SYNC touch --project <project> --valid-until <valid_until>` so the offline rule below knows it ended. Say the server's message. The user keeps every video and file they made; nothing is deleted.
4. **Server not answering:** if the cache is `intact` and its `valid_until` is today or later, go on with the cached method and say "Đang dùng bản phương pháp đã lưu (<content_version>) vì máy chủ chưa phản hồi." Otherwise stop and ask the user to try again later.
5. Never edit files in `.storykit/method/` to change behaviour (a sync replaces them). Never copy them outside the project or share them.

Then **read `<project>/.storykit/method/METHOD.md` and follow it** from its setup section. Every path in the method files is relative to `.storykit/method/`.

## Requirements and limits

- **A Blocky StoryKit Pass** (the method, the banks and the asset catalogue come from the Pass server; the starter plugin alone can't make a video).
- **Roblox Studio** (current build) with its **MCP server** added to Claude Code (command above). Studio ids change every time a place reopens.
- **Tested on Windows 10/11; macOS not tested yet.** Windows-only steps: the Studio MCP command (`cmd.exe`, `%LOCALAPPDATA%`), the Studio install path, `winget`, and the method's Studio installer (calls Studio's `mcp.bat`).
- **Claude Code** (runs on your own Claude account).
- **ffmpeg** on PATH; **Python 3.10+** with `pip install numpy opencv-python faster-whisper`. **GPU optional**: NVIDIA makes word timing faster; without it, it runs on the CPU.
- **Internet for the sync** (about 110 KB, only when the method changes); after that a video works from the saved copy while the Pass is valid.
- **Narration is yours to make**: your own voice, ElevenLabs (paid, your own account; guide thegentleminh.com/ky-nang/elevenlabs/), TTSMaker (free, about 20,000 characters a week) or VoiceStudio (free; default model non-commercial). Guides for the last two: thegentleminh.com/ky-nang/voicestudio/.
- **Speed**: about 2-4 hours of Claude time for a 2-min Short. **Studio must be the front window and the monitor awake while recording** (otherwise jerky or black takes). Takes are capped at ~30 s; a 2-min Short is 5-8 takes, joined automatically.
- **Characters are blocky R15 with Roblox dynamic heads**: mouths move with the words, faces change by mood; no true lip-sync of every sound, fingers don't move.
- **Missing assets** are made with Roblox's generate_mesh when needed: **every attempt, retries included, becomes a permanent private Package in your Roblox inventory and counts toward Roblox's generation limits.**
- **Your avatars and catalogue items are your responsibility under Roblox's terms.** Creator Store assets stay inside Studio. Don't use Roblox logos or "Roblox" in your channel branding.
- **When the Pass ends**, Blocky StoryKit stops making new videos. The videos and files you made stay yours.
- **No view or income promises.** Built with Claude Code; it may have bugs. Your Claude can fix them (below).

## If something goes wrong

1. Say plainly what happened and why, in one or two sentences, before fixing anything.
2. Connection or sync problems: use the table. Problems while making the video: follow the "If something goes wrong" section of METHOD.md.
3. Never touch the user's files outside the project folder; never delete their places; work on copies.

| Symptom | Cause | Fix |
|---|---|---|
| No `storykit-pass` tools, or `/mcp` shows it failed | Plugin off, or no Pass code entered | `/plugin` → storykit enabled → `/plugin configure storykit@thegentleminh` → paste the code → `/mcp` reconnect |
| "Chưa có mã Pass" / "Mã Pass không đúng" | Code missing or mistyped | `/plugin configure storykit@thegentleminh`, paste the code from the email again |
| "Pass hết hạn ngày …" | Pass expired | Renew at the link in the message; videos already made stay yours |
| `storykit_sync.py`: "checksum mismatch" or "download incomplete" | Download cut off | Run the sync again (call `get_bundle` for a fresh link) |
| `storykit_sync.py`: "refused: the bundle URL must be https…" | The link isn't from the Blocky StoryKit server | Don't download; report it |
| "UserPromptSubmit hook error" / "Stop hook error" with StudioMCPHook.bat on every prompt | Studio's Data access added hooks to `~/.claude/settings.json` that pass every prompt (all projects) to Roblox | User turns Data access off in Studio; with their OK, back up settings.json and remove the hooks calling StudioMCPHook.bat |

4. Suggest reporting the problem so every buyer gets the fix: **GitHub Issues**: https://github.com/thegentleminh/thegentleminh-skills/issues.

## Example prompts

See [examples/prompts.md](examples/prompts.md): a one-line starter, a detailed brief, per-step prompts and revision notes, each with what it gives.
