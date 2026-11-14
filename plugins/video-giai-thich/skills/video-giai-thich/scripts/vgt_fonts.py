"""Check that fonts cover every Vietnamese letter (or the exact text of a video).

python vgt_fonts.py FONT.ttf [FONT2.ttf ...] [--text script.txt]

A font that lacks a letter makes the browser borrow it from another font, so one
letter (often ằ, ỡ, ự) looks different from the rest. Run this before using a new font.
"""
import argparse, sys, unicodedata
from fontTools.ttLib import TTFont

BASE = "aăâeêioôơuưy"
TONES = ["", "\u0301", "\u0300", "\u0309", "\u0303", "\u0323"]  # sắc huyền hỏi ngã nặng


def vietnamese_letters():
    out = set("đĐ")
    for b in BASE:
        for t in TONES:
            c = unicodedata.normalize("NFC", b + t)
            out.add(c); out.add(c.upper())
    return out


def missing(font_path, chars):
    cmap = TTFont(font_path, lazy=True).getBestCmap()
    return sorted(c for c in chars if not c.isspace() and ord(c) not in cmap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fonts", nargs="+")
    ap.add_argument("--text", help="check exactly the characters in this file")
    a = ap.parse_args()
    chars = vietnamese_letters()
    if a.text:
        chars = set(unicodedata.normalize("NFC", open(a.text, encoding="utf-8").read()))
    bad = 0
    for f in a.fonts:
        m = missing(f, chars)
        print(("OK  " if not m else "MISSING ") + f + ("" if not m else ": " + " ".join(m)))
        bad += bool(m)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
