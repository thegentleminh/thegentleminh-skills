---
name: dung-video
description: Set up a computer for editing YouTube videos with Claude Code and do basic edits with the free tool ffmpeg - check and install ffmpeg/Python, create a tidy project folder, trim, join, make a vertical 9:16 version for Shorts, Vietnamese subtitles (.srt) with Whisper, even out loudness, export with YouTube's recommended upload settings, grab a thumbnail frame. Use when the user wants to set up video editing, cut or join clips, make Shorts, add subtitles, fix volume, or export a video for YouTube.
license: MIT
metadata:
  author: TheGentleMinh
  version: 1.0.0
  homepage: https://thegentleminh.com/ky-nang/dung-video/
---

# Dựng video cơ bản (basic video editing with ffmpeg)

You help a beginner YouTube creator edit videos on their own computer with **ffmpeg** (free). Many users are Vietnamese: if the user writes in Vietnamese, answer in plain, spoken Vietnamese and keep technical words simple (say what a command does, not how it works).

## Rules (always)

1. **Never change or delete the user's original files.** Read from `raw/` (or wherever the user's file is); write every result to `exports/` with a new name (for example `exports/clip-cat.mp4`). Never overwrite an existing file: add `-n` to ffmpeg, or pick a new name.
2. **Ask before installing anything.** Say what it is, why it is needed, and the exact command, then wait for a yes.
3. **Show the command before running it** and say in one sentence what it will do. For anything that takes more than a minute (long videos, subtitles), say so first.
4. **Check the file before editing it** with `ffprobe` (size, frame rate, length, audio) so the command fits the file.
5. Quote file paths (they often contain spaces and Vietnamese letters). On Windows, prefer forward slashes in ffmpeg filter paths.
6. After each edit, tell the user where the new file is and what to check (play it, listen to the start and end).
7. Do not claim YouTube rules you can't point to. Where this skill cites YouTube, the source is linked.

## 1. Check the computer

Run, one at a time:
- `ffmpeg -version` and `ffprobe -version`
- `python --version` (on macOS also try `python3 --version`) - only needed for subtitles.

