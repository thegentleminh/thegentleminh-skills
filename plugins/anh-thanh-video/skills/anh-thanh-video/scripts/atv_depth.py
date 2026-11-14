"""2.5D parallax for anh-thanh-video: depth from one photo, then near things move more than far things.
MIT licence.

Depth: Depth Anything V2 Small (Apache-2.0), the ONNX build from huggingface.co/onnx-community
(fp16, ~50 MB, downloaded once on first use, CPU via onnxruntime, ~0.5 s per photo).

Two looks, chosen per photo:
  layered     a clear near object (people, a bowl) is cut out as its own layer, the background behind it is
              filled in, and the layer moves faster than the background. Chosen when depth jumps sharply at
              the object's edge.
  continuous  smooth scenery (water, hills, fields): every pixel zooms a little more the nearer it is.
              No cut-out, so no seam across the water.
"""
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np

import atv_photos

URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_fp16.onnx"
NAME = "depth_anything_v2_small_fp16.onnx"
_sess = None


def model(download=True):
    p = atv_photos.model_dir() / NAME
    if p.exists() and p.stat().st_size > 10_000_000:
        return p
    if not download:
        return None
    tmp = p.with_suffix(".part")
    print("  downloading the depth model once (~50 MB, Apache-2.0)...", flush=True)
    urllib.request.urlretrieve(URL, tmp)
    tmp.replace(p)
    return p


def session():
    global _sess
    if _sess is None:
        try:
            import onnxruntime as ort
        except ImportError:
            raise SystemExit("Parallax needs onnxruntime: pip install onnxruntime (about 15 MB). Everything else works without it.")
        so = ort.SessionOptions()
        # the fp16 build trips a graph-fusion bug in onnxruntime 1.23 when optimisations are on
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        _sess = ort.InferenceSession(str(model()), so, providers=["CPUExecutionProvider"])
    return _sess


