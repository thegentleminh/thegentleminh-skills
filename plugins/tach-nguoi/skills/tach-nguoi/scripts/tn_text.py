"""Text layer for tach-nguoi: Vietnamese-safe text as per-letter sprites, entrance/exit animation. MIT licence.

A text block is rendered once into letter sprites (so letters can animate one by one). Each frame
builds a small local canvas from the sprites, then one affine warp places it in the full frame.
"""
import math
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
FONTS = {  # look name -> file (all SIL Open Font License, Vietnamese complete)
    "dam": "BeVietnamPro-Black.ttf",        # heavy, clean
    "dam-vua": "BeVietnamPro-ExtraBold.ttf",
    "cao": "Anton-Regular.ttf",             # tall condensed, the classic "text behind" look
}


def font_path(name):
    if name in FONTS:
        return FONT_DIR / FONTS[name]
    p = Path(name)
    if p.exists():
        return p
    raise SystemExit(f"Font '{name}' not found. Use one of {', '.join(FONTS)} or a path to a .ttf/.otf file.")


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


class TextBlock:
    """One or more lines of text, centred, as letter sprites in a local canvas (RGBA float 0-1)."""

    def __init__(self, text, font, size_px, color="#ffffff", tracking=0.0, line_gap=0.05, upper=False):
        text = unicodedata.normalize("NFC", text)  # decomposed marks (e.g. typed on a Mac) -> one glyph each
        if upper:
            text = text.upper()
        self.text = text
        f = ImageFont.truetype(str(font_path(font)), size_px)
        rgb = hex_rgb(color)
        lines = text.split("\n")
        asc, desc = f.getmetrics()
        # Vietnamese capitals stack marks above the cap height (Ầ, Ỗ): measure the real ink, not the metrics
        probe = "ẦỖỮẪỄÂÊÔ" + "".join(lines)
        bb = f.getbbox(probe)
        top_extra = max(0, -bb[1])
        line_h = asc + desc + top_extra
        gap = int(line_gap * size_px)
        pad = int(size_px * 0.25)
        widths = [self._width(f, ln, tracking, size_px) for ln in lines]
        W = max(widths) + 2 * pad
        H = len(lines) * line_h + (len(lines) - 1) * gap + 2 * pad
        self.sprites = []  # (rgba crop, x, y, index)
        idx = 0
        for li, ln in enumerate(lines):
            x = pad + (max(widths) - widths[li]) / 2
            y = pad + li * (line_h + gap) + top_extra
            for ch in ln:
                adv = f.getlength(ch) + tracking * size_px
                if not ch.isspace():
                    im = Image.new("L", (int(adv + size_px), line_h + size_px // 2), 0)
                    ImageDraw.Draw(im).text((size_px // 4, top_extra), ch, font=f, fill=255)
                    a = np.asarray(im, np.float32) / 255.0
                    ys, xs = np.nonzero(a > 0.01)
                    if len(xs):
                        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
                        crop = a[y0:y1, x0:x1]
                        rgba = np.dstack([np.broadcast_to(np.array(rgb, np.float32) / 255, crop.shape + (3,)), crop])
                        self.sprites.append((rgba, int(round(x - size_px // 4 + x0)), int(round(y - top_extra + y0)), idx))
                        idx += 1
                x += adv
        self.n_letters = idx
        # per letter: (word number, position in word, word length): readers fill in a hidden middle letter, not an end one
        self.letter_info = []
        for wi, word in enumerate(w for ln in lines for w in ln.split()):
            for k in range(len(word)):
                self.letter_info.append((wi, k, len(word)))
        self.W, self.H = int(W), int(H)
        self.size_px = size_px

    @staticmethod
    def _width(f, line, tracking, size_px):
        return int(sum(f.getlength(c) + tracking * size_px for c in line) - tracking * size_px)

    def labels(self):
        """Local map of which letter owns each pixel (-1 = none), for per-letter readability checks."""
        lab = np.full((self.H, self.W), -1, np.int16)
        best = np.zeros((self.H, self.W), np.float32)
        for rgba, x, y, i in self.sprites:
            h, w = rgba.shape[:2]
            a = rgba[..., 3]
            sub_b, sub_l = best[y:y + h, x:x + w], lab[y:y + h, x:x + w]
            a = a[:sub_b.shape[0], :sub_b.shape[1]]
            m = (a > 0.5) & (a > sub_b)
            sub_l[m], sub_b[m] = i, a[m]
        return lab

    def canvas(self, letter_alpha=None, letter_dy=None, shadow=0.0):
        """Local RGBA canvas. letter_alpha/letter_dy: per-letter arrays (None = all 1 / 0)."""
        c = np.zeros((self.H, self.W, 4), np.float32)
        for rgba, x, y, i in self.sprites:
            la = 1.0 if letter_alpha is None else float(letter_alpha[i])
            if la <= 0:
                continue
            dy = 0 if letter_dy is None else int(round(letter_dy[i]))
            h, w = rgba.shape[:2]
            y0, x0 = max(0, y + dy), max(0, x)
            y1, x1 = min(self.H, y + dy + h), min(self.W, x + w)
            if y1 <= y0 or x1 <= x0:
                continue
            src = rgba[y0 - (y + dy):y1 - (y + dy), x0 - x:x1 - x]
            a = src[..., 3:4] * la
            dst = c[y0:y1, x0:x1]
            dst[..., :3] = src[..., :3] * a + dst[..., :3] * (1 - a)
            dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)
        if shadow > 0:  # soft dark glow under the letters, part of the text layer (so it also sits behind the person)
            k = max(3, int(self.size_px * 0.12) | 1)
            sh = cv2.GaussianBlur(c[..., 3], (k, k), 0) * shadow
            out_a = c[..., 3] + sh * (1 - c[..., 3])
            rgb = c[..., :3] * c[..., 3:4] / np.maximum(out_a[..., None], 1e-6)
            c = np.dstack([rgb, out_a])
        return c


def ease_out_cubic(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.6):
    x = min(max(x, 0.0), 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


ANIMS = ("rise", "pop", "letters", "none")


def anim_state(anim, t, start, end, n_letters, size_px, intro=0.45, outro=0.25, drift=0.03):
    """Returns (block_alpha, scale, dy_px, letter_alpha, letter_dy) at time t, or None when hidden."""
    if t < start or t > end:
        return None
    u = t - start
    out = 1.0 if end - t >= outro else max(0.0, (end - t) / outro)
    life = (t - start) / max(end - start, 1e-6)
    scale = 1.0 + drift * life  # slow push so the word never looks pasted on
    la = ldy = None
    if anim == "rise":
        e = ease_out_cubic(u / intro)
        return e * out, scale, (1 - e) * 0.18 * size_px, None, None
    if anim == "pop":
        e = ease_out_back(u / (intro * 0.8))
        return min(1.0, u / 0.12) * out, scale * (0.82 + 0.18 * e), 0.0, None, None
    if anim == "letters":
        step = min(0.06, intro * 1.6 / max(n_letters, 1))
        la = np.array([ease_out_cubic((u - i * step) / 0.22) for i in range(n_letters)], np.float32)
        ldy = (1 - la) * 0.14 * size_px
        return out, scale, 0.0, la, ldy
    return out, scale, 0.0, la, ldy


def place(canvas, frame_w, frame_h, cx, cy, scale, dy):
    """Warp the local canvas into a full-frame RGBA layer centred at (cx, cy)."""
    h, w = canvas.shape[:2]
    m = np.float32([[scale, 0, cx - scale * w / 2], [0, scale, cy - scale * h / 2 + dy]])
    return cv2.warpAffine(canvas, m, (frame_w, frame_h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))


def fit_size(text, font, target_w, upper=False, tracking=0.0):
    """Font size (px) whose widest line is target_w pixels."""
    text = unicodedata.normalize("NFC", text.upper() if upper else text)
    fp = str(font_path(font))
    lo, hi = 8, 2000
    while hi - lo > 1:  # measure widths only; building the letter sprites at every step was the slow part
        mid = (lo + hi) // 2
        f = ImageFont.truetype(fp, mid)
        w = max(TextBlock._width(f, ln, tracking, mid) for ln in text.split("\n"))
        if w > target_w:
            hi = mid
        else:
            lo = mid
    return lo
