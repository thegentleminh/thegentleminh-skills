"""'Show all for comparison' for the setup phase: every option of one setting side by side, on the user's
own clip, low resolution, a few seconds, labelled in Vietnamese. MIT licence.
"""
import unicodedata
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import tn_freeze
import tn_io
import tn_settings
import tn_sfx
import tn_text

LABELS = {
    "font": {"cao": "Chữ cao, gọn", "dam": "Chữ đậm", "dam-vua": "Đậm vừa"},
    "cover": {"light": "Che ít (luôn dễ đọc)", "medium": "Che vừa", "bold": "Che nhiều (kiểu trend)"},
    "anim": {"rise": "Trồi lên", "pop": "Bật ra", "letters": "Hiện từng chữ cái", "none": "Hiện luôn"},
    "outline": {"white": "Viền trắng", "glow": "Viền phát sáng", "none": "Không viền"},
    "platform": {"tiktok": "TikTok", "shorts": "YouTube Shorts", "reels": "Reels", "youtube": "YouTube (ngang)"},
    "sfx": {"whoosh": "Vút", "hit": "Bụp", "shutter": "Tách (máy ảnh)", "flash": "Xẹt"},
}
COLOR_NAMES = {"#ffffff": "Trắng", "#ffd400": "Vàng", "#111111": "Đen"}
KINDS = ("font", "color", "cover", "anim", "outline", "platform", "sfx")


def label(img, text):
    """Dark box + label in the top-left corner (Vietnamese-safe font)."""
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    size = max(14, int(min(img.shape[:2]) * 0.06))
    f = ImageFont.truetype(str(tn_text.font_path("dam-vua")), size)
    text = unicodedata.normalize("NFC", text)
    bb = d.textbbox((0, 0), text, font=f)
    pad = size // 3
    d.rectangle([0, 0, bb[2] + 2 * pad, bb[3] + 2 * pad], fill=(10, 12, 14))
    d.text((pad, pad), text, font=f, fill=(255, 255, 255))
    return np.asarray(im)


def tile(panels, landscape, original=None):
    """Grid of equal panels: 2 columns for landscape, one row for vertical. A spare cell shows the original."""
    cols = 2 if landscape else len(panels)
    rows = []
    blank = label(original, "Video gốc") if original is not None else np.zeros_like(panels[0])
    for i in range(0, len(panels), cols):
        row = panels[i:i + cols] + [blank] * (cols - len(panels[i:i + cols]))
        rows.append(np.hstack(row))
    return np.vstack(rows)


def run(kind, clip, matte, meta, out, at=None, text=None, tn=None):
    """tn: the tn module (placement and render helpers)."""
    s = tn_settings.load()
    W, H, fps = meta["w"], meta["h"], meta["fps"]
    landscape = W >= H
    if landscape:
        pw = 640
        ph = int(round(H * pw / W)) // 2 * 2
    else:
        ph = 640
        pw = int(round(W * ph / H)) // 2 * 2
    scale = pw / W
    dur = 3.4
    if at is None:
        at = max(0.3, min(meta["duration"] / 2 - dur / 2, meta["duration"] - dur - 0.3))
    t0, t1 = at, min(meta["duration"] - 0.05, at + dur)
    word = text or "Bí mật"

    if kind in ("font", "color", "cover", "anim"):
        if kind == "color":
            opts = list(dict.fromkeys(["#ffffff", "#ffd400", "#111111", s["color"], s["accent"]]))[:4]
            names = {c: COLOR_NAMES.get(c, f"Màu {c}") for c in opts}
        else:
            opts = tn_settings.OPTIONS[kind][1]
            names = LABELS[kind]
        clips = []
        for o in opts:
            it = {"text": word, "start": t0 + 0.25, "end": t1 - 0.1}
            tn_settings.apply(it, s, ("font", "color", "cover", "anim", "platform"))
            it[kind] = o
            placed = tn.place_items(clip, [it], meta, matte, quiet=True)
            frames = [label(f, names[o]) for f in tn.behind_frames(clip, matte, [it], placed, fps, (pw, ph), scale, t0, t1)]
            clips.append(frames)
        n = min(len(c) for c in clips)
        orig = list(tn_io.Reader(clip, size=(pw, ph), start=t0, frames=n)) if landscape and len(clips) % 2 else None
        frames = [tile([c[i] for c in clips], landscape, orig[i] if orig else None) for i in range(n)]
        audio = None
    elif kind == "outline":
        rf = list(tn_io.Reader(clip, size=(pw, ph), start=max(0, at - 0.25), frames=int(0.5 * fps) + 1))
        ra = list(tn_io.Reader(matte, size=(pw, ph), gray=True, start=max(0, at - 0.25), frames=int(0.5 * fps) + 1))
        k = tn_freeze.sharpest(rf, ra)
        clips = []
        for o in tn_settings.OPTIONS["outline"][1]:
            it = {"effect": "intro", "name": text or "Tên của bạn", "role": "Vai trò của bạn", "outline": o,
                  "color": s["accent"], "platform": s["platform"]}
            stt = tn_freeze.prepare("intro", rf[k], ra[k], it)
            hold = 2.4
            clips.append([label(tn_freeze.render("intro", stt, i / fps, hold, it), LABELS["outline"][o]) for i in range(int(hold * fps))])
        frames = [tile([c[i] for c in clips], landscape, rf[k]) for i in range(len(clips[0]))]
        audio = None
    elif kind == "platform":
        fr = next(iter(tn_io.Reader(clip, size=(pw, ph), start=at, frames=1)))
        r = W / H
        shape = "9:16" if r < 0.8 else ("1:1" if r < 1.25 else "16:9")
        panels = []
        opts = ["youtube"] if shape == "16:9" else ["tiktok", "shorts", "reels"]  # only the ones this shape is posted to
        for o in opts:
            top, bottom, left, right = tn_settings.safe_area(o, shape)
            img = fr.astype(np.float32)
            m = np.zeros((ph, pw), bool)
            m[:int(top * ph)] = m[int((1 - bottom) * ph):] = True
            m[:, :int(left * pw)] = m[:, int((1 - right) * pw):] = True
            img[m] = img[m] * 0.45 + np.float32([200, 40, 40]) * 0.55  # red = covered by the app: no text there
            panels.append(label(img.astype(np.uint8), LABELS["platform"][o]))
        frames = [tile(panels, landscape)] * int(2.5 * fps)
        audio = None
    elif kind == "sfx":
        names = list(LABELS["sfx"])
        sr = tn_sfx.SR
        each = 1.2
        track = np.zeros((int(each * len(names) * sr), 2), np.float32)
        frames = []
        bg = next(iter(tn_io.Reader(clip, size=(pw, ph), start=at, frames=1)))
        for i, nme in enumerate(names):
            tn_sfx.mix_into(track, tn_sfx.SOUNDS[nme](), i * each + 0.2, 1.0)
            card = label((bg * 0.35).astype(np.uint8), f"{i + 1}/{len(names)}  {LABELS['sfx'][nme]}")
            frames += [card] * int(each * fps)
        audio = out.with_suffix(".wav")
        with wave.open(str(audio), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(track, -1, 1) * 32767).astype("<i2").tobytes())
    else:
        raise SystemExit(f"Nothing to compare for '{kind}'. Use one of: {', '.join(KINDS)}")

    h, w = frames[0].shape[:2]
    wr = tn_io.Writer(out, w - w % 2, h - h % 2, fps, audio_from=audio, preset="veryfast", crf=23)
    for f in frames:
        wr.write(f[:h - h % 2, :w - w % 2])
    wr.close()
    return out
