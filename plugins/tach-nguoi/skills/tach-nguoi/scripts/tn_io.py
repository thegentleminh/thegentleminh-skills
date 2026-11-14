"""Video in/out helpers for tach-nguoi: probe a clip, read frames, write frames. MIT licence.

Everything goes through ffmpeg/ffprobe on PATH as raw pipes, so OpenCV's own codecs are never needed.
"""
import json
import shutil
import subprocess
import sys

import numpy as np


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"{tool} not found on PATH. Install ffmpeg first (the skill's setup step explains how).")


def probe(path):
    """Width, height, fps, duration, frame count and whether there is audio."""
    need("ffprobe")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in v.get("avg_frame_rate", v["r_frame_rate"]).split("/"))
    fps = num / den if den else 30.0
    dur = float(v.get("duration") or info["format"]["duration"])
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"]) % 360
    if rot in (90, 270):  # phone clips: ffmpeg autorotates, so report the shape we will actually get
        w, h = h, w
    return {"w": w, "h": h, "fps": fps, "duration": dur, "frames": int(round(dur * fps)),
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}


class Reader:
    """Iterates frames as HxWx3 uint8 RGB (or HxW gray), optionally scaled to (w, h)."""

    def __init__(self, path, size=None, gray=False, start=None, end=None, frames=None):
        need("ffmpeg")
        meta = probe(path)
        self.w, self.h = size or (meta["w"], meta["h"])
        self.ch = 1 if gray else 3
        cmd = ["ffmpeg", "-v", "error"]
        if start:
            cmd += ["-ss", f"{start:.3f}"]
        cmd += ["-i", str(path)]
        if end is not None:
            cmd += ["-t", f"{end - (start or 0):.3f}"]
        if frames:  # stop ffmpeg itself, so a reader that is not drained to the end doesn't error
            cmd += ["-frames:v", str(int(frames))]
        cmd += ["-an", "-vf", f"scale={self.w}:{self.h}:flags=area", "-f", "rawvideo",
                "-pix_fmt", "gray" if gray else "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.n = self.w * self.h * self.ch

    def __iter__(self):
        while True:
            buf = self.p.stdout.read(self.n)
            if len(buf) < self.n:
                break
            a = np.frombuffer(buf, np.uint8)
            yield a.reshape(self.h, self.w) if self.ch == 1 else a.reshape(self.h, self.w, 3)
        self.p.stdout.close()
        self.p.wait()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def close(self):
        """Stop early without ffmpeg complaining about a closed pipe."""
        if self.p.poll() is None:
            self.p.kill()
            self.p.wait()


class Writer:
    """Writes RGB frames to an H.264 mp4 (with the source's audio) or gray frames to a lossless mkv."""

    def __init__(self, path, w, h, fps, audio_from=None, gray=False, crf=18, preset="medium"):
        need("ffmpeg")
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray" if gray else "rgb24",
               "-s", f"{w}x{h}", "-r", f"{fps:.6f}", "-i", "-"]
        if gray:
            cmd += ["-c:v", "ffv1", "-pix_fmt", "gray", str(path)]
        else:
            if audio_from:
                cmd += ["-i", str(audio_from), "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
            cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(path)]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def write(self, frame):
        self.p.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            sys.exit("ffmpeg failed while writing the output (see the message above).")
