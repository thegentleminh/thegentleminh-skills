"""anh-thanh-video: turn photos into a video. MIT licence.

Commands
  check                       what is installed (ffmpeg, Python packages, models)
  settings [set k=v | reset]  the saved setup answers (plans use them as defaults)
  sample <kind> <photos>      the same few photos in every option of one setting, side by side
  beats <music>               tempo and beat times of a song (what the cuts will follow)
  make  <plan.json>           build the video (--stills / --preview / full)

Modes (plan "mode")
  beat   cut on the beat: photos change every N beats with flash / pop / shake hits; camera moves
         "snap" (snap-and-ease on every beat), "kenburns" (slow push) or "none"
  album  gentle: each photo a few seconds with a slow push toward the faces, soft crossfades,
         cuts nudged onto the music's beats when there is music

Every output is a new file; photos and music are only read.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import atv_beats  # noqa: E402
import atv_io  # noqa: E402
import atv_photos  # noqa: E402
import atv_text  # noqa: E402
import atv_settings  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SHAPES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
SAFE = {"9:16": (0.10, 0.34, 0.05, 0.15), "16:9": (0.06, 0.18, 0.04, 0.04), "1:1": (0.06, 0.2, 0.05, 0.05),
        "4:5": (0.06, 0.22, 0.05, 0.05)}
FPS = 30


def ease_out_expo(x):
    x = min(max(x, 0.0), 1.0)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- timeline
def build_timeline(plan, n_photos, beats):
    """List of segments {photo, t0, t1, beats (inner beat times), strong}; total length."""
    mode = plan.get("mode", "beat")
    segs = []
    if mode == "beat":
        if not beats:
            raise SystemExit("Beat mode needs music with a beat. Add \"music\" to the plan, or use \"mode\": \"album\".")
        k = int(plan.get("beats_per_photo", 2))
        b, strong = beats["beats"], beats["strong"]
        want = plan.get("length")
        count = n_photos if not want else max(n_photos, int(math.ceil(want / (k * 60 / beats["bpm"]))))
        cuts = [0.0] + [b[i] for i in range(k, len(b), k)]
        if len(cuts) - 1 < count:
            count = len(cuts) - 1
            print(f"  ! The song is too short for every photo at {k} beats each: using {count}. Use a longer song or fewer beats per photo.")
        for i in range(count):
            t0, t1 = cuts[i], cuts[i + 1]
            inner = [x for x in b if t0 + 0.05 < x < t1 - 0.05]
            si = b.index(t0) if t0 in b else 0
            segs.append({"photo": i % n_photos, "t0": t0, "t1": t1, "beats": inner, "strong": bool(strong[si]) if t0 in b else True})
    else:
        per = float(plan.get("per_photo", 3.5))
        want = plan.get("length")
        count = n_photos if not want else max(n_photos, int(math.ceil(want / per)))
        t = 0.0
        for i in range(count):
            t1 = t + per
            if beats:  # nudge each cut onto the nearest beat
                bb = np.array(beats["beats"])
                near = bb[np.argmin(np.abs(bb - t1))] if len(bb) else t1
                if abs(near - t1) < per * 0.3:
                    t1 = float(near)
            segs.append({"photo": i % n_photos, "t0": t, "t1": t1, "beats": [], "strong": False})
            t = t1
    return segs, segs[-1]["t1"]


# ---------------------------------------------------------------- camera
SNAP_PATTERN = [(1.14, 0.0, 0.0), (1.06, 0.06, 0.0), (1.10, -0.05, 0.02), (1.0, 0.0, -0.03), (1.16, 0.03, -0.02)]


def camera(seg, idx, t, cv, plan):
    """(cx, cy, z) in canvas pixels at time t inside segment."""
    cw, ch = cv["size"]
    c0 = np.array([cw / 2, ch / 2])
    lean = c0 + (np.array(cv["focus"]) - c0) * 0.5  # aim between the middle and the faces
    move = plan.get("move", "snap" if plan.get("mode", "beat") == "beat" else "kenburns")
    u = (t - seg["t0"]) / max(seg["t1"] - seg["t0"], 1e-6)
    if move == "none":
        return lean[0], lean[1], 1.0
    if move == "parallax":  # depth does the moving (atv_depth.view); the camera only drifts toward the faces
        c = c0 + (lean - c0) * (0.5 + 0.5 * ease_in_out(u))
        return c[0], c[1], 1.0
    if move == "kenburns":
        zin = idx % 2 == 0
        z = 1.0 + 0.09 * (ease_in_out(u) if zin else 1 - ease_in_out(u))
        c = c0 + (lean - c0) * ease_in_out(u)
        return c[0], c[1], z
    # snap-and-ease: every beat the camera jumps to the next framing fast, then glides
    keys = [seg["t0"]] + seg["beats"]
    k = max(i for i, kt in enumerate(keys) if kt <= t + 1e-9)
    def key(i):
        z, dx, dy = SNAP_PATTERN[(i + idx) % len(SNAP_PATTERN)]
        return np.array([lean[0] + dx * cw, lean[1] + dy * ch, z])
    prev = key(k - 1) if k > 0 else np.array([lean[0] - 0.08 * cw * (1 if idx % 2 else -1), lean[1], 1.22])  # arrives with a whip
    cur = key(k)
    e = ease_out_expo((t - keys[k]) / 0.28)
    p = prev + (cur - prev) * e
    p[2] *= 1 + 0.025 * (t - keys[k])  # keeps drifting a little
    return p[0], p[1], p[2]


def view(cv, cx, cy, z, ow, oh, shake=(0.0, 0.0)):
    cw, ch = cv["size"]
    vw, vh = cw / (atv_photos.MARGIN * z), ch / (atv_photos.MARGIN * z)
    cx = min(max(cx, vw / 2), cw - vw / 2)
    cy = min(max(cy, vh / 2), ch - vh / 2)
    sx, sy = ow / vw, oh / vh
    m = np.float32([[sx, 0, -(cx - vw / 2) * sx + shake[0]], [0, sy, -(cy - vh / 2) * sy + shake[1]]])
    return cv2.warpAffine(cv["img"], m, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ---------------------------------------------------------------- hits on the cut
HITS = ("flash", "pop", "shake", "glitch")


def hit_state(seg, t, hits, first, rng_seed):
    """zoom multiplier, (dx, dy) shake px fraction, flash alpha, glitch px fraction."""
    if first:
        return 1.0, (0.0, 0.0), 0.0, 0.0
    u = t - seg["t0"]
    g = 1.0 if seg["strong"] else 0.6
    z = 1 + 0.08 * g * (1 - ease_out_expo(u / 0.3)) if "pop" in hits else 1.0
    sh = (0.0, 0.0)
    if "shake" in hits or "glitch" in hits:
        rng = np.random.default_rng(rng_seed)
        ang = rng.uniform(0, 2 * math.pi)
        amp = (0.022 if "glitch" in hits else 0.012) * g * math.exp(-u / 0.07) * math.sin(2 * math.pi * 26 * u)
        sh = (amp * math.cos(ang), amp * math.sin(ang))
    fl = 0.55 * g * math.exp(-u / 0.045) if "flash" in hits else 0.0
    gl = 0.012 * g * math.exp(-u / 0.06) if "glitch" in hits else 0.0
    return z, sh, fl, gl


# ---------------------------------------------------------------- text
def text_layers(plan, ow, oh, shape):
    """Title (start) and per-photo captions as (canvas RGBA, cx, cy, scale) builders."""
    top, bottom, left, right = SAFE[shape]
    out = {"title": None, "captions": {}}
    title = plan.get("title")
    if title:
        up = plan.get("title_upper", True)
        size = atv_text.fit_size(title, plan.get("font", "dam"), (1 - left - right) * ow * 0.9, upper=up)
        size = min(size, int(oh * 0.09))
        tb = atv_text.TextBlock(title, plan.get("font", "dam"), size, color=plan.get("color", "#ffffff"), upper=up)
        # two places to try: lower third (above the caption area) or upper third; the one clear of faces wins
        bands = [oh * (1 - bottom) - tb.H * 1.6, oh * top + tb.H * 0.9]
        out["title"] = (tb.canvas(shadow=0.6), ow * (0.5 + (left - right) / 2), bands, tb.H)
    caps = plan.get("captions", {})
    for key, txt in caps.items():
        size = min(atv_text.fit_size(txt, "dam-vua", (1 - left - right) * ow * 0.85), int(oh * 0.05))
        tb = atv_text.TextBlock(txt, plan.get("caption_font", "dam-vua"), size, color=plan.get("color", "#ffffff"))
        bands = [oh * (1 - bottom) - tb.H / 2, oh * top + tb.H / 2]
        out["captions"][key] = (tb.canvas(shadow=0.7), ow * (0.5 + (left - right) / 2), bands, tb.H)
    return out


def clear_band(bands, h, face_rows, oh):
    """The band (centre y in px) overlapping the faces least; the first one wins ties."""
    def overlap(cy):
        t, b = (cy - h / 2) / oh, (cy + h / 2) / oh
        pad = 0.04  # text right under a chin looks cramped even when it doesn't touch the face
        return sum(max(0.0, min(b, fb + pad) - max(t, ft - pad)) for ft, fb in face_rows)
    return min(bands, key=overlap)


def paste(img, canvas_rgba, cx, cy, alpha, scale=1.0):
    if alpha <= 0.001:
        return img
    lay = atv_text.place(canvas_rgba, img.shape[1], img.shape[0], cx, cy, scale, 0.0)
    a = lay[..., 3:4] * alpha
    f = img.astype(np.float32) / 255
    return np.clip((f * (1 - a) + lay[..., :3] * a) * 255 + 0.5, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- audio
def loudnorm_2pass(src, dst, start, dur, fade_out):
    """Music cut to [start, start+dur], short fade-in, fade-out, then a two-pass loudness match to -14 LUFS."""
    af = f"afade=t=in:d=0.05,afade=t=out:st={max(0, dur - fade_out):.3f}:d={fade_out:.3f}"
    base = ["ffmpeg", "-v", "info", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
    r = subprocess.run(base + ["-af", af + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        subprocess.run(base + ["-af", af, "-ar", "48000", str(dst)], check=True, capture_output=True)
        return
    j = json.loads(m.group(0))
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    subprocess.run(base + ["-af", af + "," + ln, "-ar", "48000", str(dst)], check=True, capture_output=True)


# ---------------------------------------------------------------- make
def resolve(base, p):
    p = Path(p)
    return p if p.is_absolute() else (base / p).resolve()


def cmd_beats(a):
    r = atv_beats.beats(a.music, a.start, a.dur)
    b = r["beats"]
    print(f"{r['bpm']} BPM, {len(b)} beats in {r['duration']:.1f} s; first beats: {', '.join(f'{x:.2f}' for x in b[:8])}")
    if a.json:
        Path(a.json).write_text(json.dumps(r), encoding="utf-8")


def cmd_make(a):
    plan_path = Path(a.plan).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if isinstance(plan.get("hits"), str):  # a preset name: manh / vua / nhe / khong
        plan["hits"] = atv_settings.HITS.get(plan["hits"], [plan["hits"]])
    atv_settings.apply(plan)
    base = plan_path.parent
    files = atv_photos.list_photos(resolve(base, plan["photos"])) if isinstance(plan["photos"], str) \
        else [resolve(base, p) for p in plan["photos"]]
    shape = plan.get("shape", "9:16")
    if shape not in SHAPES:
        sys.exit(f"Unknown shape '{shape}'. Use one of: {', '.join(SHAPES)}")
    W, H = SHAPES[shape]
    scale = 0.5 if a.preview else 1.0
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    music = resolve(base, plan["music"]) if plan.get("music") else None
    mstart = float(plan.get("music_start", 0))
    beats = atv_beats.beats(music, mstart) if music else None
    if beats:
        print(f"music: {beats['bpm']} BPM, {len(beats['beats'])} beats")
    hits = plan.get("hits", ["flash", "pop", "shake"])
    for h in hits:
        if h not in HITS:
            sys.exit(f"Unknown hit '{h}'. Use: {', '.join(HITS)}")
    segs, total = build_timeline(plan, len(files), beats)
    print(f"{len(segs)} shots, {total:.1f} s, mode {plan.get('mode', 'beat')}, move {plan.get('move', 'auto')}")
    out = Path(a.out)
    if a.preview:  # never let a preview overwrite (or be overwritten by) the full render
        out = out.with_name(out.stem + ".preview" + out.suffix)
    out.parent.mkdir(parents=True, exist_ok=True)

    cache = {}

    def cv_for(i):
        if i not in cache:
            if len(cache) > 6:
                cache.pop(next(iter(cache)))
            img = atv_photos.load(files[i])
            keep = 0.25 if plan.get("mode", "beat") == "beat" else 0.62
            cache[i] = atv_photos.canvas(img, ow, oh, plan.get("fit", "auto"), min_keep=keep)
        return cache[i]

    txt = text_layers(plan, ow, oh, shape)
    xf = float(plan.get("crossfade", 0.6)) if plan.get("mode") == "album" else 0.0

    def frame_at(t):
        si = max(i for i, s in enumerate(segs) if s["t0"] <= t + 1e-9)
        s = segs[si]
        cv = cv_for(s["photo"])
        cx, cy, z = camera(s, si, t, cv, plan)
        hz, sh, fl, gl = hit_state(s, t, hits, si == 0, si) if plan.get("mode", "beat") == "beat" else (1, (0, 0), 0, 0)
        def render(cv_, seg_, idx_, tt, zmul=1.0, shk=(0.0, 0.0)):
            x_, y_, z_ = camera(seg_, idx_, tt, cv_, plan)
            if plan.get("move") == "parallax":
                import atv_depth
                u_ = ease_in_out((tt - seg_["t0"]) / max(seg_["t1"] - seg_["t0"], 1e-6))
                return atv_depth.view(cv_, x_, y_, z_ * zmul, u_, ow, oh, swing=1 if idx_ % 2 else -1)
            return view(cv_, x_, y_, z_ * zmul, ow, oh, shk)

        img = render(cv, s, si, t, hz, (sh[0] * ow, sh[1] * oh))
        if xf and si + 1 < len(segs) and t > s["t1"] - xf:  # crossfade into the next photo
            n = segs[si + 1]
            cvn = cv_for(n["photo"])
            nxt = render(cvn, n, si + 1, n["t0"])
            k = ease_in_out((t - (s["t1"] - xf)) / xf)
            img = cv2.addWeighted(img, 1 - k, nxt, k, 0)
        if gl > 0:  # RGB split
            d = int(gl * ow)
            img = img.copy()
            img[..., 0] = np.roll(img[..., 0], d, axis=1)
            img[..., 2] = np.roll(img[..., 2], -d, axis=1)
        if fl > 0.003:
            img = cv2.addWeighted(img, 1 - fl, np.full_like(img, 255), fl, 0)
        rows = cv.setdefault("_rows", atv_photos.face_rows(cv, ow, oh))
        if txt["title"] and t < min(3.0, total):
            a_ = min(1.0, t / 0.4) * min(1.0, (min(3.0, total) - t) / 0.4)
            can, tcx, bands, th = txt["title"]
            # decided once on the first shot, so the title doesn't jump when the photo changes
            ty = txt.setdefault("_title_y", clear_band(bands, th, atv_photos.face_rows(cv_for(segs[0]["photo"]), ow, oh), oh))
            img = paste(img, can, tcx, ty, a_, 1 + 0.03 * t / 3)
        name = files[s["photo"]].name
        if name in txt["captions"]:
            can, tcx, bands, th = txt["captions"][name]
            a_ = min(1.0, (t - s["t0"]) / 0.3) * min(1.0, (s["t1"] - t) / 0.3)
            img = paste(img, can, tcx, clear_band(bands, th, rows, oh), a_)
        return img

    if a.stills:
        ts = [s["t0"] + f * (s["t1"] - s["t0"]) for s in segs[:6] for f in (0.02, 0.5)]
        th = 360
        tiles = []
        for t in ts:
            im = frame_at(t)
            im = cv2.resize(im, (int(ow * th / oh), th), interpolation=cv2.INTER_AREA)
            cv2.putText(im, f"{t:.2f}s", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
            tiles.append(im)
        cols = 6 if oh > ow else 4
        rows = [np.hstack(tiles[i:i + cols] + [np.zeros_like(tiles[0])] * (cols - len(tiles[i:i + cols]))) for i in range(0, len(tiles), cols)]
        png = out.with_suffix(".stills.png")
        cv2.imwrite(str(png), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
        print(f"stills -> {png}")
        for i, f in enumerate(files[:len(segs)]):
            c = cv_for(i)
            print(f"  {f.name}: {c['mode']}, {c['faces']} face(s)")
        return

    audio = None
    if music:
        audio = out.with_name(out.stem + ".music.wav")
        fade = 0.35 if plan.get("mode", "beat") == "beat" else 1.5
        loudnorm_2pass(music, audio, mstart, total, fade)
    n = int(round(total * FPS))
    wr = atv_io.Writer(out, ow, oh, FPS, audio_from=audio, preset="veryfast" if a.preview else "medium")
    t0 = time.time()
    for i in range(n):
        wr.write(frame_at(i / FPS))
    wr.close()
    if audio and audio.exists():
        audio.unlink()  # the levelled music is inside the video now
    print(f"{'preview' if a.preview else 'render'} -> {out} ({n} frames, {n / max(time.time() - t0, 1e-6):.1f} fps)")


def cmd_check(a):
    import shutil
    ok = lambda b: "OK " if b else "-- "
    v = sys.version_info
    print(ok(v >= (3, 10)) + f"Python {v.major}.{v.minor}", sys.executable)
    for exe in ("ffmpeg", "ffprobe"):
        print(ok(shutil.which(exe)) + exe, shutil.which(exe) or "(missing: needed for everything)")
    for mod, why in (("numpy", "needed"), ("cv2", "needed (pip install opencv-python)"), ("PIL", "needed (pip install pillow)")):
        try:
            __import__(mod)
            print(ok(True) + mod)
        except ImportError:
            print(ok(False) + f"{mod} ({why})")
    try:
        import onnxruntime  # noqa: F401
        print(ok(True) + "onnxruntime (parallax / 3D move available)")
    except ImportError:
        print(ok(False) + "onnxruntime (optional: only for move 'parallax'; pip install onnxruntime, about 15 MB)")
    fm = atv_photos.model_dir() / Path(atv_photos.YUNET_URL).name
    print(ok(fm.exists()) + "face model", "downloaded" if fm.exists() else "downloads once on first use (~230 KB)")


def cmd_settings(a):
    if a.action == "reset":
        print("settings removed:", atv_settings.reset())
        return
    if a.action == "set":
        print("saved:", atv_settings.save(dict(v.split("=", 1) for v in a.values)))
    if a.action == "defaults":
        print("defaults saved:", atv_settings.save_defaults())
    s = atv_settings.load()
    state = "(saved)" if s["_saved"] else ("(NOT saved yet: run the setup questions)" if len(s["_missing"]) == len(atv_settings.OPTIONS) - len(atv_settings.OPTIONAL)
                                           else "(NOT finished: still ask " + ", ".join(s["_missing"]) + ")")
    print("Settings", state, "-", atv_settings.path())
    for k, (d, allowed, what) in atv_settings.OPTIONS.items():
        print(f"  {k:6s} = {s[k]!s:9s} {what}" + (f"  [{', '.join(allowed)}]" if allowed else ""))


def cmd_sample(a):
    """'Show all for comparison': the user's own photos in every option of one setting, labelled, side by side."""
    import shutil
    import tempfile
    kind = a.kind
    values = list(atv_settings.OPTIONS[kind][1])
    if kind == "move":
        values = [v for v in values if v != "auto"]
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            values.remove("parallax")
            print("(parallax left out: onnxruntime isn't installed)")
    names = atv_settings.NAMES_VI.get(kind, {})
    photos = Path(a.photos)
    files = atv_photos.list_photos(photos) if photos.is_dir() else [photos]
    files = files[:4]
    if not files:
        sys.exit("no photos found")
    th = 640
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copy(HERE.parent / "fonts" / "BeVietnamPro-ExtraBold.ttf", tmp / "label.ttf")
        clips = []
        for i, v in enumerate(values):
            plan = {"photos": [str(f.resolve()) for f in files], "length": a.length}
            if a.music:
                plan["music"] = str(Path(a.music).resolve())
                plan["music_start"] = a.music_start
            if kind == "font":
                plan["title"] = a.text
            if kind == "hits":
                plan["hits"] = atv_settings.HITS[v]
                plan["mode"] = "beat"
            else:
                plan[kind] = v
            if kind == "mode":
                plan["move"] = "snap" if v == "beat" else "kenburns"
            if kind == "mode" and v == "album":
                plan["per_photo"] = max(1.5, a.length / len(files))
            pp = tmp / f"plan-{i}.json"
            pp.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            print(f"making {names.get(v, v)} ({i + 1}/{len(values)})...", flush=True)
            out = tmp / f"v{i}.mp4"
            cmd_make(argparse.Namespace(plan=str(pp), out=str(out), stills=False, preview=True))
            (tmp / f"v{i}.txt").write_text(names.get(v, v), encoding="utf-8")
            clips.append(out)
        inputs, fl = [], []
        for i, c in enumerate(clips):
            inputs += ["-i", c.name]
            fl.append(f"[{i}:v]scale=-2:{th},setsar=1,fps=30,trim=0:{a.length},setpts=PTS-STARTPTS,"
                      f"drawbox=x=0:y=0:w=iw:h=54:color=black@0.7:t=fill,"
                      f"drawtext=fontfile=label.ttf:textfile=v{i}.txt:fontsize=30:fontcolor=white:x=(w-tw)/2:y=11[t{i}]")
        fl.append("".join(f"[t{i}]" for i in range(len(clips))) + f"hstack=inputs={len(clips)}[v]")
        amap = []
        if a.music:
            fl.append(f"[0:a]atrim=0:{a.length},asetpts=PTS-STARTPTS[a]")
            amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fl), "-map", "[v]", *amap,
                            "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", "sample.mp4"],
                           cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            sys.exit("ffmpeg failed: " + r.stderr[-1500:])
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp / "sample.mp4"), a.out)
    print("sample ->", a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("beats", help="tempo and beats of a song")
    b.add_argument("music")
    b.add_argument("--start", type=float, default=0.0)
    b.add_argument("--dur", type=float)
    b.add_argument("--json")
    b.set_defaults(fn=cmd_beats)
    m = sub.add_parser("make", help="build the video from a plan")
    m.add_argument("plan")
    m.add_argument("--out", required=True)
    g = m.add_mutually_exclusive_group()
    g.add_argument("--stills", action="store_true", help="2 stills per shot for the first 6 shots (fast)")
    g.add_argument("--preview", action="store_true", help="half size")
    m.set_defaults(fn=cmd_make)
    c = sub.add_parser("check", help="what is installed")
    c.set_defaults(fn=cmd_check)
    st = sub.add_parser("settings", help="saved setup answers")
    st.add_argument("action", nargs="?", default="show", choices=["show", "set", "reset", "defaults"])
    st.add_argument("values", nargs="*", help="key=value pairs for 'set'")
    st.set_defaults(fn=cmd_settings)
    sp = sub.add_parser("sample", help="every option of one setting, side by side, on the user's photos")
    sp.add_argument("kind", choices=["shape", "mode", "move", "hits", "font", "fit"])
    sp.add_argument("photos", help="a folder of photos (the first 4 are used) or one photo")
    sp.add_argument("--music", help="their song (needed to judge mode and hits)")
    sp.add_argument("--music-start", type=float, default=0.0)
    sp.add_argument("--length", type=float, default=6.0)
    sp.add_argument("--text", default="Mùa hè 2026", help="title shown in the font sample")
    sp.add_argument("--out", required=True)
    sp.set_defaults(fn=cmd_sample)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
