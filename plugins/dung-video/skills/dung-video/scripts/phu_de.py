"""Make an .srt subtitle file from a video or audio file with faster-whisper (runs on your computer).

    python phu_de.py "raw/video.mp4" --lang vi --out "exports/video.srt" [--model small]

Whisper makes mistakes (names, numbers, accents): open the .srt and fix it before using it.
Long lines are split so each subtitle stays short and on screen long enough to read.
"""
import argparse
import sys
from pathlib import Path


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def chunks(words, max_chars):
    """Group words into lines of at most max_chars, keeping each word's timing."""
    line, start = [], None
    for w in words:
        text = w.word.strip()
        if not text:
            continue
        candidate = " ".join([x[0] for x in line] + [text])
        if line and len(candidate) > max_chars:
            yield line
            line = []
        line.append((text, w.start, w.end))
    if line:
        yield line


def main() -> int:
    ap = argparse.ArgumentParser(description="Video/audio -> .srt with faster-whisper")
    ap.add_argument("input")
    ap.add_argument("--lang", default="vi", help="language code, e.g. vi or en")
    ap.add_argument("--out", required=True, help="output .srt path")
    ap.add_argument("--model", default="small", help="tiny, base, small, medium, large-v3 (bigger = slower, more accurate)")
    ap.add_argument("--max-chars", type=int, default=42, help="max characters per subtitle line")
    a = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is not installed. Run: python -m pip install faster-whisper")
        return 1
    src, out = Path(a.input), Path(a.out)
    if not src.exists():
        print(f"File not found: {src}")
        return 1
    if out.exists():
        print(f"{out} already exists; choose another name (nothing was overwritten).")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading model '{a.model}' (the first run downloads it)...")
    model = WhisperModel(a.model, device="auto", compute_type="auto")
    segments, info = model.transcribe(str(src), language=a.lang, word_timestamps=True, vad_filter=True)
    cues = []
    for seg in segments:
        words = seg.words or []
        if not words:
            cues.append((seg.start, seg.end, seg.text.strip()))
            continue
        for line in chunks(words, a.max_chars):
            cues.append((line[0][1], line[-1][2], " ".join(x[0] for x in line)))
    # no overlaps: each subtitle ends before the next one starts
    fixed = []
    for i, (s, e, t) in enumerate(cues):
        if i + 1 < len(cues):
            e = min(e, cues[i + 1][0] - 0.04)
        fixed.append((s, max(e, s + 0.3), t))
    out.write_text("".join(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(fixed, 1)), encoding="utf-8")
    print(f"Wrote {len(fixed)} subtitles to {out}. Open it and fix any mistakes before using it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