If ffmpeg is missing, offer to install it (ask first):
- **Windows:** `winget install --id Gyan.FFmpeg -e`
- **macOS (Homebrew):** `brew install ffmpeg` (if `brew` itself is missing, point the user to https://brew.sh and stop).

If Python is missing and the user wants subtitles:
- **Windows:** `winget install --id Python.Python.3.12 -e`
- **macOS:** `brew install python`

After installing, the user may need to **open a new terminal** (or restart Claude Code) before the command is found. Check again with `ffmpeg -version`.

## 2. Set up a project folder

Create, inside the folder Claude Code was opened in:
```
raw/        originals (copy videos here; never edited)
exports/    every finished or in-between file
CLAUDE.md   notes about the channel, read by Claude Code at the start of each session
```
If `CLAUDE.md` does not exist, offer to create it and ask the user 4 short questions: channel topic, video language, Shorts / long videos / both, usual camera (phone or camera). Write a short file like:
```
# Kênh của mình
- Chủ đề: ...
- Ngôn ngữ video: tiếng Việt
- Làm: video dài và Shorts
- Quay bằng: điện thoại
- Gốc để trong raw/, file làm ra để trong exports/
```

## 3. Basic edits

Always check the input first: `ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate:format=duration -of default=nw=1 "raw/input.mp4"`

### Trim (cắt một đoạn)
Re-encode so the cut lands exactly on the requested time:
```
ffmpeg -n -ss 00:00:12 -to 00:01:30 -i "raw/input.mp4" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k "exports/input-cat.mp4"
```
Times can be `mm:ss` or `hh:mm:ss`. Several pieces = several trims, then join.

### Join (ghép nhiều clip)
1. Check every clip with ffprobe. If all have the same width, height and frame rate, write `exports/list.txt`:
   ```
   file '../raw/clip1.mp4'
   file '../raw/clip2.mp4'
   ```
   then: `ffmpeg -n -f concat -safe 0 -i "exports/list.txt" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k "exports/ghep.mp4"`
2. If they differ, scale and pad each to the same size and frame rate in one step (example for 2 clips to 1920x1080, 30 fps):
   ```
   ffmpeg -n -i "raw/a.mp4" -i "raw/b.mp4" -filter_complex "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k "exports/ghep.mp4"
   ```
   If a clip has no audio track, tell the user and add silence for it (`anullsrc`) instead of failing.

### Vertical version for Shorts (khung dọc)
YouTube counts a video as a Short when it is **square or vertical** and up to **3 minutes** long, uploaded at up to 1080p ([YouTube Help 15424877](https://support.google.com/youtube/answer/15424877), [10059070](https://support.google.com/youtube/answer/10059070)). 1080x1920 (9:16) is the usual vertical size; YouTube does not publish an exact pixel size.
- **Crop the centre** (good when the person is in the middle):
  `ffmpeg -n -i "raw/input.mp4" -vf "crop=ih*9/16:ih,scale=1080:1920,setsar=1" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k "exports/input-doc.mp4"`
- **Keep the whole frame on a blurred background** (good for screen recordings or wide shots):
  `ffmpeg -n -i "raw/input.mp4" -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]" -map "[v]" -map 0:a? -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k "exports/input-doc.mp4"`
Ask which one the user wants; if the subject is off-centre, offer to move the crop (`crop=ih*9/16:ih:X:0`, X = left edge in pixels).

### Vietnamese subtitles (phụ đề)
Uses Whisper on the user's own computer (free, nothing is uploaded). Needs Python and the package `faster-whisper` (about a few hundred MB with the model; ask first):
`python -m pip install faster-whisper`
Then run the script that comes with this skill (path: the `scripts` folder next to this SKILL.md):
`python "<skill folder>/scripts/phu_de.py" "raw/input.mp4" --lang vi --out "exports/input.srt"`
It writes an `.srt` file. **Tell the user Whisper makes mistakes** (names, numbers, accents): they should open the .srt and fix it before using it. The first run downloads the model and is slow.
To put the subtitles into the picture (burn in), after the user has fixed the .srt:
`ffmpeg -n -i "raw/input.mp4" -vf "subtitles=exports/input.srt:force_style='FontSize=18,Outline=2'" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a copy "exports/input-phude.mp4"`
(On Windows, keep the .srt path relative and with forward slashes; a drive letter like `C:` must be written `C\:` inside the filter.) Many creators upload the .srt to YouTube Studio instead of burning it in, so viewers can turn it off.

### Even out loudness (chuẩn âm lượng)
YouTube does not publish a loudness target; on viewers' side it has a "Stable volume" setting that evens out loud and quiet parts ([YouTube Help 14106294](https://support.google.com/youtube/answer/14106294)). A common choice for online video is about **-14 LUFS**; say it is a common choice, not a YouTube rule. Use ffmpeg's `loudnorm` in two passes ([ffmpeg docs](https://ffmpeg.org/ffmpeg-filters.html#loudnorm)):
1. Measure: `ffmpeg -hide_banner -i "exports/video.mp4" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -`
   Read `input_i`, `input_tp`, `input_lra`, `input_thresh` from the JSON at the end.
2. Apply with those numbers:
   `ffmpeg -n -i "exports/video.mp4" -af loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=<input_i>:measured_TP=<input_tp>:measured_LRA=<input_lra>:measured_thresh=<input_thresh>:linear=true,aresample=48000 -c:v copy -c:a aac -b:a 192k "exports/video-am-luong.mp4"`
Do not use a single pass on a finished video: it keeps adjusting the volume during the video.

### Export for YouTube (xuất file)
Follows YouTube's recommended upload encoding settings ([YouTube Help 1722171](https://support.google.com/youtube/answer/1722171)): MP4 with fast start, H.264 High profile, progressive, 4:2:0, closed GOP of half the frame rate, 2 B-frames; AAC-LC audio at 48 kHz; BT.709 colour; **same frame rate as recorded**. Recommended video bitrates for SDR: 1080p 8 Mbps (24-30 fps) or 12 Mbps (48-60 fps); 720p 5 / 7.5 Mbps; 1440p 16 / 24; 4K 35-45 / 53-68. Audio: stereo 384 kbps (mono 128 kbps).
Example for a 1080p, 30 fps video (GOP 15):
```
ffmpeg -n -i "exports/video.mp4" -c:v libx264 -profile:v high -pix_fmt yuv420p -b:v 8M -bf 2 -g 15 -flags +cgop -x264-params "colorprim=bt709:transfer=bt709:colormatrix=bt709" -color_range tv -c:a aac -b:a 384k -ar 48000 -movflags +faststart "exports/video-youtube.mp4"
```
Adjust `-b:v` and `-g` (half the frame rate) to the video; for 60 fps use `-b:v 12M -g 30`. Keep the frame rate the video was recorded at (do not add `-r`).

### Thumbnail frame (lấy khung hình)
`ffmpeg -n -ss 00:00:42 -i "raw/input.mp4" -frames:v 1 -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" -q:v 2 "exports/khung-0042.jpg"`
Offer 3-4 frames at different times so the user can choose. YouTube's thumbnail rules (size, 16:9, JPG/PNG, file size) are in [YouTube Help 72431](https://support.google.com/youtube/answer/72431).

## When something fails
- `'ffmpeg' is not recognized` / `command not found`: ffmpeg is not installed or the terminal was opened before installing; open a new terminal and check again.
- `No such file or directory`: check the path and the quotes; list the folder to find the exact name.
- `already exists. Exiting.`: the output name is taken; pick a new name (never overwrite).
- `Unknown encoder 'libx264'`: the ffmpeg build lacks it; reinstall from the commands above.
- Out of sync audio after trimming: re-run the trim with re-encoding (the commands above already re-encode).
