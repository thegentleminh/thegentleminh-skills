"""Saved setup answers for anh-thanh-video (asked once, reused for every video). MIT licence.

The file is `anh-thanh-video.settings.json` in the user's project folder (the folder Claude Code runs in),
unless ANH_THANH_VIDEO_SETTINGS points somewhere else. A plan's own fields always win over these defaults.
"""
import json
import os
from pathlib import Path

# key -> (default, allowed values or None for free text, what it changes)
OPTIONS = {
    "shape": ("9:16", ["9:16", "16:9", "1:1", "4:5"], "video shape: 9:16 TikTok/Reels/Shorts, 16:9 YouTube, 1:1 / 4:5 feed posts"),
    "mode": ("beat", ["beat", "album"], "beat = photos change on the beat; album = gentle, a few seconds per photo"),
    "move": ("auto", ["auto", "snap", "kenburns", "parallax", "none"], "camera move (auto: snap for beat, kenburns for album)"),
    "hits": ("vua", ["manh", "vua", "nhe", "khong"], "beat mode: how hard each cut hits"),
    "font": ("dam", ["cao", "dam", "dam-vua"], "title font (captions stay in a readable bold, dam-vua)"),
    "color": ("#ffffff", None, "text colour (hex)"),
    "fit": ("auto", ["auto", "crop", "blur"], "fill the screen when faces fit, always fill, or always show the whole photo"),
}

OPTIONAL = {"color"}  # asked only when the user wants a title or captions

HITS = {"manh": ["flash", "pop", "shake", "glitch"], "vua": ["flash", "pop", "shake"], "nhe": ["pop"], "khong": []}
NAMES_VI = {  # labels for comparison samples
    "mode": {"beat": "Theo nhịp", "album": "Album nhẹ nhàng"},
    "move": {"snap": "Giật theo nhịp", "kenburns": "Đẩy chậm", "parallax": "3D chiều sâu", "none": "Đứng yên"},
    "hits": {"manh": "Mạnh", "vua": "Vừa", "nhe": "Nhẹ", "khong": "Không"},
    "font": {"cao": "Chữ cao", "dam": "Chữ đậm", "dam-vua": "Đậm vừa"},
    "fit": {"auto": "Tự động", "crop": "Luôn lấp đầy", "blur": "Giữ cả ảnh"},
    "shape": {"9:16": "9:16 dọc", "16:9": "16:9 ngang", "1:1": "1:1 vuông", "4:5": "4:5"},
}


def path():
    return Path(os.environ.get("ANH_THANH_VIDEO_SETTINGS") or (Path.cwd() / "anh-thanh-video.settings.json"))


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
        if k == "color" and not (v.startswith("#") and len(v) == 7):
            raise SystemExit("'color' must be a colour like #ffd400")
        cur[k] = v
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def reset():
    p = path()
    if p.exists():
        p.unlink()
    return p


def apply(plan, s=None):
    """Fill the plan's missing fields from the saved settings."""
    s = s or load()
    plan.setdefault("shape", s["shape"])
    plan.setdefault("mode", s["mode"])
    if s["move"] != "auto":
        plan.setdefault("move", s["move"])
    plan.setdefault("hits", HITS[s["hits"]])
    plan.setdefault("font", s["font"])
    plan.setdefault("color", s["color"])
    plan.setdefault("fit", s["fit"])
    return plan
