# SPDX-License-Identifier: GPL-3.0-or-later
"""Person matte for a whole video with Robust Video Matting (RVM).

This one file is GPL-3.0 because it loads RVM (github.com/PeterL1n/RobustVideoMatting, GPL-3.0).
The rest of tach-nguoi is MIT and only talks to this script through files on disk: it reads a video
and writes the matte as a lossless grayscale video (white = person). RVM itself is downloaded by
torch.hub onto the user's own machine the first time it runs; it is not part of this repository.

Usage (inside the tach-nguoi Python environment that has torch):
    python rvm_matte.py <video> <alpha.mkv> [--model resnet50|mobilenetv3] [--width 1280]
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402
import tn_io  # noqa: E402


def load(model_name):
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    hub = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch")) / "hub" / "PeterL1n_RobustVideoMatting_master"
    if hub.exists():  # already downloaded once: no network needed
        model = torch.hub.load(str(hub), model_name, source="local", pretrained=True)
    else:
        model = torch.hub.load("PeterL1n/RobustVideoMatting", model_name, trust_repo=True)
    return model.eval().to(dev), dev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", default=None, help="resnet50 (best, GPU) or mobilenetv3 (faster, fine on CPU)")
    ap.add_argument("--width", type=int, default=0, help="matte at this width (0 = source width)")
    a = ap.parse_args()

    import torch
    model_name = a.model or ("resnet50" if torch.cuda.is_available() else "mobilenetv3")
    model, dev = load(model_name)
    meta = tn_io.probe(a.video)
    w = a.width or meta["w"]
    w -= w % 2
    h = int(round(meta["h"] * w / meta["w"])) // 2 * 2
    # RVM's own guidance: run its coarse pass at roughly 512 px on the long side
    ratio = min(1.0, max(0.1, 512 / max(w, h)))
    rd = tn_io.Reader(a.video, size=(w, h))
    wr = tn_io.Writer(a.out, w, h, meta["fps"], gray=True)
    rec = [None] * 4
    t0, n = time.time(), 0
    with torch.no_grad():
        for fr in rd:
            x = torch.from_numpy(fr.copy()).to(dev).permute(2, 0, 1)[None].float().div_(255)
            _, pha, *rec = model(x, *rec, ratio)
            wr.write((pha[0, 0].clamp(0, 1).mul(255).byte().cpu().numpy()))
            n += 1
            if n % 100 == 0:
                print(f"  matte {n}/{meta['frames']} frames ({n / (time.time() - t0):.1f} fps)", flush=True)
    wr.close()
    print(f"matte done: {n} frames, {w}x{h}, {model_name} on {dev}, {n / max(time.time() - t0, 1e-6):.1f} fps -> {a.out}")


if __name__ == "__main__":
    main()
