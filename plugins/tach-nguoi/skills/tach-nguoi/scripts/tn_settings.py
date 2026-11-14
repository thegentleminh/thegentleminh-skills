"""Saved setup answers for tach-nguoi (asked once, reused on every plan). MIT licence.

The file is `tach-nguoi.settings.json` in the user's project folder (the folder Claude Code runs in),
unless TACH_NGUOI_SETTINGS points somewhere else. A plan's own fields always win over these defaults.
"""
import json
import os
from pathlib import Path

# key -> (default, allowed values or None for free text, what it changes)
OPTIONS = {
    "platform": ("tiktok", ["tiktok", "shorts", "reels", "youtube"], "safe areas: where text and cards may go"),
    "font": ("cao", ["cao", "dam", "dam-vua"], "text look"),
    "color": ("#ffffff", None, "text colour (hex)"),
    "accent": ("#ffd400", None, "accent colour: name-card bar and role line, glow outline, comic caption box"),
    "cover": ("medium", ["light", "medium", "bold"], "how much the person may cover the text"),
    "anim": ("rise", ["rise", "pop", "letters", "none"], "how text comes in"),
    "outline": ("white", ["white", "glow", "none"], "outline around the person in the character intro"),
    "sfx": ("on", ["on", "off"], "sound effects on freezes and clones"),
}

OPTIONAL = set()  # every question is asked

# fraction of the frame kept free: top, bottom, left, right (the app's buttons, captions and description)
SAFE = {
    ("tiktok", "9:16"): (0.10, 0.34, 0.05, 0.15),   # right-hand buttons, caption + description at the bottom
    ("reels", "9:16"): (0.10, 0.32, 0.05, 0.14),
    ("shorts", "9:16"): (0.10, 0.30, 0.05, 0.13),
    ("youtube", "16:9"): (0.06, 0.18, 0.02, 0.02),  # caption band at the bottom
}


def safe_area(platform, shape):
    if (platform, shape) in SAFE:
        return SAFE[(platform, shape)]
    if shape == "9:16":
        return SAFE[("tiktok", "9:16")]          # strictest vertical one
    if shape == "1:1":
        return (0.06, 0.20, 0.05, 0.05)
    return SAFE[("youtube", "16:9")]


def path():
    return Path(os.environ.get("TACH_NGUOI_SETTINGS") or (Path.cwd() / "tach-nguoi.settings.json"))


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
        if k in ("color", "accent") and not (v.startswith("#") and len(v) == 7):
            raise SystemExit(f"'{k}' must be a colour like #ffd400")
        cur[k] = v
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def apply(item, s, keys):
    """Fill missing plan fields from the saved settings."""
    for k in keys:
        if k == "accent":
            continue
        item.setdefault(k, s[k])
    return item
