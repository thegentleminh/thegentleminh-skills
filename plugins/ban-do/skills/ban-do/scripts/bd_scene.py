"""Scene for ban-do: read the JSON, move the camera, draw one frame.

Drawing: map shapes at 2x then scaled down (smooth edges), text at final size.
"""
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import bd_geo as geo

FONT = Path(__file__).resolve().parent.parent / "fonts" / "BeVietnamPro-ExtraBold.ttf"
SS = 2  # supersampling for shapes

THEMES = {
    "dem": {   # dark
        "ocean_top": (9, 24, 38), "ocean_bot": (14, 42, 64), "grid": (22, 50, 72),
        "land": (44, 60, 74), "border": (84, 104, 120), "dim": (28, 38, 48),
        "tint": (255, 200, 70), "edge": (255, 240, 190), "pin": (255, 77, 77),
        "text": (255, 255, 255), "stroke": (8, 18, 28), "sea": (120, 170, 205),
        "island": (150, 175, 195), "number": (255, 214, 74), "pill": (12, 24, 36), "vignette": 0.35,
    },
    "sang": {  # light
        "ocean_top": (186, 215, 230), "ocean_bot": (214, 233, 242), "grid": (200, 224, 236),
        "land": (244, 239, 228), "border": (184, 174, 156), "dim": (222, 222, 218),
        "tint": (232, 71, 60), "edge": (150, 30, 22), "pin": (215, 38, 38),
        "text": (24, 34, 44), "stroke": (255, 255, 255), "sea": (70, 120, 150),
        "island": (120, 120, 110), "number": (200, 40, 30), "pill": (255, 255, 255), "vignette": 0.0,
    },
}

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}

STYLE_ALIASES = {"to": "tint", "tint": "tint", "vien": "outline", "outline": "outline",
                 "noi-bat": "spotlight", "noibat": "spotlight", "spotlight": "spotlight"}

FORBIDDEN = [  # wrong names for Vietnam's sea and islands (checked without tone marks too)
    "south china sea", "bien nam trung hoa", "nam trung hoa", "paracel", "spratly",
    "xisha", "nansha", "sansha",
]
FORBIDDEN_TONED = ["tây sa", "nam sa"]


def nfc(s):
    return unicodedata.normalize("NFC", str(s))


def hexcolor(c, default):
    if not c:
        return default
    if isinstance(c, (list, tuple)):
        return tuple(int(v) for v in c[:3])
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ease(u, kind="inOut"):
    u = min(1.0, max(0.0, u))
    if kind == "linear":
        return u
    if kind == "in":
        return u * u * u
    if kind == "out":
        return 1 - (1 - u) ** 3
    return 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def out_back(u):
    u = min(1.0, max(0.0, u))
    c1, c3 = 1.7, 2.7
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def fade(t, t0, t1=None, d=0.4):
    if t0 is None:
        t0 = 0
    a = ease((t - t0) / d, "out") if d > 0 else float(t >= t0)
    if t1 is not None:
        a = min(a, ease((t1 - t) / d, "in") if t < t1 else 0.0)
    return max(0.0, min(1.0, a))


_fonts = {}


def font(px):
    px = max(8, int(round(px)))
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(str(FONT), px)
    return _fonts[px]


def fmt_number(v, decimals=0, lang="vi"):
    s = f"{abs(v):,.{decimals}f}"
    if lang == "vi":
        s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return ("-" if v < 0 else "") + s


class SceneError(Exception):
    pass


