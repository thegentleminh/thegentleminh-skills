"""Map data for ban-do: Natural Earth download + cache, Web Mercator, name lookup.

Natural Earth (naturalearthdata.com) is public domain. We use the 1:10m countries file in
Natural Earth's Vietnam point of view, where Hoàng Sa and Trường Sa are part of Vietnam,
plus the 1:10m populated places file for city names.
"""
import json
import math
import os
import pickle
import sys
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np

NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"  # a fixed release
FILES = {
    "countries": "ne_10m_admin_0_countries_vnm.geojson",   # about 13 MB
    "places": "ne_10m_populated_places_simple.geojson",    # about 5 MB
}
CACHE_VERSION = 4

# The two archipelagos (boxes used to find their islands in the data and to check frames).
HOANG_SA_BOX = (111.0, 15.6, 113.0, 17.3)     # lon0, lat0, lon1, lat1
TRUONG_SA_BOX = (111.5, 6.0, 117.0, 12.0)
BIEN_DONG_AT = (113.4, 13.3)

REGIONS = {
    # slug: (lon0, lat0, lon1, lat1)
    "the-gioi": (-170, -58, 190, 78),
    "chau-a": (40, -10, 150, 60),
    "dong-nam-a": (90, -11, 128, 28),
    "dong-a": (95, 4, 150, 50),
    "nam-a": (60, 5, 98, 37),
    "trung-dong": (25, 12, 63, 42),
    "chau-au": (-25, 34, 45, 71),
    "chau-phi": (-20, -36, 53, 38),
    "bac-my": (-170, 7, -50, 75),
    "nam-my": (-85, -56, -33, 13),
    "chau-uc": (110, -48, 180, 0),
}
REGION_ALIASES = {
    "world": "the-gioi", "thegioi": "the-gioi", "asia": "chau-a", "chaua": "chau-a",
    "southeastasia": "dong-nam-a", "dongnama": "dong-nam-a", "eastasia": "dong-a", "donga": "dong-a",
    "southasia": "nam-a", "nama": "nam-a", "middleeast": "trung-dong", "trungdong": "trung-dong",
    "europe": "chau-au", "chauau": "chau-au", "africa": "chau-phi", "chauphi": "chau-phi",
    "northamerica": "bac-my", "bacmy": "bac-my", "southamerica": "nam-my", "nammy": "nam-my",
    "oceania": "chau-uc", "australia-region": "chau-uc", "chauuc": "chau-uc",
}

# Common Vietnamese / short names that the data spells differently.
PLACE_ALIASES = {
    "saigon": "Ho Chi Minh City", "tphcm": "Ho Chi Minh City", "hcm": "Ho Chi Minh City",
    "thanhphohochiminh": "Ho Chi Minh City", "hochiminh": "Ho Chi Minh City",
    "thudo": "Hanoi", "hue": "Hue", "nhatrang": "Nha Trang", "dalat": "Da Lat",
    "vungtau": "Vung Tau", "cantho": "Can Tho", "haiphong": "Haiphong", "quynhon": "Quy Nhon",
    "phuquoc": "Duong Dong", "tokyo": "Tokyo", "seoul": "Seoul", "newyork": "New York",
    "bangkok": "Bangkok", "luandon": "London",
    "paris": "Paris", "backinh": "Beijing", "beijing": "Beijing", "matxcova": "Moscow",
}
COUNTRY_ALIASES = {
    "my": "USA", "hoaky": "USA", "us": "USA", "usa": "USA", "america": "USA",
    "anh": "GBR", "uk": "GBR", "phap": "FRA", "duc": "DEU", "nga": "RUS", "trungquoc": "CHN",
    "nhatban": "JPN", "nhat": "JPN", "hanquoc": "KOR", "trieutien": "PRK", "uc": "AUS",
    "thailan": "THA", "campuchia": "KHM", "lao": "LAO", "vietnam": "VNM", "vn": "VNM",
    "dailoan": "TWN", "ando": "IND", "y": "ITA", "taybannha": "ESP", "canada": "CAN",
}


