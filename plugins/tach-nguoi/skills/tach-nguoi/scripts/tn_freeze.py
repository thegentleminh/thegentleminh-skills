"""Freeze-frame effects for tach-nguoi: character intro (cut-out + outline + name card), photo snap, comic freeze.
MIT licence.

Each effect is a pure function of (frozen frame, person matte, time into the hold) -> RGB frame, so stills,
previews and full renders all come from the same code. Heavy per-freeze work (blur, comic filter, card) is
done once in `prepare` and reused for every frame of the hold.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import tn_settings
import tn_text

EFFECTS = ("intro", "snap", "comic")
SFX = {  # sounds per effect: (name, seconds into the hold, gain)
    "intro": [("flash", 0.0, 0.8), ("whoosh", 0.02, 1.0), ("hit", 0.18, 1.0)],
    "snap": [("shutter", 0.0, 1.0), ("flash", 0.0, 0.6)],
    "comic": [("hit", 0.0, 0.9), ("whoosh", 0.05, 0.6)],
}


def ease_out_cubic(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.7):
    x = min(max(x, 0.0), 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def f32(img):
    return img.astype(np.float32) / 255


def u8(img):
    return np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)


def person_box(alpha):
    ys, xs = np.nonzero(alpha > 0.5)
    if not len(xs):
        h, w = alpha.shape
        return w * 0.3, h * 0.2, w * 0.7, h
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def sharpest(frames, alphas):
    """Index of the frame whose person region is sharpest (least motion blur): the frame to freeze on."""
    best, bi = -1.0, 0
    for i, (fr, al) in enumerate(zip(frames, alphas)):
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        lap = cv2.Laplacian(g, cv2.CV_32F)
        m = al > 128
        v = float(lap[m].var()) if m.sum() > 500 else 0.0
        if v > best:
            best, bi = v, i
    return bi


def _text_rgba(text, font, size, color):
    f = ImageFont.truetype(str(tn_text.font_path(font)), size)
    bb = f.getbbox(text)
    w, h = bb[2] - bb[0] + size // 4, bb[3] - bb[1] + size // 4
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-bb[0] + size // 8, -bb[1] + size // 8), text, font=f, fill=tn_text.hex_rgb(color) + (255,))
    return np.asarray(im, np.float32) / 255


def name_card(name, role, H, accent, font_name="dam", font_role="dam-vua"):
    """Name (big, white) + role (smaller, accent colour) with an accent bar on the left. RGBA float."""
    import unicodedata
    name, role = unicodedata.normalize("NFC", name or ""), unicodedata.normalize("NFC", role or "")
    n = _text_rgba(name.upper(), font_name, int(H * 0.105), "#ffffff") if name else None
    r = _text_rgba(role, font_role, int(H * 0.05), accent) if role else None
    parts = [p for p in (n, r) if p is not None]
    gap = int(H * 0.008)
    bar_w, pad = max(4, int(H * 0.011)), int(H * 0.022)
    w = max(p.shape[1] for p in parts) + bar_w + pad
    h = sum(p.shape[0] for p in parts) + gap * (len(parts) - 1)
    card = np.zeros((h, w, 4), np.float32)
    rgb = np.array(tn_text.hex_rgb(accent), np.float32) / 255
    card[:, :bar_w, :3], card[:, :bar_w, 3] = rgb, 1.0
    y = 0
    for p in parts:
        ph, pw = p.shape[:2]
        card[y:y + ph, bar_w + pad:bar_w + pad + pw] = p
        y += ph + gap
    # soft dark glow so white text reads on any background
    k = max(3, int(H * 0.03) | 1)
    glow = cv2.GaussianBlur(card[..., 3], (k, k), 0) * 0.55
    a = card[..., 3] + glow * (1 - card[..., 3])
    rgb_out = card[..., :3] * card[..., 3:4] / np.maximum(a[..., None], 1e-6)
    return np.dstack([rgb_out, a])


def over(dst, rgba, x, y, alpha=1.0):
    """Paste RGBA float onto RGB float dst at (x, y), clipped to the frame."""
    h, w = rgba.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return dst
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] * alpha
    dst[y0:y1, x0:x1] = src[..., :3] * a + dst[y0:y1, x0:x1] * (1 - a)
    return dst


def comic_filter(rgb):
    """Comic-book look without any AI model: flat colours, ink lines, halftone dots in the shadows."""
    H, W = rgb.shape[:2]
    s = 960 / max(H, W)
    small = cv2.resize(rgb, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    flat = small
    for _ in range(3):
        flat = cv2.bilateralFilter(flat, 9, 60, 60)
    data = flat.reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lab, cen = cv2.kmeans(data[::7], 9, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    d = ((data[:, None, :] - cen[None]) ** 2).sum(-1)
    flat = cen[d.argmin(1)].reshape(flat.shape).astype(np.uint8)
    hsv = cv2.cvtColor(flat, cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1].astype(np.int16) * 13 // 10, 0, 255).astype(np.uint8)  # punchier colour
    flat = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    flat = cv2.resize(flat, (W, H), interpolation=cv2.INTER_NEAREST)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.medianBlur(gray, 7)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 5)
    ink = cv2.erode(ink, np.ones((2, 2), np.uint8)) if H >= 900 else ink
    out = f32(flat) * (f32(ink)[..., None] * 0.92 + 0.08)
    # halftone: dot size follows darkness, on a grid
    cell = max(6, int(H / 120))
    lum = cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    cl = cv2.resize(lum, (W // cell + 1, H // cell + 1), interpolation=cv2.INTER_AREA)
    r = np.clip((0.55 - cl) / 0.55, 0, 1) * cell * 0.55
    rmap = cv2.resize(r, (W, H), interpolation=cv2.INTER_NEAREST)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.hypot((xx % cell) - cell / 2, (yy % cell) - cell / 2)
    dots = (dist < rmap).astype(np.float32) * 0.45
    return np.clip(out * (1 - dots[..., None]), 0, 1)


def speed_lines(H, W, cx, cy, seed):
    """Radial black wedges from the frame edge toward the person (anime/comic 'shock' lines). Alpha 0-1."""
    rng = np.random.default_rng(seed)
    m = np.zeros((H, W), np.uint8)
    R = math.hypot(W, H)
    for ang in np.sort(rng.uniform(0, 2 * math.pi, 70)):
        inner = rng.uniform(0.32, 0.5) * R
        wdt = rng.uniform(0.004, 0.012)
        p = [(cx + math.cos(ang - wdt) * R, cy + math.sin(ang - wdt) * R),
             (cx + math.cos(ang + wdt) * R, cy + math.sin(ang + wdt) * R),
             (cx + math.cos(ang) * inner, cy + math.sin(ang) * inner)]
        cv2.fillConvexPoly(m, np.int32(p), 255, cv2.LINE_AA)
    return m.astype(np.float32) / 255


def prepare(effect, frame, alpha_u8, item):
    """Work done once per freeze: blurred background, outline, comic filter, card."""
    H, W = frame.shape[:2]
    a = alpha_u8.astype(np.float32) / 255
    f = f32(frame)
    st = {"f": f, "a": a, "W": W, "H": H, "box": person_box(a)}
    if effect == "intro":
        k = max(3, int(H * 0.035) | 1)
        bg = cv2.GaussianBlur(f, (k, k), 0)
        gray = bg.mean(axis=2, keepdims=True)
        st["bg"] = (gray * 0.7 + bg * 0.3) * 0.42             # darker, mostly grey: the person pops
        r = max(2, int(H * float(item.get("outline_px", 0.006))))
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        st["stroke"] = cv2.GaussianBlur(cv2.dilate(a, ker), (3, 3), 0)
        style = item.get("outline", "white")
        st["outline"] = style
        col = item.get("color", "#ffd400")
        if style == "glow":
            kk = max(5, int(H * 0.03) | 1)
            st["glow"] = np.clip(cv2.GaussianBlur(cv2.dilate(a, ker), (kk, kk), 0) * 1.6, 0, 1)
        st["accent"] = np.array(tn_text.hex_rgb(col), np.float32) / 255
        x0, y0, x1, y1 = st["box"]
        # card size follows the short side, so 9:16 cards aren't huge; it stays inside the platform's safe area
        st["card"] = name_card(item.get("name", ""), item.get("role", ""), min(W, H) * (1.0 if W >= H else 1.25), col) \
            if (item.get("name") or item.get("role")) else None
        st["card_side"] = "right" if (x0 + x1) / 2 < W / 2 else "left"
        r = W / H
        shape = "9:16" if r < 0.8 else ("1:1" if r < 1.25 else "16:9")
        top, bottom, left, right = tn_settings.safe_area(item.get("platform", "tiktok"), shape)
        st["safe"] = (top, bottom, left, right)
        if st["card"] is not None:
            ch = st["card"].shape[0]
            st["card_y"] = int(min(0.60 * H - ch / 2, (1 - bottom) * H - ch))
    elif effect == "snap":
        k = max(3, int(H * 0.05) | 1)
        st["bg"] = cv2.GaussianBlur(f, (k, k), 0) * 0.55
    elif effect == "comic":
        st["comic"] = comic_filter(frame)
        x0, y0, x1, y1 = st["box"]
        st["center"] = ((x0 + x1) / 2, y0 + (y1 - y0) * 0.3)
        cap = item.get("caption")
        if cap:
            import unicodedata
            t = _text_rgba(unicodedata.normalize("NFC", cap), "dam", int(H * 0.06), "#111111")
            pad = int(H * 0.02)
            box = np.ones((t.shape[0] + 2 * pad, t.shape[1] + 2 * pad, 3), np.float32)
            box[...] = np.array(tn_text.hex_rgb(item.get("color", "#ffe14d")), np.float32) / 255
            bw = max(3, int(H * 0.005))
            box[:bw], box[-bw:], box[:, :bw], box[:, -bw:] = 0.07, 0.07, 0.07, 0.07
            over(box, t, pad, pad)
            st["caption"] = np.dstack([box, np.ones(box.shape[:2], np.float32)])
    return st


def _scale_about(img, s, cx, cy, W, H, border=0):
    m = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
    return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def render(effect, st, u, hold, item):
    """Frame u seconds into a hold of `hold` seconds. Returns RGB uint8."""
    W, H, f, a = st["W"], st["H"], st["f"], st["a"]
    fade_out = 1.0 if hold - u > 0.15 else max(0.0, (hold - u) / 0.15)
    if effect == "intro":
        k_in = ease_out_cubic(u / 0.22) * fade_out
        img = f * (1 - k_in) + st["bg"] * k_in
        x0, y0, x1, y1 = st["box"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        s = 1 + (float(item.get("pop", 0.06)) * ease_out_back(u / 0.32) + 0.012 * u / hold) * fade_out
        a_s = _scale_about(a, s, cx, cy, W, H)
        f_s = _scale_about(f, s, cx, cy, W, H)
        if st["outline"] != "none":
            sk = _scale_about(st["stroke"], s, cx, cy, W, H) * k_in
            if st["outline"] == "glow":
                g = _scale_about(st["glow"], s, cx, cy, W, H)[..., None] * k_in
                img = img * (1 - g) + st["accent"] * g
                img = img * (1 - sk[..., None]) + np.float32([1, 1, 1]) * sk[..., None]
            else:
                img = img * (1 - sk[..., None]) + 1.0 * sk[..., None]
        img = img * (1 - a_s[..., None]) + f_s * a_s[..., None]
        if st["card"] is not None:
            e = ease_out_cubic((u - 0.18) / 0.35)
            if e > 0:
                c = st["card"]
                ch, cw = c.shape[:2]
                _, _, sl, sr = st["safe"]
                y = st["card_y"]
                tx = (W - int(W * max(sr, 0.05)) - cw) if st["card_side"] == "right" else int(W * max(sl, 0.05))
                tx = max(0, min(tx, W - cw))
                dx = int((1 - e) * W * 0.12) * (1 if st["card_side"] == "right" else -1)
                img = over(img, c, tx + dx, y, alpha=min(1.0, e * 1.3) * fade_out)
        fl = max(0.0, 1 - u / 0.14) * 0.75                       # white flash on the freeze
        img = img * (1 - fl) + fl
        return u8(img)
    if effect == "snap":
        k_in = ease_out_cubic(u / 0.25) * fade_out
        s = 1 - 0.16 * k_in                                     # the picture shrinks into a printed photo
        rot = -3.0 * k_in
        border = int(H * 0.025)
        photo = cv2.copyMakeBorder(f, border, border, border, border, cv2.BORDER_CONSTANT, value=(1, 1, 1))
        ph, pw = photo.shape[:2]
        m = cv2.getRotationMatrix2D((pw / 2, ph / 2), rot, s * (1 + 0.02 * u / hold))
        m[0, 2] += W / 2 - pw / 2
        m[1, 2] += H / 2 - ph / 2
        mask = cv2.warpAffine(np.ones((ph, pw), np.float32), m, (W, H))
        pic = cv2.warpAffine(photo, m, (W, H))
        sh = cv2.GaussianBlur(cv2.warpAffine(np.ones((ph, pw), np.float32), m + np.float32([[0, 0, H * 0.012], [0, 0, H * 0.018]]), (W, H)),
                              (max(3, int(H * 0.03) | 1),) * 2, 0) * 0.6 * k_in
        bg = f * (1 - k_in) + st["bg"] * k_in
        img = bg * (1 - sh[..., None])
        img = img * (1 - mask[..., None]) + pic * mask[..., None]
        fl = max(0.0, 1 - u / 0.22)
        img = img * (1 - fl) + fl
        return u8(img)
    if effect == "comic":
        k_in = fade_out
        s = 1 + 0.05 * ease_out_back(u / 0.25) * fade_out
        cx, cy = st["center"]
        cm = _scale_about(st["comic"], s, cx, cy, W, H)
        a_s = _scale_about(a, s, cx, cy, W, H)
        lines = speed_lines(H, W, cx, cy, seed=int(u * 12))     # redraw 12x a second: the lines flicker
        img = cm * (1 - (lines * (1 - a_s))[..., None] * 0.9)
        bw = max(4, int(H * 0.012))
        img[:bw], img[-bw:], img[:, :bw], img[:, -bw:] = 0.05, 0.05, 0.05, 0.05
        if "caption" in st:
            e = ease_out_back((u - 0.12) / 0.25)
            if e > 0:
                cap = st["caption"]
                ch, cw = cap.shape[:2]
                sc = max(0.01, e)
                c2 = cv2.resize(cap, (max(1, int(cw * sc)), max(1, int(ch * sc))))
                x = int(W * 0.06 + cw * (1 - sc) / 2)
                y = int(H * 0.07 + ch * (1 - sc) / 2)
                img = over(img, c2, x, y)
        img = f * (1 - k_in) + img * k_in
        fl = max(0.0, 1 - u / 0.1) * 0.8
        img = img * (1 - fl) + fl
        return u8(img)
    raise ValueError(effect)