def nearness(rgb):
    """0 = far, 1 = near, same size as the image."""
    s = session()
    h, w = rgb.shape[:2]
    x = cv2.resize(rgb, (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    d = s.run(None, {s.get_inputs()[0].name: x})[0][0].astype(np.float32)
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)


def prepare(cv):
    """Adds depth, the foreground layer (if any) and a filled background plate to a photo canvas."""
    img = cv["img"]
    ch, cw = img.shape[:2]
    d = cv2.GaussianBlur(nearness(img), (0, 0), 1.5)
    out = {"depth": d}
    u8 = (d * 255).astype(np.uint8)
    thr, _ = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = (u8 > thr).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    keep = np.zeros_like(mask)
    k9 = np.ones((9, 9), np.uint8)
    jumps = []
    # only people get their own layer: near shapes without a face (a roof, a door frame, flowers) are
    # often wrong in depth, and a wrong layer shows as a sliding edge. Everything else gets the smooth push.
    face_pts = [(int(x + w_ / 2), int(y + h_ / 2)) for x, y, w_, h_ in cv.get("boxes", [])]
    face_pts = [(x, y) for x, y in face_pts if 0 <= x < cw and 0 <= y < ch]
    if cv.get("mode") != "crop":
        face_pts = []  # whole photo over a blurred copy: depth of the blurred part means nothing
    for k in range(1, n):
        if st[k][4] < 0.01 * cw * ch:
            continue
        if not any(lab[y, x] == k for x, y in face_pts):
            continue
        comp = (lab == k).astype(np.uint8)
        # a real separate object: depth jumps across its edge (smooth ground or water doesn't)
        ring_in = comp - cv2.erode(comp, k9)
        ring_out = cv2.dilate(comp, k9) - comp
        if not ring_in.any() or not ring_out.any():
            continue
        j = float(d[ring_in > 0].mean() - d[ring_out > 0].mean())
        if j > 0.12:
            keep |= comp
            jumps.append(j)
    jump = max(jumps) if jumps else 0.0
    area = keep.mean()
    # a long straight horizontal edge means the shape took in a floor, a railing or a table: moving it
    # would show a seam or tear, so such photos get the smooth push instead
    widths = keep.sum(axis=1).astype(np.float32) / cw
    step = float(np.abs(np.diff(widths)).max()) if keep.any() else 0.0
    out["step"] = round(step, 3)
    out["layered"] = bool(jump > 0.12 and 0.03 < area < 0.6 and step < 0.3)
    out["jump"], out["area"] = round(jump, 3), round(float(area), 3)
    if out["layered"]:
        a = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 1.2)
        out["fg_alpha"] = a
        # background plate: fill where the object was (a bit wider), inpainted at quarter size for speed
        hole = cv2.dilate(keep, np.ones((int(0.03 * min(cw, ch)) | 1,) * 2, np.uint8))
        s = 0.25
        sm = cv2.resize(img, (int(cw * s), int(ch * s)), interpolation=cv2.INTER_AREA)
        hs = cv2.resize(hole, (sm.shape[1], sm.shape[0]), interpolation=cv2.INTER_NEAREST)
        fill = cv2.inpaint(cv2.cvtColor(sm, cv2.COLOR_RGB2BGR), hs, 7, cv2.INPAINT_TELEA)
        fill = cv2.cvtColor(cv2.resize(fill, (cw, ch), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
        fill = cv2.GaussianBlur(fill, (0, 0), 3)
        hb = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 3)[..., None]
        out["bg"] = (img * (1 - hb) + fill * hb).astype(np.uint8)
        out["bg_depth"] = np.where(hole > 0, cv2.inpaint((d * 255).astype(np.uint8), hole, 7, cv2.INPAINT_TELEA) / 255.0, d).astype(np.float32)
    cv["px"] = out
    return out


_grid = {}


def view(cv, cx, cy, z, u, ow, oh, amount=1.0, swing=1):
    """Frame at progress u (0-1) of the move: the whole picture pushes in, near things more."""
    px = cv.get("px") or prepare(cv)
    cw, ch = cv["size"]
    vw, vh = cw / (atv_photos.MARGIN * z), ch / (atv_photos.MARGIN * z)
    cx = min(max(cx, vw / 2), cw - vw / 2)
    cy = min(max(cy, vh / 2), ch - vh / 2)
    key = (ow, oh)
    if key not in _grid:
        _grid[key] = np.meshgrid(np.arange(ow, dtype=np.float32), np.arange(oh, dtype=np.float32))
    qx, qy = _grid[key]
    cx, cy = float(cx), float(cy)
    X0 = (cx - vw / 2 + qx * (vw / ow)).astype(np.float32)
    Y0 = (cy - vh / 2 + qy * (vh / oh)).astype(np.float32)
    kb, kf = 0.07 * amount, 0.13 * amount
    side = 0.015 * amount * swing * vw * u
    if px["layered"]:
        bg, dmap = px["bg"], px["bg_depth"]
    else:
        bg, dmap = cv["img"], px["depth"]
    d = cv2.remap(dmap, X0, Y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    zf = 1 + kb * u * d                    # nearer pixels zoom more
    X = (cx + (X0 - cx) / zf - side * 0.5 * d).astype(np.float32)
    Y = (cy + (Y0 - cy) / zf).astype(np.float32)
    out = cv2.remap(bg, X, Y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if px["layered"]:
        zf2 = 1 + kf * u
        Xf = (cx + (X0 - cx) / zf2 - side).astype(np.float32)
        Yf = (cy + (Y0 - cy) / zf2).astype(np.float32)
        fg = cv2.remap(cv["img"], Xf, Yf, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        a = cv2.remap(px["fg_alpha"], Xf, Yf, cv2.INTER_LINEAR, borderValue=0)[..., None]
        out = (out * (1 - a) + fg * a).astype(np.uint8)
    return out