class Scene:
    def __init__(self, spec, world, preview=False):
        self.spec = spec
        self.w = world
        aspect = spec.get("aspect", spec.get("khung", "9:16"))
        if aspect not in ASPECTS:
            raise SceneError(f"aspect phải là một trong {list(ASPECTS)} (đang là {aspect!r})")
        self.aspect = aspect
        W, H = ASPECTS[aspect]
        if preview:
            W, H = W // 2, H // 2
        self.W, self.H = W, H
        self.u = min(W, H) / 1080.0           # text scale
        self.fps = int(spec.get("fps", 30))
        self.lang = spec.get("lang", "vi")
        self.th = dict(THEMES.get(spec.get("theme", "dem"), THEMES["dem"]))
        if spec.get("color"):
            self.th["tint"] = hexcolor(spec["color"], self.th["tint"])
        self.vertical = H > W
        # where the map subject sits: clear of the title and of app buttons at the bottom
        self.safe = (0.06, 0.12, 0.94, 0.78) if self.vertical else (0.05, 0.13, 0.95, 0.90)
        self.keys = [self._key(k) for k in spec.get("camera", [])]
        if not self.keys:
            raise SceneError("camera trống: cần ít nhất một khung (ví dụ {\"t\": 0, \"fit\": \"VNM\"})")
        self.keys.sort(key=lambda k: k["t"])
        last = self.keys[-1]["t"]
        self.duration = float(spec.get("duration", last + 2.0))
        self.highlights = [self._highlight(h) for h in spec.get("highlight", [])]
        self.pins = [self._pin(p) for p in spec.get("pins", [])]
        self.numbers = [self._number(n) for n in spec.get("numbers", [])]
        self.titles = [self._title(x) for x in spec.get("title", [])] if isinstance(spec.get("title"), list) \
            else ([self._title({"text": spec["title"]})] if spec.get("title") else [])
        self.labels = [self._label(x) for x in spec.get("labels", [])]
        self.show_country_names = spec.get("country_names", True)
        self.vn_extras = True   # Hoàng Sa, Trường Sa, Biển Đông: always on
        self._bg = None
        self._vig = None

    # ---------- parsing ----------
    def _lonlat(self, d, what):
        if "lon" in d and "lat" in d:
            return float(d["lon"]), float(d["lat"])
        if d.get("place"):
            p = self.w.place(d["place"])
            if not p:
                c = self.w.country(d["place"])
                if c and c["label"][0] is not None:
                    return float(c["label"][0]), float(c["label"][1])
                raise SceneError(f"{what}: không tìm thấy nơi {d['place']!r}. Thử: python bando.py find \"{d['place']}\" "
                                 "hoặc ghi lon/lat")
            return float(p["lon"]), float(p["lat"])
        raise SceneError(f"{what}: cần place hoặc lon + lat")

    def _fit(self, bbox, pad):
        x0, y0, x1, y1 = bbox
        sx0, sy0, sx1, sy1 = self.safe
        bw, bh = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
        fw, fh = (sx1 - sx0), (sy1 - sy0)       # fractions of the frame
        span = max(bw / fw, bh / fh * self.W / self.H)
        # put the box centre at the safe-area centre
        k = self.W / span
        cx = (x0 + x1) / 2 - ((sx0 + sx1) / 2 - 0.5) * self.W / k
        cy = (y0 + y1) / 2 + ((sy0 + sy1) / 2 - 0.5) * self.H / k
        return cx, cy, span

    def _key(self, k):
        t = float(k.get("t", 0))
        pad = float(k.get("pad", 0.08))
        if k.get("view"):
            r = geo.region(k["view"])
            if not r:
                raise SceneError(f"camera: không biết vùng {k['view']!r}. Có: {', '.join(geo.REGIONS)}")
            x0, y0 = geo.merc(r[0], r[1])
            x1, y1 = geo.merc(r[2], r[3])
            cx, cy, span = self._fit((x0, y0, x1, y1), 0.0)
        elif k.get("fit"):
            c = self.w.country(k["fit"])
            if not c:
                raise SceneError(f"camera: không tìm thấy nước {k['fit']!r}. Thử: python bando.py find \"{k['fit']}\"")
            cx, cy, span = self._fit(self.w.fit_bbox(c), pad)
        else:
            lon, lat = self._lonlat(k, "camera")
            if "span_km" in k:
                deg = float(k["span_km"]) / (111.32 * math.cos(math.radians(lat)))
            else:
                deg = float(k.get("span", 6))
            mx, my = geo.merc(lon, lat)
            cx, cy, span = float(mx), float(my), math.radians(deg)
        return {"t": t, "cx": float(cx), "cy": float(cy), "span": float(span), "ease": k.get("ease", "inOut")}

    def _highlight(self, h):
        c = self.w.country(h.get("country"))
        if not c:
            raise SceneError(f"highlight: không tìm thấy nước {h.get('country')!r}")
        style = STYLE_ALIASES.get(str(h.get("style", "tint")).lower())
        if not style:
            raise SceneError(f"highlight style: tint | outline | spotlight (đang là {h.get('style')!r})")
        return {"c": c, "t0": float(h.get("t0", 0)), "t1": h.get("t1"), "style": style,
                "color": hexcolor(h.get("color"), self.th["tint"]), "name": h.get("name", True),
                "label": nfc(h["label"]) if h.get("label") else None}

    def _pin(self, p):
        lon, lat = self._lonlat(p, "pin")
        label = p.get("label")
        if label is None and p.get("place"):
            label = p["place"]
        return {"lon": lon, "lat": lat, "label": nfc(label) if label else "", "t0": float(p.get("t0", 0)),
                "t1": p.get("t1"), "color": hexcolor(p.get("color"), self.th["pin"])}

    def _number(self, n):
        if "value" not in n and "text" not in n:
            raise SceneError("numbers: cần value (số đếm lên) hoặc text")
        at = n.get("at", "tren")
        if isinstance(at, (list, tuple)):
            x, y = float(at[0]), float(at[1])
        else:
            # "tren" = the title's spot (end the title with t1 before the number comes in)
            pos = {"tren": (0.5, 0.115), "giua": (0.5, 0.45), "duoi": (0.5, 0.66)} if self.vertical else                 {"tren": (0.5, 0.15), "giua": (0.5, 0.45), "duoi": (0.5, 0.72)}
            x, y = pos.get(at, pos["tren"])
        return {"value": n.get("value"), "text": nfc(n["text"]) if n.get("text") else None,
                "prefix": nfc(n.get("prefix", "")), "suffix": nfc(n.get("suffix", "")),
                "decimals": int(n.get("decimals", 0)), "label": nfc(n.get("label", "")),
                "t0": float(n.get("t0", 0)), "t1": n.get("t1"), "count": float(n.get("count", 1.2)),
                "x": x, "y": y, "size": float(n.get("size", 1.0))}

    def _title(self, x):
        return {"text": nfc(x["text"]), "t0": float(x.get("t0", 0)), "t1": x.get("t1")}

    def _label(self, x):
        lon, lat = self._lonlat(x, "labels")
        return {"lon": lon, "lat": lat, "text": nfc(x["text"]), "style": x.get("style", "place"),
                "t0": float(x.get("t0", 0)), "t1": x.get("t1")}

    def all_texts(self):
        out = [t["text"] for t in self.titles] + [p["label"] for p in self.pins] + [l["text"] for l in self.labels]
        out += [n["text"] or "" for n in self.numbers] + [n["label"] + n["prefix"] + n["suffix"] for n in self.numbers]
        out += [h["label"] or "" for h in self.highlights]
        return out

    # ---------- camera ----------
    def camera(self, t):
        ks = self.keys
        if t <= ks[0]["t"]:
            k = ks[0]
            return k["cx"], k["cy"], k["span"]
        for a, b in zip(ks, ks[1:]):
            if t <= b["t"]:
                e = ease((t - a["t"]) / max(1e-6, b["t"] - a["t"]), b["ease"])
                s = math.exp(math.log(a["span"]) * (1 - e) + math.log(b["span"]) * e)
                r = b["span"] / a["span"]
                if abs(math.log(r)) > 0.05:
                    w = (s / a["span"] - 1) / (r - 1)    # zoom about a fixed point: a straight dolly
                else:
                    w = e
                return a["cx"] + (b["cx"] - a["cx"]) * w, a["cy"] + (b["cy"] - a["cy"]) * w, s
        k = ks[-1]
        return k["cx"], k["cy"], k["span"]

    def to_px(self, cam, lon, lat):
        cx, cy, span = cam
        k = self.W / span
        x, y = geo.merc(lon, lat)
        return (float(x) - cx) * k + self.W / 2, self.H / 2 - (float(y) - cy) * k

    # ---------- drawing ----------
    def _background(self):
        if self._bg is None:
            W, H = self.W * SS, self.H * SS
            a, b = np.array(self.th["ocean_top"], float), np.array(self.th["ocean_bot"], float)
            g = np.linspace(0, 1, H)[:, None]
            col = (a + (b - a) * g).astype(np.uint8)
            self._bg = Image.fromarray(np.repeat(col[:, None, :], W, axis=1).reshape(H, W, 3))
            v = self.th["vignette"]
            if v:
                yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
                d = np.hypot((xx / self.W - 0.5) * 1.2, (yy / self.H - 0.5) * 1.0)
                self._vig = (1 - v * np.clip((d - 0.35) / 0.45, 0, 1) ** 1.5)[..., None]
        return self._bg.copy()

    def _rings_px(self, c, cam, k, offs):
        """Rings of a country in supersampled pixels, culled and thinned."""
        cx, cy, span = cam
        W, H = self.W * SS, self.H * SS
        out = []
        for off in offs:
            for r in c["rings"]:
                x0, y0, x1, y1 = r["bbox"]
                px0, px1 = (x0 + off - cx) * k + W / 2, (x1 + off - cx) * k + W / 2
                py0, py1 = H / 2 - (y1 - cy) * k, H / 2 - (y0 - cy) * k
                if px1 < -4 or px0 > W + 4 or py1 < -4 or py0 > H + 4:
                    continue
                if (px1 - px0) < 0.8 and (py1 - py0) < 0.8:
                    continue
                xy = r["xy"]
                p = np.empty_like(xy)
                p[:, 0] = (xy[:, 0] + off - cx) * k + W / 2
                p[:, 1] = H / 2 - (xy[:, 1] - cy) * k
                q = np.round(p).astype(np.int64)
                keep = np.ones(len(q), bool)
                keep[1:] = np.any(q[1:] != q[:-1], axis=1)
                q = q[keep]
                if len(q) < 3:
                    continue
                np.clip(q, -2_000_000_000, 2_000_000_000, out=q)
                out.append(q.ravel().tolist())
        return out

    def frame(self, t, collect=None):
        th = self.th
        cam = self.camera(t)
        cx, cy, span = cam
        W, H = self.W, self.H
        k = W * SS / span
        offs = [0.0]
        if cx - span / 2 < -math.pi:
            offs.append(-2 * math.pi)
        if cx + span / 2 > math.pi:
            offs.append(2 * math.pi)
        img = self._background()
        d = ImageDraw.Draw(img)
        self._grid(d, cam, k)

        hl = {}
        for h in self.highlights:
            a = fade(t, h["t0"], h["t1"], 0.6)
            if a > 0.001:
                hl[h["c"]["iso"]] = (h, a)
        spot = max([a for h, a in hl.values() if h["style"] == "spotlight"] + [0.0])
        bw = max(1, int(round(1.3 * SS * self.u)))
        polys = {}
        for c in self.w.countries:
            rings = self._rings_px(c, cam, k, offs)
            if not rings:
                continue
            polys[c["iso"]] = rings
            fill = th["land"]
            if c["iso"] in hl:
                h, a = hl[c["iso"]]
                if h["style"] in ("tint", "spotlight"):
                    fill = mix(th["land"], h["color"], 0.95 * a)
            elif spot:
                fill = mix(th["land"], th["dim"], spot)
            for r in rings:
                d.polygon(r, fill=fill)
            for r in rings:
                if len(r) >= 6:
                    d.line(r + r[:2], fill=th["border"], width=bw)
        # highlighted outlines on top of the neighbours' borders
        for iso, (h, a) in hl.items():
            for r in polys.get(iso, []):
                if len(r) >= 6:
                    d.line(r + r[:2], fill=mix(th["border"], th["edge"] if h["style"] != "outline" else h["color"], a),
                           width=max(2, int(round(2.6 * SS * self.u))), joint="curve")
        isl_px = self._islands(d, cam, hl)
        img = img.resize((W, H), Image.Resampling.BOX) if SS > 1 else img

        # glow around highlighted countries
        if hl:
            m = Image.new("L", (W, H), 0)
            md = ImageDraw.Draw(m)
            gl = 0.0
            for iso, (h, a) in hl.items():
                for r in polys.get(iso, []):
                    md.polygon([v / SS for v in r], fill=255)
                gl = max(gl, a)
            sharp = np.asarray(m, np.float32)[..., None] / 255.0
            m = m.filter(ImageFilter.GaussianBlur(radius=max(4, 0.014 * W)))
            col = np.array(next(iter(hl.values()))[0]["color"], np.float32)
            arr = np.asarray(img, np.float32)
            # glow outside the border only, so the fill keeps its true colour
            g = (np.asarray(m, np.float32)[..., None] / 255.0) * (1 - 0.9 * sharp) * (0.5 * gl)
            arr = arr * (1 - g) + col * g
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if self._vig is not None:
            img = Image.fromarray((np.asarray(img, np.float32) * self._vig).astype(np.uint8))

        # overlay: pins, labels, numbers, title
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        boxes = []      # (priority, name, rect)
        self._titles(od, t, boxes)
        self._numbers(od, t, boxes)
        self._pins(ov, od, t, cam, boxes)
        self._vn_labels(od, cam, isl_px, boxes)
        self._user_labels(od, t, cam, boxes)
        if self.show_country_names:
            self._country_names(od, t, cam, hl, boxes)
        if collect is not None:
            collect.extend(boxes)
        img = img.convert("RGBA")
        img.alpha_composite(ov)
        return img.convert("RGB")

    def _grid(self, d, cam, k):
        cx, cy, span = cam
        deg = math.degrees(span)
        step = 30 if deg > 120 else 10 if deg > 30 else 5 if deg > 10 else 1 if deg > 2 else None
        if not step:
            return
        W, H = self.W * SS, self.H * SS
        col = self.th["grid"]
        lw = max(1, int(SS * self.u))
        lon0 = math.degrees(cx - span / 2)
        lon1 = math.degrees(cx + span / 2)
        for lon in range(int(math.floor(lon0 / step) * step), int(lon1) + step, step):
            x = (math.radians(lon) - cx) * k + W / 2
            d.line([(x, 0), (x, H)], fill=col, width=lw)
        top = geo.unmerc(0, cy + span * self.H / self.W / 2)[1]
        bot = geo.unmerc(0, cy - span * self.H / self.W / 2)[1]
        for lat in range(int(math.floor(max(-80, bot) / step) * step), int(min(80, top)) + step, step):
            y = H / 2 - (float(geo.merc(0, lat)[1]) - cy) * k
            d.line([(0, y), (W, y)], fill=col, width=lw)

    def _islands(self, d, cam, hl):
        """Island dots of Hoàng Sa and Trường Sa, always visible; tinted with Vietnam."""
        out = {}
        vn = hl.get("VNM")
        for key, pts in self.w.islands.items():
            fill = self.th["island"]
            if vn and vn[0]["style"] in ("tint", "spotlight"):
                fill = mix(self.th["island"], vn[0]["color"], vn[1])
            r = max(1.2, 3.4 * self.u) * SS
            xs, ys = [], []
            for lon, lat in pts:
                x, y = self.to_px(cam, lon, lat)
                xs.append(x)
                ys.append(y)
                X, Y = x * SS, y * SS
                if -20 < X < self.W * SS + 20 and -20 < Y < self.H * SS + 20:
                    d.ellipse([X - r, Y - r, X + r, Y + r], fill=fill)
            seen = any(-2 < x < self.W + 2 and -2 < y < self.H + 2 for x, y in zip(xs, ys))
            out[key] = (sum(xs) / len(xs), sum(ys) / len(ys), min(xs), min(ys), max(xs), max(ys), seen)
        return out

    # ----- text helpers -----
    def _text(self, od, xy, text, px, fill, a, anchor="mm", stroke=None, spacing=0):
        if a <= 0.01 or not text:
            return None
        f = font(px)
        sw = max(1, int(round(px * 0.09))) if stroke is None else stroke
        al = int(255 * a)
        if spacing:
            # letter-spaced (sea names)
            widths = [f.getlength(ch) for ch in text]
            total = sum(widths) + spacing * (len(text) - 1)
            x = xy[0] - total / 2
            for ch, wd in zip(text, widths):
                od.text((x, xy[1]), ch, font=f, fill=fill + (al,), anchor="lm", stroke_width=sw,
                        stroke_fill=self.th["stroke"] + (int(al * 0.85),))
                x += wd + spacing
            return (xy[0] - total / 2, xy[1] - px * 0.6, xy[0] + total / 2, xy[1] + px * 0.6)
        od.text(xy, text, font=f, fill=fill + (al,), anchor=anchor, stroke_width=sw,
                stroke_fill=self.th["stroke"] + (int(al * 0.85),))
        return od.textbbox(xy, text, font=f, anchor=anchor, stroke_width=sw)

    def _clamp(self, rect, margin=None):
        m = (margin if margin is not None else 0.025) * self.W
        x0, y0, x1, y1 = rect
        dx = max(0, m - x0) - max(0, x1 - (self.W - m))
        dy = max(0, m - y0) - max(0, y1 - (self.H - m))
        return dx, dy

    def _titles(self, od, t, boxes):
        for x in self.titles:
            a = fade(t, x["t0"], x["t1"])
            if a <= 0.01:
                continue
            px = 58 * self.u
            maxw = self.W * 0.86
            lines = wrap(x["text"], font(px), maxw)
            if len(lines) > 2:
                px *= 0.8
                lines = wrap(x["text"], font(px), maxw)
            y = (0.075 if self.vertical else 0.08) * self.H
            lh = px * 1.22
            bw = max(font(px).getlength(l) for l in lines) + px * 1.1
            bh = lh * len(lines) + px * 0.55
            rect = (self.W / 2 - bw / 2, y - px * 0.4, self.W / 2 + bw / 2, y - px * 0.4 + bh)
            od.rounded_rectangle(rect, radius=px * 0.45, fill=self.th["pill"] + (int(215 * a),))
            for i, l in enumerate(lines):
                self._text(od, (self.W / 2, rect[1] + px * 0.28 + lh * (i + 0.5)), l, px, self.th["text"], a, stroke=0)
            boxes.append((0, "title", rect))

    def _numbers(self, od, t, boxes):
        for n in self.numbers:
            a = fade(t, n["t0"], n["t1"], 0.25)
            if a <= 0.01:
                continue
            pop = 0.6 + 0.4 * out_back((t - n["t0"]) / 0.35)
            if n["value"] is not None:
                v = float(n["value"]) * ease((t - n["t0"]) / max(0.01, n["count"]), "out")
                s = n["prefix"] + fmt_number(v, n["decimals"], self.lang) + n["suffix"]
                full = n["prefix"] + fmt_number(float(n["value"]), n["decimals"], self.lang) + n["suffix"]
            else:
                s = full = n["text"]
            px = 150 * self.u * n["size"]
            f = font(px)
            if f.getlength(full) > self.W * 0.88:
                px *= self.W * 0.88 / f.getlength(full)
            x, y = n["x"] * self.W, n["y"] * self.H
            half = font(px).getlength(full) / 2
            m = 0.03 * self.W
            x = min(max(x, m + half), self.W - m - half)   # keep the whole number in frame
            r = self._text(od, (x, y), s, px * pop, self.th["number"], a, stroke=max(2, int(px * 0.06)))
            if r:
                # box from the full number at full size, so the check is stable while it counts up
                fw = font(px).getlength(full)
                boxes.append((1, "number", (x - fw / 2, y - px * 0.5, x + fw / 2, y + px * 0.42)))
            if n["label"]:
                r2 = self._text(od, (x, y + px * 0.78), n["label"], 46 * self.u, self.th["text"], a)
                if r2:
                    boxes.append((1, "number label", r2))

    def _pins(self, ov, od, t, cam, boxes):
        for p in self.pins:
            a = fade(t, p["t0"], p["t1"], 0.2)
            if a <= 0.01:
                continue
            x, y = self.to_px(cam, p["lon"], p["lat"])
            if not (-50 < x < self.W + 50 and -50 < y < self.H + 50):
                continue
            u = self.u
            drop = (1 - out_back((t - p["t0"]) / 0.45)) * 60 * u
            # pulse ring at the point
            pu = ((t - p["t0"]) % 1.6) / 1.6
            rr = (8 + 34 * pu) * u
            od.ellipse([x - rr, y - rr * 0.5, x + rr, y + rr * 0.5], outline=p["color"] + (int(200 * a * (1 - pu)),),
                       width=max(2, int(3 * u)))
            od.ellipse([x - 9 * u, y - 4 * u, x + 9 * u, y + 4 * u], fill=(0, 0, 0, int(90 * a)))
            # pin head (drawn 4x for smooth edges)
            R = 22 * u
            hx, hy = x, y - drop - R * 2.1
            S = 4
            size = int(R * 2.6 * S) + 4
            pin = Image.new("RGBA", (size, int(size * 1.5)), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pin)
            c = size / 2
            pd.polygon([(c - R * 0.78 * S, R * 1.6 * S), (c + R * 0.78 * S, R * 1.6 * S), (c, (R * 2.1 + R * 0.9) * S)],
                       fill=p["color"] + (255,))
            pd.ellipse([c - R * S, R * 0.3 * S, c + R * S, R * 2.3 * S], fill=p["color"] + (255,),
                       outline=(255, 255, 255, 255), width=int(2.5 * u * S))
            pd.ellipse([c - R * 0.38 * S, R * 0.92 * S, c + R * 0.38 * S, R * 1.68 * S], fill=(255, 255, 255, 255))
            pin = pin.resize((max(1, pin.width // S), max(1, pin.height // S)), Image.Resampling.LANCZOS)
            if a < 1:
                al = pin.getchannel("A").point(lambda v: int(v * a))
                pin.putalpha(al)
            tip_y = y - drop
            ox, oy = int(round(x - pin.width / 2)), int(round(tip_y - (R * 3.0) - 0.5))
            ov.alpha_composite(pin, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
            head = (x - R, oy + R * 0.3, x + R, tip_y)
            boxes.append((2, "pin", head))
            if p["label"]:
                px = 44 * u
                f = font(px)
                tw = f.getlength(p["label"])
                ly = oy - px * 0.35
                rect = [x - tw / 2 - px * 0.5, ly - px * 1.15, x + tw / 2 + px * 0.5, ly]
                if any(overlap(rect, b[2]) for b in boxes if b[0] <= 1) or rect[1] < self.H * 0.02:
                    # title or number above: put the label under the pin instead
                    rect = [rect[0], tip_y + px * 0.45, rect[2], tip_y + px * 1.6]
                dx, dy = self._clamp(rect)
                rect = [rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy]
                od.rounded_rectangle(rect, radius=px * 0.4, fill=self.th["pill"] + (int(225 * a),))
                self._text(od, ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), p["label"], px, self.th["text"], a,
                           stroke=0)
                boxes.append((2, "pin label", tuple(rect)))

    def _vn_labels(self, od, cam, isl, boxes):
        """Quần đảo Hoàng Sa, Quần đảo Trường Sa, Biển Đông: drawn whenever they are on screen."""
        span_deg = math.degrees(cam[2])
        sc = 1.0 if span_deg < 45 else max(0.62, 45 / span_deg) ** 0.5
        small, big = 24 * self.u * sc, 32 * self.u * sc
        vi = self.lang == "vi"
        for key, name in (("hoang-sa", "Hoàng Sa"), ("truong-sa", "Trường Sa")):
            mx, my, x0, y0, x1, y1, on = isl[key]   # on = at least one island is in frame
            if key == "hoang-sa":
                lx, ly = x1 + big * 0.5, my       # to the right of the islands
                anchor_x = "left"
            else:
                lx, ly = mx, y1 + big * 0.9      # below
                anchor_x = "centre"
            top = "QUẦN ĐẢO" if vi else "VIETNAM"
            main = name if vi else name + " Is."
            fw = max(font(small).getlength(top), font(big).getlength(main))
            if anchor_x == "left":
                rect = [lx, ly - big * 1.05, lx + fw, ly + big * 0.75]
            else:
                rect = [lx - fw / 2, ly - big * 0.4, lx + fw / 2, ly + big * 1.45]
            if on:
                dx, dy = self._clamp(rect, 0.02)
                rect = [rect[0] + dx, rect[1] + dy, rect[2] + dx, rect[3] + dy]
            if rect[2] < 0 or rect[0] > self.W or rect[3] < 0 or rect[1] > self.H:
                continue
            ccx = (rect[0] + rect[2]) / 2
            self._text(od, (ccx, rect[1] + small * 0.55), top, small, self.th["text"], 0.85)
            self._text(od, (ccx, rect[3] - big * 0.55), main, big, self.th["text"], 1.0)
            boxes.append((3, key, tuple(rect)))
        # sea name
        x, y = self.to_px(cam, *geo.BIEN_DONG_AT)
        if -200 < x < self.W + 200 and -50 < y < self.H + 50 and span_deg < 90:
            txt = "Biển Đông" if vi else "East Sea"
            px = 34 * self.u * sc
            r = self._text(od, (x, y), txt, px, self.th["sea"], 0.95, spacing=px * 0.18, stroke=max(1, int(px * 0.05)))
            if r:
                boxes.append((4, "bien-dong", r))

    def _user_labels(self, od, t, cam, boxes):
        for l in self.labels:
            a = fade(t, l["t0"], l["t1"])
            x, y = self.to_px(cam, l["lon"], l["lat"])
            inside = 0 <= x <= self.W and 0 <= y <= self.H
            if inside:
                # anchor in frame: slide the text in so it isn't cut at the edge
                sea = l["style"] in ("sea", "bien")
                px = (34 if sea else 38) * self.u
                hw = font(px).getlength(l["text"]) / 2 + (px * 0.18 * len(l["text"]) / 2 if sea else 0) + px * 0.1
                m = 0.025 * self.W
                x = min(max(x, m + hw), self.W - m - hw)
            if l["style"] in ("sea", "bien"):
                px = 34 * self.u
                r = self._text(od, (x, y), l["text"], px, self.th["sea"], a, spacing=px * 0.18,
                               stroke=max(1, int(px * 0.05)))
            else:
                r = self._text(od, (x, y), l["text"], 38 * self.u, self.th["text"], a)
            if r and inside:   # a label whose place is off screen is just sliding out with the map
                boxes.append((5, "label", r))

    def _country_names(self, od, t, cam, hl, boxes):
        for iso, (h, a) in hl.items():
            if not h["name"]:
                continue
            c = h["c"]
            name = h["label"] or (c["name_vi"] if self.lang == "vi" else c["name_en"])
            lon, lat = c["label"]
            if lon is None:
                continue
            x, y = self.to_px(cam, lon, lat)
            px = 46 * self.u
            f = font(px)
            tw = f.getlength(name)
            y0 = y
            for dy in (0, 1.4, -1.4, 2.6, -2.6, 3.8):   # step away from pins, numbers and the islands
                y = y0 + dy * px
                rect = (x - tw / 2, y - px * 0.6, x + tw / 2, y + px * 0.6)
                if not any(overlap(rect, b[2]) for b in boxes if b[0] <= 4):
                    break
            r = self._text(od, (x, y), name, px, self.th["text"], a)
            if r:
                boxes.append((6, "country", r))


def wrap(text, f, maxw):
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if f.getlength(trial) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def overlap(a, b, pad=2):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def forbidden_terms(texts):
    bad = []
    for s in texts:
        low = nfc(s).lower()
        f = " ".join(geo.fold(w) for w in low.split())
        for term in FORBIDDEN:
            if re.search(r"(?<!\w)" + term, f):
                bad.append((s, term))
        for term in FORBIDDEN_TONED:
            if re.search(r"(?<!\w)" + term + r"(?!\w)", low):
                bad.append((s, term))
    return bad
