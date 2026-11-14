"""Photos for anh-thanh-video: load the right way up, find faces, frame for the output shape. MIT licence.

Each photo becomes a "canvas" a bit larger than the output frame (MARGIN), so the camera can push in
and pan without running out of picture. A photo that fits the shape is cropped around the faces; one
that doesn't (a portrait photo in a 16:9 video, a group shot in 9:16) is shown whole over a blurred,
darkened copy of itself, so nobody gets cut off.
"""
import os
import urllib.request
from pathlib import Path

import cv2
try:  # OpenCV prints a harmless "setPreferableTarget" warning on every run otherwise
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except AttributeError:
    pass
import numpy as np
from PIL import Image, ImageOps

MARGIN = 1.25
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"}
YUNET_URL = "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"


def model_dir():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    d = Path(base) / "anh-thanh-video" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def face_model(download=True):
    """Path to OpenCV's YuNet face model (MIT, ~230 KB). Downloaded once; None if unavailable."""
    p = model_dir() / "face_detection_yunet_2023mar.onnx"
    if p.exists() and p.stat().st_size > 100_000:
        return p
    if not download:
        return None
    try:
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(YUNET_URL, tmp)
        tmp.replace(p)
        return p
    except Exception as e:  # no internet: framing falls back to the picture's centre of interest
        print(f"  (face model not downloaded: {e}; framing uses the centre of the picture)")
        return None


def list_photos(src):
    p = Path(src)
    if p.is_dir():
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in EXTS)
    else:
        files = [p]
    if not files:
        raise SystemExit(f"No photos found in {src} (jpg, png, webp).")
    return files


def load(path, max_side=3000):
    """RGB uint8, rotated the way the phone meant it (EXIF), capped in size."""
    try:
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    except Exception as e:
        raise SystemExit(f"Can't open {path}: {e}. If it's an iPhone HEIC photo, export it as JPG first.")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    return np.asarray(im)


_det = None


def faces(rgb):
    """Face boxes (x, y, w, h) in pixels; empty if none or no model."""
    global _det
    if _det is None:
        m = face_model()
        # 0.75: at 0.6 a bowl of phở gave two "faces"; on 21 test photos 0.75 drops the false ones and keeps real ones
        _det = cv2.FaceDetectorYN.create(str(m), "", (320, 320), 0.75) if m else False
    if _det is False:
        return []
    h, w = rgb.shape[:2]
    s = 640 / max(h, w)
    sm = cv2.resize(rgb, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    _det.setInputSize((sm.shape[1], sm.shape[0]))
    _, f = _det.detect(cv2.cvtColor(sm, cv2.COLOR_RGB2BGR))
    if f is None:
        return []
    tiny = 0.02 * min(sm.shape[:2])  # specks in the background aren't faces worth framing for
    return [tuple(float(v) / s for v in r[:4]) for r in f if min(r[2], r[3]) >= tiny]


def interest_point(rgb, fs):
    """Where the camera should aim: the faces' centre (a bit above), else the most detailed region."""
    h, w = rgb.shape[:2]
    if fs:
        xs = [x + fw / 2 for x, y, fw, fh in fs]
        ys = [y + fh / 2 for x, y, fw, fh in fs]
        return float(np.mean(xs)), float(np.mean(ys))
    g = cv2.cvtColor(cv2.resize(rgb, (160, int(160 * h / w))), cv2.COLOR_RGB2GRAY).astype(np.float32)
    e = cv2.GaussianBlur(np.abs(cv2.Laplacian(g, cv2.CV_32F)), (31, 31), 0)
    y, x = np.unravel_index(np.argmax(e), e.shape)
    return x * w / g.shape[1], y * h / g.shape[0]


def canvas(rgb, out_w, out_h, fit="auto", min_keep=0.62):
    """Photo → canvas (out size × MARGIN) + focus point in canvas pixels + how it was framed.

    auto: crop when the crop keeps at least `min_keep` of the photo and every face; otherwise show it whole
    over a blurred copy. Beat edits pass a low min_keep (filling the screen matters more in fast cuts).
    """
    h, w = rgb.shape[:2]
    cw, ch = int(out_w * MARGIN), int(out_h * MARGIN)
    fs = faces(rgb)
    fx, fy = interest_point(rgb, fs)
    target = cw / ch
    # biggest crop of the photo with the canvas's shape
    if w / h > target:
        crop_h, crop_w = h, int(h * target)
    else:
        crop_w, crop_h = w, int(w / target)
    keeps = (crop_w * crop_h) / (w * h)
    x0 = int(np.clip(fx - crop_w / 2, 0, w - crop_w))
    y0 = int(np.clip(fy - crop_h * 0.42, 0, h - crop_h))  # faces sit a little above the middle
    inside = all(x0 <= x and x + fw <= x0 + crop_w and y0 <= y and y + fh <= y0 + crop_h for x, y, fw, fh in fs)
    mode = fit if fit in ("crop", "blur") else ("crop" if keeps >= min_keep and inside else "blur")
    if mode == "crop":
        c = cv2.resize(rgb[y0:y0 + crop_h, x0:x0 + crop_w], (cw, ch), interpolation=cv2.INTER_AREA)
        focus = ((fx - x0) * cw / crop_w, (fy - y0) * ch / crop_h)
        k = cw / crop_w
        boxes = [((x - x0) * k, (y - y0) * k, fw * k, fh * k) for x, y, fw, fh in fs]
    else:
        # blurred, darker copy filling the frame + the whole photo on top
        s_cover = max(cw / w, ch / h)
        bg = cv2.resize(rgb, (int(w * s_cover) + 1, int(h * s_cover) + 1), interpolation=cv2.INTER_AREA)
        oy, ox = (bg.shape[0] - ch) // 2, (bg.shape[1] - cw) // 2
        bg = bg[oy:oy + ch, ox:ox + cw]
        k = int(min(cw, ch) * 0.08) | 1
        bg = (cv2.GaussianBlur(bg, (k, k), 0) * 0.55).astype(np.uint8)
        s_fit = min(cw / w, ch / h) / MARGIN * 0.96  # the photo fits the visible frame, not the margin
        fw_, fh_ = int(w * s_fit), int(h * s_fit)
        ph = cv2.resize(rgb, (fw_, fh_), interpolation=cv2.INTER_AREA)
        px, py = (cw - fw_) // 2, (ch - fh_) // 2
        sh = np.zeros((ch, cw), np.float32)
        sh[py + 8:py + fh_ + 8, px + 4:px + fw_ + 4] = 1
        sh = cv2.GaussianBlur(sh, (k, k), 0) * 0.5
        bg = (bg * (1 - sh[..., None])).astype(np.uint8)
        bg[py:py + fh_, px:px + fw_] = ph
        c = bg
        focus = (px + fx * s_fit, py + fy * s_fit)
        boxes = [(px + x * s_fit, py + y * s_fit, fw * s_fit, fh * s_fit) for x, y, fw, fh in fs]
    return {"img": c, "focus": focus, "mode": mode, "faces": len(fs), "size": (cw, ch), "boxes": boxes}


def face_rows(cv, ow, oh):
    """Which output rows (0-1) hold faces when the canvas is seen at rest (centred, zoom 1)."""
    cw, ch = cv["size"]
    vh = ch / MARGIN
    y0 = (ch - vh) / 2
    rows = []
    for x, y, fw, fh in cv.get("boxes", []):
        top = (y - fh * 0.35 - y0) / vh      # hair above the detected box
        bot = (y + fh * 1.15 - y0) / vh      # chin below it
        rows.append((max(0.0, top), min(1.0, bot)))
    return rows