def fold(s):
    """Lowercase, no tone marks, no spaces or punctuation: 'Đà Nẵng' -> 'danang'."""
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c for c in s.lower() if c.isalnum())


def cache_dir():
    """Map data lives in ~/.cache/ban-do on every system (BAN_DO_DATA overrides it)."""
    d = Path(os.environ.get("BAN_DO_DATA") or (Path.home() / ".cache" / "ban-do"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def have_data():
    d = cache_dir()
    return all((d / f).exists() for f in FILES.values())


def download(quiet=False):
    d = cache_dir()
    for key, name in FILES.items():
        dst = d / name
        if dst.exists() and dst.stat().st_size > 100_000:
            continue
        url = NE_BASE + name
        if not quiet:
            print(f"Tải {name} (Natural Earth, public domain)...", flush=True)
        tmp = dst.with_suffix(".part")
        req = urllib.request.Request(url, headers={"User-Agent": "ban-do-skill"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        tmp.replace(dst)
    return d


# ---------- projection (Web Mercator, unit = radians) ----------

def merc(lon, lat):
    lat = np.clip(lat, -85.0, 85.0)
    return np.radians(lon), np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def unmerc(x, y):
    return math.degrees(x), math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


# ---------- world ----------

class World:
    def __init__(self):
        if not have_data():
            raise SystemExit("Chưa có dữ liệu bản đồ. Chạy: python bando.py data  (tải ~18 MB, một lần)")
        d = cache_dir()
        pk = d / f"world-v{CACHE_VERSION}.pkl"
        if pk.exists():
            with open(pk, "rb") as f:
                self.__dict__.update(pickle.load(f))
            return
        self._build(d)
        with open(pk, "wb") as f:
            pickle.dump(self.__dict__, f, protocol=4)

    def _build(self, d):
        gj = json.loads((d / FILES["countries"]).read_text(encoding="utf-8"))
        countries = []
        for feat in gj["features"]:
            p = feat["properties"]
            g = feat["geometry"]
            if not g:
                continue
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            rings = []
            for poly in polys:
                ring = np.asarray(poly[0], dtype=np.float64)
                x, y = merc(ring[:, 0], ring[:, 1])
                m = np.stack([x, y], axis=1)
                area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
                rings.append({"xy": m, "bbox": (x.min(), y.min(), x.max(), y.max()), "area": area,
                              "lonlat": ring})
            iso = p.get("ADM0_A3") or p.get("ISO_A3")
            countries.append({
                "iso": iso, "name": p.get("NAME") or p.get("ADMIN"), "name_en": p.get("NAME_EN") or p.get("NAME"),
                "name_vi": p.get("NAME_VI") or p.get("NAME"), "admin": p.get("ADMIN"),
                "label": (p.get("LABEL_X"), p.get("LABEL_Y")), "rings": rings,
                "area": sum(r["area"] for r in rings),
            })
        countries.sort(key=lambda c: -c["area"])   # big first, so enclaves are drawn on top
        self.countries = countries
        self.by_iso = {c["iso"]: i for i, c in enumerate(countries)}

        # islands of the two archipelagos, from Vietnam's own feature
        vn = countries[self.by_iso["VNM"]]
        self.islands = {"hoang-sa": [], "truong-sa": []}
        for r in vn["rings"]:
            lon, lat = r["lonlat"][:, 0].mean(), r["lonlat"][:, 1].mean()
            for key, box in (("hoang-sa", HOANG_SA_BOX), ("truong-sa", TRUONG_SA_BOX)):
                if box[0] <= lon <= box[2] and box[1] <= lat <= box[3]:
                    self.islands[key].append((float(lon), float(lat)))
        # mainland = Vietnam without the two archipelagos
        main = [r for r in vn["rings"] if r["bbox"][2] < math.radians(110.5)]
        bx = np.array([r["bbox"] for r in main])
        self.vn_mainland_bbox = (bx[:, 0].min(), bx[:, 1].min(), bx[:, 2].max(), bx[:, 3].max())

        pl = json.loads((d / FILES["places"]).read_text(encoding="utf-8"))
        places = []
        for feat in pl["features"]:
            p = feat["properties"]
            places.append({"name": p.get("name"), "ascii": p.get("nameascii") or p.get("name"),
                           "country": p.get("adm0_a3"), "lon": p.get("longitude"), "lat": p.get("latitude"),
                           "pop": p.get("pop_max") or 0})
        places.sort(key=lambda q: -(q["pop"] or 0))
        self.places = places
        for c in countries:
            for r in c["rings"]:
                del r["lonlat"]

    # ----- lookup -----
    def country(self, q):
        if q is None:
            return None
        if isinstance(q, dict):
            q = q.get("country")
        s = str(q).strip()
        if s.upper() in self.by_iso:
            return self.countries[self.by_iso[s.upper()]]
        f = fold(s)
        if f in COUNTRY_ALIASES and COUNTRY_ALIASES[f] in self.by_iso:
            return self.countries[self.by_iso[COUNTRY_ALIASES[f]]]
        for c in self.countries:
            if f in (fold(c["name"]), fold(c["name_vi"]), fold(c["name_en"]), fold(c["admin"])):
                return c
        return None

    def place(self, q):
        f = fold(q)
        target = PLACE_ALIASES.get(f)
        for p in self.places:
            if target and p["ascii"] == target:
                return p
        for p in self.places:
            if f in (fold(p["name"]), fold(p["ascii"])):
                return p
        return None

    def search(self, q, n=8):
        f = fold(q)
        out = []
        p = self.place(q) if f in PLACE_ALIASES else None
        if p:
            out.append(("place", p["country"], p["name"], f"{p['lat']:.3f}, {p['lon']:.3f}"))
        c = self.country(q)
        if c:
            out.append(("country", c["iso"], c["name_vi"], c["name_en"]))
        for c in self.countries:
            names = (c["name"], c["name_vi"], c["name_en"], c["iso"])
            if any(f and f in fold(x) for x in names):
                out.append(("country", c["iso"], c["name_vi"], c["name_en"]))
        for p in self.places:
            if f and (f in fold(p["name"]) or f in fold(p["ascii"])):
                out.append(("place", p["country"], p["name"], f"{p['lat']:.3f}, {p['lon']:.3f}"))
            if len(out) >= n * 2:
                break
        return out[: n * 2]

    def fit_bbox(self, c):
        """Bounding box (mercator) of a country's main parts; far-off small islands left out.
        Vietnam always includes Hoàng Sa and Trường Sa."""
        rings = c["rings"]
        big = max(rings, key=lambda r: r["area"])
        bx0, by0, bx1, by1 = big["bbox"]
        diag = math.hypot(bx1 - bx0, by1 - by0)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        keep = []
        for r in rings:
            rx, ry = (r["bbox"][0] + r["bbox"][2]) / 2, (r["bbox"][1] + r["bbox"][3]) / 2
            if r is big or (r["area"] > 0.02 * big["area"] and math.hypot(rx - cx, ry - cy) < 1.2 * diag):
                keep.append(r["bbox"])
        if c["iso"] == "VNM":
            for box in (HOANG_SA_BOX, TRUONG_SA_BOX):
                x0, y0 = merc(box[0], box[1])
                x1, y1 = merc(box[2], box[3])
                keep.append((x0, y0, x1, y1))
        k = np.array(keep, dtype=float)
        return k[:, 0].min(), k[:, 1].min(), k[:, 2].max(), k[:, 3].max()


def region(q):
    s = str(q).strip().lower()
    if s in REGIONS:
        return REGIONS[s]
    f = fold(s)
    if f in REGION_ALIASES:
        return REGIONS[REGION_ALIASES[f]]
    for k in REGIONS:
        if fold(k) == f:
            return REGIONS[k]
    return None


def stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
