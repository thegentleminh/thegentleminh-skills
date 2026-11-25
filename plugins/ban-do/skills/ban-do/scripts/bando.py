#!/usr/bin/env python3
"""ban-do: animated map clips (MP4) from a small JSON scene.

  python bando.py check                      what is installed, is the map data there
  python bando.py data                       download the map data once (Natural Earth, ~18 MB)
  python bando.py find "Đà Nẵng"             look up a country or city
  python bando.py lint scene.json            check the scene before rendering
  python bando.py still scene.json --at 0,2,5 [-o sheet.jpg]   key frames as one picture
  python bando.py render scene.json [-o out.mp4] [--preview]   render the clip (+ contact sheet)
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bd_geo as geo  # noqa: E402

geo.stdout_utf8()


def load_scene(path, preview=False):
    import bd_scene
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Lỗi JSON trong {path}: {e}")
    world = geo.World()
    try:
        return bd_scene.Scene(spec, world, preview=preview)
    except bd_scene.SceneError as e:
        raise SystemExit(f"Lỗi cảnh: {e}")


def free_path(p):
    p = Path(p)
    if not p.exists():
        return p
    i = 2
    while True:
        q = p.with_name(f"{p.stem}-{i}{p.suffix}")
        if not q.exists():
            return q
        i += 1


def ffmpeg_bin():
    return shutil.which("ffmpeg")


# ---------- check / data / find ----------

def cmd_check(a):
    ok = True
    print(f"Python {sys.version.split()[0]}", "OK" if sys.version_info >= (3, 9) else "(cần 3.9+)")
    for mod in ("numpy", "PIL"):
        try:
            m = __import__(mod)
            print(f"{mod} {getattr(m, '__version__', '')} OK")
        except ImportError:
            ok = False
            print(f"{mod}: CHƯA CÓ  ->  python -m pip install numpy pillow")
    f = ffmpeg_bin()
    if f:
        v = subprocess.run([f, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        print(v.split(" Copyright")[0], "OK")
    else:
        ok = False
        print("ffmpeg: CHƯA CÓ  ->  Windows: winget install Gyan.FFmpeg · macOS: brew install ffmpeg")
    print("Dữ liệu bản đồ:", "OK" if geo.have_data() else "CHƯA TẢI  ->  python bando.py data  (~18 MB, một lần)")
    print("Thư mục dữ liệu:", geo.cache_dir())
    return 0 if ok and geo.have_data() else 1


def cmd_data(a):
    d = geo.download()
    t = time.time()
    geo.World()
    print(f"Xong. Dữ liệu ở {d} (đọc lần đầu {time.time() - t:.1f} s).")


def cmd_find(a):
    w = geo.World()
    r = geo.region(a.name)
    if r:
        print(f"vùng  {a.name}  -> \"view\": \"{a.name}\"")
    res = w.search(a.name)
    if not res and not r:
        print("Không thấy. Thử tên tiếng Anh, bỏ dấu, hoặc ghi lon/lat trực tiếp.")
    for kind, code, name, extra in res:
        if kind == "country":
            print(f"nước  {code}  {name}  ({extra})   -> \"fit\": \"{code}\" / \"country\": \"{code}\"")
        else:
            print(f"nơi   {name}  [{code}]  lat, lon = {extra}   -> \"place\": \"{name}\"")
    print("Vùng có sẵn:", ", ".join(geo.REGIONS))


# ---------- lint ----------

def lint(sc, quiet=False):
    import bd_scene
    errors, warns = [], []
    for s, term in bd_scene.forbidden_terms(sc.all_texts()):
        errors.append(f"Chữ {s!r} dùng tên sai ({term}). Dùng Biển Đông, Hoàng Sa, Trường Sa.")
    # Vietnam: whenever (almost) all of mainland Vietnam is in frame, both archipelagos must be too
    vb = sc.w.vn_mainland_bbox
    isl = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in sc.w.islands.items()}
    bad_t = []
    steps = int(sc.duration * 10) + 1
    for i in range(steps):
        t = i / 10
        cx, cy, span = sc.camera(t)
        k = sc.W / span
        x0, x1 = (vb[0] - cx) * k + sc.W / 2, (vb[2] - cx) * k + sc.W / 2
        y0, y1 = sc.H / 2 - (vb[3] - cy) * k, sc.H / 2 - (vb[1] - cy) * k
        area = (x1 - x0) * (y1 - y0)
        ix = max(0, min(x1, sc.W) - max(x0, 0)) * max(0, min(y1, sc.H) - max(y0, 0))
        if area <= 0 or ix / area < 0.9 or (x1 - x0) < sc.W * 0.03:
            continue
        for key, (lon, lat) in isl.items():
            px, py = sc.to_px((cx, cy, span), lon, lat)
            m = 0.02 * sc.W
            if not (m < px < sc.W - m and m < py < sc.H - m):
                bad_t.append((t, key))
    if bad_t:
        ts = sorted({t for t, _ in bad_t})
        which = sorted({k for _, k in bad_t})
        errors.append(f"Việt Nam hiện gần trọn mà thiếu {', '.join(which)} ở {ts[0]:.1f}-{ts[-1]:.1f} s. "
                      "Lùi camera ra hoặc dời tâm sang phải (\"fit\": \"VNM\" đã tính sẵn hai quần đảo).")
    # overlaps and safe area at the moments that matter
    times = {round(k["t"], 2) for k in sc.keys} | {sc.duration - 0.05}
    for e in sc.pins + sc.numbers + sc.titles + sc.labels:
        times.add(round(e["t0"] + 0.7, 2))
    for t in sorted(x for x in times if 0 <= x <= sc.duration):
        boxes = []
        sc.frame(t, collect=boxes)
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if bd_scene.overlap(a[2], b[2]) and min(a[0], b[0]) <= 4:
                    warns.append(f"{t:.1f} s: '{a[1]}' chồng lên '{b[1]}'")
            x0, y0, x1, y1 = a[2]
            if a[0] <= 2 and sc.vertical and a[1] != "title":
                if y1 > sc.H * 0.80 or x1 > sc.W * 0.88:
                    warns.append(f"{t:.1f} s: '{a[1]}' nằm trong vùng nút bấm của TikTok/Shorts (dưới 20% hoặc mép phải)")
            if x0 < 0 or y0 < 0 or x1 > sc.W or y1 > sc.H:
                if a[0] <= 2 or a[0] == 5:
                    warns.append(f"{t:.1f} s: '{a[1]}' bị cắt ở mép khung")
    for k in sc.keys:
        km = math.degrees(k["span"]) * 111.32 * math.cos(math.atan(math.sinh(k["cy"])))
        if km < 150:
            warns.append(f"Khung camera ở {k['t']} s chỉ rộng ~{km:.0f} km: gần thế này bản đồ chỉ còn nền đất trơn "
                         "(không có đường, sông). Nên để 200 km trở lên.")
    for e in sc.pins + sc.numbers + sc.titles + sc.labels + sc.highlights:
        if e["t0"] >= sc.duration:
            warns.append(f"Một mục bắt đầu ở {e['t0']} s, sau khi clip đã hết ({sc.duration} s)")
    warns = list(dict.fromkeys(warns))
    if not quiet:
        for e in errors:
            print("LỖI:", e)
        for w in warns:
            print("Chú ý:", w)
        print(f"Kiểm tra: {len(errors)} lỗi, {len(warns)} chú ý · {sc.aspect} · {sc.duration:.1f} s")
    return errors, warns


def cmd_lint(a):
    sc = load_scene(a.scene)
    errors, _ = lint(sc)
    return 1 if errors else 0


# ---------- stills / sheet ----------

def sheet(frames, path, cols=None):
    from PIL import Image, ImageDraw
    import bd_scene
    if not frames:
        return
    w0, h0 = frames[0][1].size
    th = 560 if h0 > w0 else 300
    tw = int(w0 * th / h0)
    cols = cols or min(len(frames), 6 if h0 > w0 else 3)
    rows = math.ceil(len(frames) / cols)
    pad = 8
    out = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + 30) + pad), (30, 30, 30))
    d = ImageDraw.Draw(out)
    for i, (t, im) in enumerate(frames):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad + 30)
        out.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (x, y + 30))
        d.text((x + 4, y + 4), f"{t:.1f} s", font=bd_scene.font(22), fill=(235, 235, 235))
    out.save(path, quality=90)


def cmd_still(a):
    sc = load_scene(a.scene, preview=a.preview)
    times = [float(x) for x in a.at.split(",")] if a.at else default_times(sc)
    frames = [(t, sc.frame(t)) for t in times]
    out = free_path(a.out or Path("ban-do") / f"{Path(a.scene).stem}-khung.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(frames) == 1:
        frames[0][1].save(out, quality=92)
    else:
        sheet(frames, out)
    print(f"Ảnh: {out}")


def default_times(sc, n=6):
    return [round(sc.duration * (i + 0.5) / n, 2) for i in range(n)]


# ---------- render ----------

def cmd_render(a):
    sc = load_scene(a.scene, preview=a.preview)
    errors, warns = lint(sc, quiet=True)
    if errors:
        for e in errors:
            print("LỖI:", e)
        print("Chưa render: sửa lỗi trên rồi chạy lại.")
        return 1
    for w in warns:
        print("Chú ý:", w)
    f = ffmpeg_bin()
    if not f:
        raise SystemExit("Chưa có ffmpeg. Chạy: python bando.py check")
    stem = Path(a.scene).stem + ("-preview" if a.preview else "")
    out = free_path(a.out or Path("ban-do") / f"{stem}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(sc.duration * sc.fps))
    cmd = [f, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{sc.W}x{sc.H}", "-r", str(sc.fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    want = {int(round(t * sc.fps)) for t in default_times(sc)}
    keep = []
    t0 = time.time()
    try:
        for i in range(n):
            t = i / sc.fps
            im = sc.frame(t)
            proc.stdin.write(im.tobytes())
            if i in want:
                keep.append((t, im))
            if i and i % (sc.fps * 2) == 0:
                el = time.time() - t0
                print(f"  {i}/{n} khung · còn khoảng {el / i * (n - i):.0f} s", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise SystemExit("ffmpeg báo lỗi khi ghi video.")
    sh = out.with_name(out.stem + "-khung.jpg")
    sheet(keep, sh)
    el = time.time() - t0
    print(f"Xong: {out}  ({sc.W}x{sc.H}, {sc.duration:.1f} s, {sc.fps} fps, {el:.0f} s để render, không có âm thanh)")
    print(f"Ảnh kiểm tra: {sh}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="ban-do: animated map clips")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("data").set_defaults(fn=cmd_data)
    p = sub.add_parser("find")
    p.add_argument("name")
    p.set_defaults(fn=cmd_find)
    p = sub.add_parser("lint")
    p.add_argument("scene")
    p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("still")
    p.add_argument("scene")
    p.add_argument("--at", help="giây, cách nhau bằng dấu phẩy: 0,2.5,5")
    p.add_argument("-o", "--out")
    p.add_argument("--preview", action="store_true", help="nửa kích thước, nhanh hơn")
    p.set_defaults(fn=cmd_still)
    p = sub.add_parser("render")
    p.add_argument("scene")
    p.add_argument("-o", "--out")
    p.add_argument("--preview", action="store_true", help="nửa kích thước, nhanh gấp ~3 lần")
    p.set_defaults(fn=cmd_render)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
