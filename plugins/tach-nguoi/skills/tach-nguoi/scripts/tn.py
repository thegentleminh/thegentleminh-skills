"""tach-nguoi: person cut-out effects for short videos. MIT licence.

Commands
  check                       what is installed (ffmpeg, Python packages, GPU, RVM) and what works
  matte  <clip>               cut the person out of the whole clip (cached next to the outputs)
  behind <plan.json>          text behind the person (stills / preview / full)
  freeze <plan.json>          freeze-frame effects: character intro, photo snap, comic freeze
  clone  <plan.json>          clones: a trail of copies from one take, or one person in two roles from two takes
  settings [set k=v ...|reset]  the saved setup answers (asked once, reused by every plan)
  sample <kind> <clip>        every option of one setting side by side on your own clip (setup phase)

Run `python tn.py <command> -h` for options. Every output is a new file; source clips are only read.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import cv2  # noqa: E402
import tn_io  # noqa: E402
import tn_text  # noqa: E402
import tn_freeze  # noqa: E402
import tn_sfx  # noqa: E402
import tn_clone  # noqa: E402
import tn_settings  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- check
def cmd_check(a):
    ok = lambda b: "OK " if b else "-- "
    v = sys.version_info
    print(ok(v >= (3, 10)) + f"Python {v.major}.{v.minor}", sys.executable)
    print(ok(shutil.which("ffmpeg")) + "ffmpeg", shutil.which("ffmpeg") or "(missing: needed for everything)")
    print(ok(shutil.which("ffprobe")) + "ffprobe", shutil.which("ffprobe") or "(missing: comes with ffmpeg)")
    for mod in ("numpy", "cv2", "PIL"):
        try:
            __import__(mod)
            print(ok(True) + mod)
        except ImportError:
            print(ok(False) + mod + " (missing)")
    try:
        import torch
        gpu = torch.cuda.is_available()
        print(ok(True) + f"torch {torch.__version__}", "GPU: " + (torch.cuda.get_device_name(0) if gpu else "none (matting runs on CPU, slowly)"))
        hub = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch")) / "hub" / "PeterL1n_RobustVideoMatting_master"
        print(ok(hub.exists()) + "RVM model", "downloaded" if hub.exists() else "not downloaded yet (first matte asks to download it)")
    except ImportError:
        print(ok(False) + "torch (missing: every effect needs it; see 'Installing PyTorch' in SKILL.md, ask the user first)")


# ---------------------------------------------------------------- matte
def work_dir(out):
    d = Path(out).resolve().parent / "_tach-nguoi-work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_key(clip):
    st = Path(clip).stat()
    return hashlib.sha1(f"{Path(clip).resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:10]


def matte_path(clip, wd, width):
    return wd / f"{Path(clip).stem}.{clip_key(clip)}.w{width}.alpha.mkv"


def ensure_matte(clip, wd, width=None):
    # cut-out width: 1280 by default; TACH_NGUOI_MATTE_WIDTH=960 (or lower) uses less GPU memory and time
    width = width or int(os.environ.get("TACH_NGUOI_MATTE_WIDTH", "1280"))
    meta = tn_io.probe(clip)
    width = min(width, meta["w"])
    width -= width % 2
    mp = matte_path(clip, wd, width)
    if mp.exists() and mp.stat().st_size > 0:
        return mp
    tmp = mp.with_suffix(".part.mkv")
    print(f"Cutting the person out of {Path(clip).name} (once per clip; cached in {wd.name}) ...", flush=True)
    r = subprocess.run([sys.executable, str(HERE / "rvm_matte.py"), str(clip), str(tmp), "--width", str(width)])
    if r.returncode != 0:
        sys.exit("The cut-out step failed. Run `python tn.py check` to see what is missing.")
    tmp.replace(mp)
    return mp


def cmd_matte(a):
    wd = Path(a.work) if a.work else work_dir(Path(a.clip).parent / "x")
    print(ensure_matte(a.clip, wd, a.width))


# ---------------------------------------------------------------- placement
def shape_of(w, h):
    r = w / h
    return "9:16" if r < 0.8 else ("1:1" if r < 1.25 else "16:9")


def sample_alpha(matte, t0, t1, fps, size, n=40):
    """Up to n matte frames between t0 and t1, resized to size (w, h), as float 0-1."""
    rd = tn_io.Reader(matte, size=size, gray=True, start=t0, end=t1)
    frames = [f.astype(np.float32) / 255 for f in rd]
    if not frames:
        return np.zeros((1, size[1], size[0]), np.float32)
    idx = np.linspace(0, len(frames) - 1, min(n, len(frames))).astype(int)
    return np.stack([frames[i] for i in idx])


# cover level -> (max hidden share of a word's first/last letter, one heavily hidden middle letter allowed per N
#                 letters, max share of all text ink hidden, target share hidden)
COVER = {
    "light": (0.45, 6, 0.15, 0.06),
    "medium": (0.60, 5, 0.22, 0.10),
    "bold": (0.80, 3, 0.35, 0.18),
}


def letter_cover(lab, alphas, n_letters):
    """Per-letter share hidden by the person (95th percentile over frames) and the overall mean."""
    ink = lab >= 0
    if not ink.any():
        return np.zeros(n_letters), 0.0
    overall = float((alphas[:, ink]).mean())
    per = np.zeros(n_letters)
    for i in range(n_letters):
        m = lab == i
        if m.any():
            per[i] = float(np.percentile(alphas[:, m].mean(axis=1), 95))
    return per, overall


def head_top(alphas):
    """Row (0-1) where the person starts, from the average matte."""
    mean = alphas.mean(axis=0)
    rows = np.nonzero(mean.mean(axis=1) > 0.04)[0]
    return rows[0] / mean.shape[0] if len(rows) else None


def plan_item(item, meta, matte, small_w=360):
    """Decide size and position for one text item: as big as the frame allows, behind the head, still readable.

    Readable (how people actually read a half-covered word): the first and last letter of every word stay
    mostly visible, a word may lose one middle letter per five letters, and no more than `max_hidden` of all
    the ink is hidden on average.
    """
    W, H = meta["w"], meta["h"]
    shape = shape_of(W, H)
    top, bottom, left, right = tn_settings.safe_area(item.get("platform", "tiktok"), shape)
    font = item.get("font", "cao")
    upper = item.get("upper", True)
    tracking = item.get("tracking", 0.02)
    width_frac = item.get("width", 1 - left - right)
    sc = small_w / W
    sh = int(round(H * sc))
    alphas = sample_alpha(matte, item["start"], item["end"], meta["fps"], (small_w, sh))
    ht = head_top(alphas)
    # how much the person may cover: light = always easy to read, bold = the heavy trend look (setup-phase choice)
    cover = item.get("cover", "medium")
    if cover not in COVER:
        sys.exit(f"Unknown cover '{cover}'. Use light, medium or bold.")
    end_max, per_word, max_hidden, want = COVER[cover]
    max_letter = item.get("max_letter", 0.65)
    max_hidden = item.get("max_hidden", max_hidden)
    best = None
    layouts = [item["text"]]
    words = item["text"].split()
    if "\n" not in item["text"] and len(words) >= 2 and item.get("lines", "auto") == "auto":
        # stacked version: split where the two lines come out closest in length
        cut = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
        layouts.append(" ".join(words[:cut]) + "\n" + " ".join(words[cut:]))
    cands = [(lay, shrink) for shrink in (1.0, 0.9, 0.8, 0.7, 0.6) for lay in layouts]
    for text, shrink in cands:
        size = tn_text.fit_size(text, font, width_frac * shrink * W, upper=upper, tracking=tracking)
        tb = tn_text.TextBlock(text, font, size, color=item.get("color", "#ffffff"), upper=upper, tracking=tracking)
        max_h = (1 - top - bottom) * H * 0.75
        if tb.H > max_h:  # stacked lines can get taller than the frame allows
            size = int(size * max_h / tb.H)
            tb = tn_text.TextBlock(text, font, size, color=item.get("color", "#ffffff"), upper=upper, tracking=tracking)
        lab_i = tb.labels()
        lab_local = lab_i.astype(np.float32)
        ry, rx = np.nonzero(lab_i >= 0)
        # where the ink is inside the block (the block has padding), so safe areas apply to real letters
        ix0, ix1, iy0, iy1 = (rx.min() - tb.W / 2) / W, (rx.max() - tb.W / 2) / W, (ry.min() - tb.H / 2) / H, (ry.max() - tb.H / 2) / H
        th = (ry.max() - ry.min()) / H
        ylo, yhi = top - iy0, 1 - bottom - iy1
        xlo, xhi = left - ix0, 1 - right - ix1
        if yhi < ylo or xhi < xlo:
            continue  # this size doesn't fit the safe area
        ys = [item["y"]] if item.get("y") is not None else np.linspace(ylo, yhi, 32)
        # slide sideways too, so the head can land between words or on a middle letter
        xs = [item["x"]] if item.get("x") is not None else (np.linspace(xlo, xhi, 11) if xhi - xlo > 0.005 else [(xlo + xhi) / 2])
        info = tb.letter_info if len(tb.letter_info) == tb.n_letters else [(0, 1, 9)] * tb.n_letters
        for xf in xs:
            cx = xf * W
            for yf in ys:
                m = np.float32([[sc, 0, cx * sc - sc * tb.W / 2], [0, sc, yf * H * sc - sc * tb.H / 2]])
                lab = cv2.warpAffine(lab_local, m, (small_w, sh), flags=cv2.INTER_NEAREST, borderValue=-1).astype(np.int16)
                per, overall = letter_cover(lab, alphas, tb.n_letters)
                end_hidden = sum(1 for i, (wi, k, n) in enumerate(info) if (k == 0 or k == n - 1) and per[i] > end_max)
                heavy_by_word = {}
                for i, (wi, k, n) in enumerate(info):
                    if per[i] > max_letter:
                        heavy_by_word[wi] = heavy_by_word.get(wi, 0) + 1
                word_len = {wi: n for wi, k, n in info}
                too_many = sum(1 for wi, c in heavy_by_word.items() if c > word_len[wi] // per_word)
                partly = int((per > 0.35).sum())
                fits = end_hidden == 0 and too_many == 0 and overall <= max_hidden
                # the look: the text sits behind the top of the head, so the head cuts into its lower half
                near_head = 0.0 if ht is None else abs(yf - (ht + 0.15 * th))
                area = tb.W * tb.H / (W * H)  # bigger reads as bolder: the main thing among readable options
                score = (2.0 * area - abs(overall - want) - 0.15 * near_head - 0.02 * partly - 0.05 * abs(xf - 0.5)
                         - (10 if not fits else 0) - (0.3 if overall < 0.02 else 0))
                cand = {"text_layout": text, "size": size, "cx": cx, "cy": yf * H, "xf": round(float(xf), 3), "yf": round(float(yf), 3),
                        "hidden_mean": round(overall, 3), "worst_letter": round(float(per.max(initial=0)), 2),
                        "letters_partly_hidden": partly, "end_letters_hidden": end_hidden,
                        "fits": fits, "score": score, "block": tb}
                if best is None or score > best["score"]:
                    best = cand
    if not best["fits"]:
        best["note"] = (f"NOT READABLE: {best['end_letters_hidden']} first/last letters hidden, worst letter "
                        f"{best['worst_letter']:.0%} hidden, {best['hidden_mean']:.0%} of the text hidden overall. "
                        f"Try a shorter word, another time range, or set 'y'/'x' by hand.")
    elif best["hidden_mean"] < 0.01:
        best["note"] = "The person never passes in front of this text, so it won't look 'behind'. Try another 'y' or a bigger 'width'."
    return best


def rel_lum(rgb):
    c = np.asarray(rgb, np.float32) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]) if c.ndim == 1 else 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def contrast_check(clip, item, p, W, H):
    """WCAG-style contrast between the text color and the background under the text, mid-range frame."""
    t = (item["start"] + item["end"]) / 2
    fr = next(iter(tn_io.Reader(clip, start=t, frames=1)))
    ink = tn_text.place(p["block"].canvas(), W, H, p["cx"], p["cy"], 1.0, 0.0)[..., 3] > 0.5
    if not ink.any():
        return 21.0
    bg = float(np.median(rel_lum(fr[ink])))
    fg = rel_lum(tn_text.hex_rgb(item.get("color", "#ffffff")))
    hi, lo = max(bg, fg), min(bg, fg)
    return round((hi + 0.05) / (lo + 0.05), 2)


# ---------------------------------------------------------------- render
def compose(frame, alpha, layer):
    """frame RGB uint8, alpha HxW float (person), layer HxWx4 float (text). Person stays in front."""
    f = frame.astype(np.float32) / 255
    ta = layer[..., 3:4]
    under = f * (1 - ta) + layer[..., :3] * ta
    a = alpha[..., None]
    return np.clip((f * a + under * (1 - a)) * 255 + 0.5, 0, 255).astype(np.uint8)


def text_canvas(p, item, la, ldy):
    """Letter canvas with its glow; cached, since most frames show the same letters."""
    cache = p.setdefault("_cache", {})
    key = None if la is None else (np.round(la, 2).tobytes() + np.round(ldy, 0).tobytes())
    if key not in cache:
        if len(cache) > 64:
            cache.clear()
        cache[key] = p["block"].canvas(la, ldy, shadow=item.get("shadow", 0.35))
    return cache[key]


def text_layer(p, item, t, W, H, scale_px=1.0):
    """The text at time t as (RGBA crop, x0, y0) covering only where it lands, or None when hidden."""
    st = tn_text.anim_state(item.get("anim", "rise"), t, item["start"], item["end"], p["block"].n_letters,
                            p["block"].size_px, drift=item.get("drift", 0.03))
    if st is None:
        return None
    ba, sc, dy, la, ldy = st
    if ba <= 0.001:
        return None
    can = text_canvas(p, item, la, ldy)
    s = sc * scale_px
    h, w = can.shape[:2]
    x0f, y0f = p["cx"] * scale_px - s * w / 2, p["cy"] * scale_px - s * h / 2 + dy * scale_px
    X0, Y0 = max(0, int(x0f)), max(0, int(y0f))
    X1, Y1 = min(W, int(x0f + s * w) + 2), min(H, int(y0f + s * h) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return None
    m = np.float32([[s, 0, x0f - X0], [0, s, y0f - Y0]])
    crop = cv2.warpAffine(can, m, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    if ba < 1:
        crop[..., 3] *= ba
    return crop, X0, Y0


def compose_roi(frame, alpha_u8, roi):
    """Blend one text crop into the frame, behind the person. frame/alpha are full size, uint8."""
    crop, x0, y0 = roi
    h, w = crop.shape[:2]
    out = frame.copy()
    f = out[y0:y0 + h, x0:x0 + w].astype(np.float32) / 255
    a = alpha_u8[y0:y0 + h, x0:x0 + w, None].astype(np.float32) / 255
    ta = crop[..., 3:4]
    under = f * (1 - ta) + crop[..., :3] * ta
    out[y0:y0 + h, x0:x0 + w] = np.clip((f * a + under * (1 - a)) * 255 + 0.5, 0, 255).astype(np.uint8)
    return out


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    base = Path(path).resolve().parent
    clip = Path(plan["clip"])
    if not clip.is_absolute():
        clip = (base / clip).resolve()
    if not clip.exists():
        sys.exit(f"Clip not found: {clip}")
    dur = tn_io.probe(clip)["duration"]
    st = tn_settings.load()
    for it in plan["items"]:
        tn_settings.apply(it, st, ("font", "color", "cover", "anim", "platform"))
        it["end"] = min(float(it["end"]), dur - 0.05)
        if it["end"] - it["start"] < 0.5:
            sys.exit(f"'{it['text']}': the text needs at least 0.5 s on screen (start {it['start']}, end {it['end']}).")
        if it["anim"] not in tn_text.ANIMS:
            sys.exit(f"Unknown anim '{it['anim']}'. Use one of: {', '.join(tn_text.ANIMS)}")
    return plan, clip


def place_items(clip, items, meta, matte, quiet=False):
    """Placement + contrast check for every text item; prints the checks unless quiet."""
    W, H = meta["w"], meta["h"]
    placed = []
    for it in items:
        p = plan_item(it, meta, matte)
        placed.append(p)
        p["contrast"] = contrast_check(clip, it, p, W, H)
        if "shadow" not in it:  # light text on a light wall (or dark on dark) gets a stronger glow to stay legible
            it["shadow"] = 0.35 if p["contrast"] >= 3 else 0.75
        if p["contrast"] < 1.6:
            p.setdefault("note", f"Low contrast ({p['contrast']:.1f}:1) between the text color and the background. Try a darker or lighter color.")
        msg = f"'{it['text']}' {it['start']:.2f}-{it['end']:.2f}s: size {p['size']}px, y {p['yf']:.2f}, " \
              f"hidden {p['hidden_mean']:.0%}, worst letter {p['worst_letter']:.0%}, {p['letters_partly_hidden']} letters partly hidden, " \
              f"contrast {p['contrast']:.1f}:1 ({'good' if p['contrast'] >= 3 else 'low: stronger shadow added'})"
        if not quiet:
            print(msg + (f"\n  ! {p['note']}" if p.get("note") else ""))
    return placed


def behind_frames(clip, matte, items, placed, fps, size, scale, t0, t1):
    """Rendered frames (text behind the person) from t0 to t1 at output size."""
    nfr = int(round((t1 - t0) * fps))
    rd = tn_io.Reader(clip, size=size, start=t0 or None, end=t1, frames=nfr)
    ra = tn_io.Reader(matte, size=size, gray=True, start=t0 or None, end=t1, frames=nfr)
    for i, (fr, al) in enumerate(zip(rd, ra)):
        t = t0 + i / fps
        img = fr
        for p, it in zip(placed, items):
            lay = text_layer(p, it, t, size[0], size[1], scale_px=scale)
            if lay is not None:
                img = compose_roi(img, al, lay)
        yield img


def cmd_behind(a):
    plan, clip = load_plan(a.plan)
    out = Path(a.out)
    wd = work_dir(out)
    meta = tn_io.probe(clip)
    W, H, fps = meta["w"], meta["h"], meta["fps"]
    matte = ensure_matte(clip, wd)
    items = plan["items"]
    placed = place_items(clip, items, meta, matte)
    report = [{k: v for k, v in p.items() if k not in ("block", "_cache")} | {"text": it["text"]} for p, it in zip(placed, items)]

    if a.stills:
        times = []
        for it in items:
            s, e = it["start"], it["end"]
            times += [s + 0.15, s + 0.45, (s + e) / 2, e - 0.1]
        sheet = []
        for t in times:
            fr = next(iter(tn_io.Reader(clip, start=t, frames=1)))
            al = next(iter(tn_io.Reader(matte, size=(W, H), gray=True, start=t, frames=1)))
            img = fr
            for p, it in zip(placed, items):
                lay = text_layer(p, it, t, W, H)
                if lay is not None:
                    img = compose_roi(img, al, lay)
            th = 360
            sheet.append(cv2.resize(img, (int(W * th / H), th), interpolation=cv2.INTER_AREA))
            cv2.putText(sheet[-1], f"{t:.2f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cols = 4
        rows = [np.hstack(sheet[i:i + cols] + [np.zeros_like(sheet[0])] * (cols - len(sheet[i:i + cols]))) for i in range(0, len(sheet), cols)]
        png = out.with_suffix(".stills.png")
        cv2.imwrite(str(png), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
        print(f"stills -> {png}")
        out.with_suffix(".checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        return

    scale = 0.5 if a.preview else 1.0
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    t0 = max(0.0, min(it["start"] for it in items) - 1.0) if a.preview else 0.0
    t1 = min(meta["duration"], max(it["end"] for it in items) + 1.0) if a.preview else meta["duration"]
    if a.preview and meta["audio"]:  # the preview is cut to the text's range: take the matching audio
        tmp_audio = wd / f"{out.stem}.audio.m4a"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-i", str(clip), "-t", f"{t1 - t0:.3f}",
                        "-vn", "-c:a", "aac", str(tmp_audio)], check=False)
        audio = tmp_audio if tmp_audio.exists() else None
    elif a.preview:
        audio = None
    else:
        audio = clip if meta["audio"] else None
    wr = tn_io.Writer(out, ow, oh, fps, audio_from=audio, preset="veryfast" if a.preview else "medium")
    tstart, n = time.time(), 0
    for img in behind_frames(clip, matte, items, placed, fps, (ow, oh), scale, t0, t1):
        wr.write(img)
        n += 1
    wr.close()
    print(f"{'preview' if a.preview else 'render'} -> {out} ({n} frames, {n / max(time.time() - tstart, 1e-6):.1f} fps)")
    out.with_suffix(".checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- freeze effects
def load_freeze_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    base = Path(path).resolve().parent
    clip = Path(plan["clip"])
    clip = clip if clip.is_absolute() else (base / clip).resolve()
    if not clip.exists():
        sys.exit(f"Clip not found: {clip}")
    dur = tn_io.probe(clip)["duration"]
    st = tn_settings.load()
    for it in plan["items"]:
        if it.get("effect") not in tn_freeze.EFFECTS:
            sys.exit(f"Unknown effect '{it.get('effect')}'. Use one of: {', '.join(tn_freeze.EFFECTS)}")
        it["at"] = float(it["at"])
        if not 0 <= it["at"] < dur:
            sys.exit(f"'at' {it['at']} is outside the clip (0-{dur:.2f} s).")
        it.setdefault("hold", {"intro": 2.4, "snap": 1.6, "comic": 1.8}[it["effect"]])
        it.setdefault("outline", st["outline"])
        it.setdefault("color", st["accent"])
        it.setdefault("platform", st["platform"])
        it.setdefault("sfx", st["sfx"] == "on")
    plan["items"].sort(key=lambda x: x["at"])
    return plan, clip


def pick_freeze_frames(clip, matte, items, fps, W, H):
    """Freeze on the sharpest frame within +-0.25 s of each 'at' (unless "exact": true)."""
    for it in items:
        if it.get("exact"):
            it["frame"] = int(round(it["at"] * fps))
            continue
        t0 = max(0.0, it["at"] - 0.25)
        n = int(0.5 * fps) + 1
        sw = 480
        sh = int(round(H * sw / W))
        frs = list(tn_io.Reader(clip, size=(sw, sh), start=t0 or None, frames=n))
        als = list(tn_io.Reader(matte, size=(sw, sh), gray=True, start=t0 or None, frames=n))
        k = tn_freeze.sharpest(frs, als)
        it["frame"] = int(round(t0 * fps)) + k
    return items


def read_audio(clip, sr):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def build_freeze_audio(clip, meta, items, fps, n_out, wav):
    """Original audio with silence during each hold, plus the effect sounds. Writes a 16-bit wav."""
    import wave
    sr = tn_sfx.SR
    src = read_audio(clip, sr) if meta["audio"] else np.zeros((int(meta["duration"] * sr), 2), np.float32)
    out = np.zeros((int(round(n_out / fps * sr)) + sr, 2), np.float32)
    pos_src, pos_out = 0, 0
    for it in items:
        cut = int(round((it["frame"] + 1) / fps * sr))       # audio up to the end of the frozen frame
        seg = src[pos_src:cut]
        out[pos_out:pos_out + len(seg)] = seg
        pos_out += len(seg)
        hold_start = pos_out / sr
        for name, dt, gain in tn_freeze.SFX[it["effect"]]:
            if it.get("sfx", True):
                tn_sfx.mix_into(out, tn_sfx.SOUNDS[name](), hold_start + dt, gain * float(it.get("sfx_gain", 1.0)))
        pos_out += int(round(it["n_hold"] / fps * sr))
        pos_src = cut
    seg = src[pos_src:]
    out[pos_out:pos_out + len(seg)] = seg[:len(out) - pos_out]
    out = out[:int(round(n_out / fps * sr))]
    pk = np.abs(out).max()
    if pk > 0.98:  # never clip
        out *= 0.98 / pk
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype("<i2").tobytes())


def cmd_freeze(a):
    plan, clip = load_freeze_plan(a.plan)
    out = Path(a.out)
    wd = work_dir(out)
    meta = tn_io.probe(clip)
    W, H, fps = meta["w"], meta["h"], meta["fps"]
    matte = ensure_matte(clip, wd)
    items = pick_freeze_frames(clip, matte, plan["items"], fps, W, H)
    scale = 0.5 if a.preview else 1.0
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    for it in items:
        it["n_hold"] = int(round(it["hold"] * fps))
        fr = next(iter(tn_io.Reader(clip, size=(ow, oh), start=it["frame"] / fps, frames=1)))
        al = next(iter(tn_io.Reader(matte, size=(ow, oh), gray=True, start=it["frame"] / fps, frames=1)))
        it["_state"] = tn_freeze.prepare(it["effect"], fr, al, it)
        it["_before"] = fr
        print(f"{it['effect']} at {it['at']:.2f}s -> freezes frame {it['frame']} ({it['frame'] / fps:.2f}s), hold {it['hold']:.1f}s")

    if a.stills:
        rows = []
        for it in items:
            us = [0.04, 0.2, 0.45, it["hold"] * 0.6, it["hold"] - 0.08]
            imgs = [it["_before"]] + [tn_freeze.render(it["effect"], it["_state"], u, it["hold"], it) for u in us]
            th = 300
            row = [cv2.resize(x, (int(ow * th / oh), th), interpolation=cv2.INTER_AREA) for x in imgs]
            for x, lab in zip(row, ["before"] + [f"+{u:.2f}s" for u in us]):
                cv2.putText(x, lab, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            rows.append(np.hstack(row))
        png = out.with_suffix(".stills.png")
        cv2.imwrite(str(png), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
        print(f"stills -> {png}")
        return

    n_src = meta["frames"]
    n_out = n_src + sum(it["n_hold"] for it in items)
    wav = wd / f"{out.stem}.audio.wav"
    build_freeze_audio(clip, meta, items, fps, n_out, wav)
    wr = tn_io.Writer(out, ow, oh, fps, audio_from=wav, preset="veryfast" if a.preview else "medium")
    at = {it["frame"]: it for it in items}
    tstart, n = time.time(), 0
    for i, fr in enumerate(tn_io.Reader(clip, size=(ow, oh))):
        wr.write(fr)
        n += 1
        it = at.get(i)
        if it:
            for k in range(it["n_hold"]):
                wr.write(tn_freeze.render(it["effect"], it["_state"], k / fps, it["hold"], it))
                n += 1
    wr.close()
    print(f"{'preview' if a.preview else 'render'} -> {out} ({n} frames, {n / max(time.time() - tstart, 1e-6):.1f} fps)")


# ---------------------------------------------------------------- clones
def cmd_clone(a):
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    base = Path(a.plan).resolve().parent
    res = lambda p: (Path(p) if Path(p).is_absolute() else (base / p)).resolve()
    clip = res(plan["clip"])
    if not clip.exists():
        sys.exit(f"Clip not found: {clip}")
    out = Path(a.out)
    wd = work_dir(out)
    meta = tn_io.probe(clip)
    W, H, fps = meta["w"], meta["h"], meta["fps"]
    matte = ensure_matte(clip, wd)
    scale = 0.5 if a.preview else 1.0
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    fx = []
    for it in plan["items"]:
        eff = it.get("effect")
        if eff == "trail":
            if it.get("style", "fade") not in tn_clone.STYLES:
                sys.exit(f"Unknown style '{it['style']}'. Use one of: {', '.join(tn_clone.STYLES)}")
            e = tn_clone.Trail(clip, matte, it, (ow, oh), fps)
            dmax, dscale = e.drift
            print(f"trail {e.start:.2f}-{e.end:.2f}s: {len(e.stamps)} copies at {', '.join(f'{t:.2f}' for t in e.stamp_times())}s; "
                  f"camera drift {dmax / scale:.0f}px, zoom {dscale * 100:.1f}% ({'aligned' if dmax / scale > 1 else 'locked'})")
            if not e.stamps:
                print("  ! Nobody moved enough in this range to leave copies. Pick the part where the person walks or moves across.")
        elif eff == "two":
            clip_b = res(it["second"])
            if not clip_b.exists():
                sys.exit(f"Second take not found: {clip_b}")
            if tn_io.probe(clip_b)["w"] * H != tn_io.probe(clip_b)["h"] * W:
                print("  ! The second take has a different shape from the first; it is scaled to fit.")
            e = tn_clone.Two(clip, matte, clip_b, ensure_matte(clip_b, wd), it, (ow, oh), fps)
            print(f"two takes {e.start:.2f}-{e.start + e.n / fps:.2f}s, mode {e.mode}" +
                  (f", seam at x={e.seam / ow:.2f} (take B on the {e.b_side})" if e.mode == "split" else ""))
        else:
            sys.exit(f"Unknown effect '{eff}'. Use trail or two.")
        fx.append(e)

    if a.stills:
        sheet = []
        for e in fx:
            span = (e.end + getattr(e, "fade", 0)) if hasattr(e, "end") else e.start + e.n / fps
            for t in np.linspace(e.start + 0.2, min(span, meta["duration"] - 0.1) - 0.1, 5):
                fr = next(iter(tn_io.Reader(clip, size=(ow, oh), start=t, frames=1)))
                al = next(iter(tn_io.Reader(matte, size=(ow, oh), gray=True, start=t, frames=1)))
                img = e.render(fr, al, round(t * fps) / fps)
                th = 300
                sm = cv2.resize(img, (int(ow * th / oh), th), interpolation=cv2.INTER_AREA)
                cv2.putText(sm, f"{t:.2f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                sheet.append(sm)
        rows = [np.hstack(sheet[i:i + 5]) for i in range(0, len(sheet), 5)]
        png = out.with_suffix(".stills.png")
        cv2.imwrite(str(png), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
        print(f"stills -> {png}")
        return

    # sounds: a soft flash as each copy appears (trail only); the clip's own audio is kept as it is
    wav = None
    stamps = [t for e in fx if isinstance(e, tn_clone.Trail) for t in e.stamp_times()[1:]]
    if stamps and plan.get("sfx", tn_settings.load()["sfx"] == "on"):
        import wave
        sr = tn_sfx.SR
        track = read_audio(clip, sr) if meta["audio"] else np.zeros((int(meta["duration"] * sr) + sr, 2), np.float32)
        for t in stamps:
            tn_sfx.mix_into(track, tn_sfx.flash(), t, 0.5)
        pk = np.abs(track).max()
        if pk > 0.98:
            track *= 0.98 / pk
        wav = wd / f"{out.stem}.audio.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((track * 32767).astype("<i2").tobytes())
    audio = wav or (clip if meta["audio"] else None)
    wr = tn_io.Writer(out, ow, oh, fps, audio_from=audio, preset="veryfast" if a.preview else "medium")
    tstart, n = time.time(), 0
    for i, (fr, al) in enumerate(zip(tn_io.Reader(clip, size=(ow, oh)), tn_io.Reader(matte, size=(ow, oh), gray=True))):
        t = i / fps
        img = fr
        for e in fx:
            if e.active(t):
                img = e.render(img, al, t)
        wr.write(img)
        n += 1
    wr.close()
    print(f"{'preview' if a.preview else 'render'} -> {out} ({n} frames, {n / max(time.time() - tstart, 1e-6):.1f} fps)")


# ---------------------------------------------------------------- setup phase
def cmd_settings(a):
    p = tn_settings.path()
    if a.action == "reset":
        if p.exists():
            p.unlink()
        print(f"Settings cleared ({p}). The setup questions will be asked again.")
        return
    if a.action == "set":
        kv = dict(x.split("=", 1) for x in a.values)
        print(f"saved -> {tn_settings.save(kv)}")
    if a.action == "defaults":
        print(f"defaults saved -> {tn_settings.save_defaults()}")
    s = tn_settings.load()
    st = ("saved" if s["_saved"] else ("NOT saved yet: run the setup questions" if len(s["_missing"]) == len(tn_settings.OPTIONS) - len(tn_settings.OPTIONAL) else "NOT finished: still ask " + ", ".join(s["_missing"])))
    print(f"settings file: {p} ({st})")
    for k, (default, allowed, what) in tn_settings.OPTIONS.items():
        print(f"  {k:9} = {s[k]:10}  {what}" + (f"  [{' | '.join(allowed)}]" if allowed else ""))


def cmd_sample(a):
    import tn_sample
    clip = Path(a.clip).resolve()
    if not clip.exists():
        sys.exit(f"Clip not found: {clip}")
    out = Path(a.out)
    wd = work_dir(out)
    meta = tn_io.probe(clip)
    matte = ensure_matte(clip, wd)
    t = time.time()
    tn_sample.run(a.kind, clip, matte, meta, out, at=a.at, text=a.text, tn=sys.modules[__name__])
    print(f"sample ({a.kind}) -> {out} ({time.time() - t:.0f} s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    m = sub.add_parser("matte")
    m.add_argument("clip")
    m.add_argument("--width", type=int, default=None)
    m.add_argument("--work")
    m.set_defaults(fn=cmd_matte)
    b = sub.add_parser("behind", help="text behind the person")
    b.add_argument("plan", help="plan JSON: {clip, items:[{text,start,end,font,color,anim,width,y,...}]}")
    b.add_argument("--out", required=True, help="output .mp4 (stills/checks are written next to it)")
    g = b.add_mutually_exclusive_group()
    g.add_argument("--stills", action="store_true", help="4 key stills per text + checks only (fast)")
    g.add_argument("--preview", action="store_true", help="half-size render of the text's range only")
    b.set_defaults(fn=cmd_behind)
    z = sub.add_parser("freeze", help="freeze-frame effects: intro, snap, comic")
    z.add_argument("plan", help="plan JSON: {clip, items:[{effect,at,hold,name,role,outline,color,caption,...}]}")
    z.add_argument("--out", required=True)
    g2 = z.add_mutually_exclusive_group()
    g2.add_argument("--stills", action="store_true")
    g2.add_argument("--preview", action="store_true", help="half-size render of the whole clip")
    z.set_defaults(fn=cmd_freeze)
    c = sub.add_parser("clone", help="clone trail (one take) or two roles (two takes)")
    c.add_argument("plan", help="plan JSON: {clip, items:[{effect:trail,start,end,every,style} | {effect:two,second,end,mode}]}")
    c.add_argument("--out", required=True)
    g3 = c.add_mutually_exclusive_group()
    g3.add_argument("--stills", action="store_true")
    g3.add_argument("--preview", action="store_true", help="half-size render")
    c.set_defaults(fn=cmd_clone)
    st = sub.add_parser("settings", help="show / set / reset the saved setup answers")
    st.add_argument("action", nargs="?", default="show", choices=["show", "set", "reset", "defaults"])
    st.add_argument("values", nargs="*", help="key=value pairs for 'set'")
    st.set_defaults(fn=cmd_settings)
    sp = sub.add_parser("sample", help="every option of one setting side by side on your clip (setup phase)")
    sp.add_argument("kind", choices=["font", "color", "cover", "anim", "outline", "platform", "sfx"])
    sp.add_argument("clip")
    sp.add_argument("--out", required=True)
    sp.add_argument("--at", type=float, help="start time in the clip (default: the middle)")
    sp.add_argument("--text", help="the word to show (default 'Bí mật'); for outline: the name on the card")
    sp.set_defaults(fn=cmd_sample)
    a = ap.parse_args()
    if getattr(a, "preview", False) and getattr(a, "out", None):  # a preview never overwrites the full render
        o = Path(a.out)
        a.out = str(o.with_name(o.stem + ".preview" + o.suffix))
    a.fn(a)


if __name__ == "__main__":
    main()
