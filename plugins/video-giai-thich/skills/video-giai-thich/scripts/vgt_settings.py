"""Saved setup answers for video-giai-thich (asked once, reused for every video). MIT licence.

The file is `video-giai-thich.settings.json` in the user's project folder (the folder Claude Code runs in),
unless VIDEO_GIAI_THICH_SETTINGS points somewhere else. Anything the user asks for in one video wins.
"""
import json
import os
from pathlib import Path

# key -> (default, allowed values or None for free text, what it changes)
OPTIONS = {
    "look": ("in-riso", ["in-riso", "bang-phan", "bao-giay", "ban-ve", "poster"], "the look of every scene"),
    "voice": ("elevenlabs", ["elevenlabs", "own", "none"], "who reads the script"),
    "voice_id": ("UsgbMVmY3U59ijwK5mdh", None, "ElevenLabs voice id (default: Triệu Dương, Southern, public library)"),
    "reveal": ("word", ["word", "sentence"], "words appear one by one with the voice, or a whole sentence at once"),
    "music": ("none", ["none", "own"], "background music under the voice"),
    "music_file": ("", None, "path to the user's own music file (only theirs, or royalty-free)"),
    "length": ("short", ["short", "long"], "short = 30-60 s (TikTok, Reels, Shorts); long = 1-3 min"),
    "tone": ("than-mat", ["than-mat", "chuan", "vui"], "how the script talks: friendly, neutral, playful"),
    "handle": ("", None, "channel name shown small at the top (empty = none)"),
}

OPTIONAL = {"voice_id", "music_file"}  # only asked when voice=elevenlabs / music=own

QUESTIONS_VI = {  # what Claude asks, in this order
    "look": "Bạn muốn video theo kiểu nào? (In riso / Bảng phấn / Báo giấy / Bản vẽ / Poster)",
    "voice": "Ai đọc lời? (Giọng ElevenLabs / Bạn tự thu / Không có giọng, chỉ có chữ)",
    "reveal": "Chữ hiện ra thế nào? (Từng chữ theo giọng đọc / Cả câu một lúc)",
    "music": "Có nhạc nền không? (Không / Nhạc của bạn)",
    "length": "Video thường dài bao nhiêu? (Ngắn 30-60 giây / Dài 1-3 phút)",
    "tone": "Giọng văn thế nào? (Thân mật / Chuẩn mực / Vui nhộn)",
    "handle": "Có muốn hiện tên kênh nhỏ ở trên không? (Không / Có: tên kênh là gì?)",
}


def path():
    return Path(os.environ.get("VIDEO_GIAI_THICH_SETTINGS") or (Path.cwd() / "video-giai-thich.settings.json"))


def load():
    p = path()
    s = {k: v[0] for k, v in OPTIONS.items()}
    saved = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    s.update(saved)
    s["_missing"] = [k for k in OPTIONS if k not in OPTIONAL and k not in saved]
    s["_saved"] = not s["_missing"]
    return s


def save_defaults():
    """The user said "cứ làm đi" / "mặc định": answer every remaining question with its default."""
    cur = load()
    return save({k: OPTIONS[k][0] for k in cur["_missing"]}) if cur["_missing"] else path()


def save(updates):
    p = path()
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in updates.items():
        if k not in OPTIONS:
            raise SystemExit(f"Unknown setting '{k}'. Settings: {', '.join(OPTIONS)}")
        allowed = OPTIONS[k][1]
        if allowed and v not in allowed:
            raise SystemExit(f"'{k}' must be one of: {', '.join(allowed)}")
        if k == "music_file" and v and not Path(v).exists():
            raise SystemExit(f"Music file not found: {v}")
        cur[k] = v
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def reset():
    p = path()
    if p.exists():
        p.unlink()
    return p
