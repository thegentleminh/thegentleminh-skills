"""Read a video-giai-thich script.

One line per scene, starting with the scene id in brackets. Inside a line:
  /          splits the scene into separate on-screen sentences (cues)
  *words*    highlighted words (can span several words)
  dọc_đường  keep these words on one line (shown with a non-breaking space)
  {6|sáu}    show "6" on screen, say "sáu"

[s4] Không khí đầy những *phân tử* nhỏ xíu. / Xanh bị dội gần *gấp {6|sáu} lần* đỏ.
"""
import json, re, sys, unicodedata

SUB = re.compile(r"\{([^|}]*)\|([^}]*)\}")
NBSP = " "


def parse(text):
    beats = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = unicodedata.normalize("NFC", raw.strip())
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[([A-Za-z0-9_-]+)\]\s*(.+)$", line)
        if not m:
            sys.exit(f"script line {n}: start it with a scene id like [s1]")
        bid, body = m.groups()
        cues, hl = [], False
        for part in body.split(" / "):
            toks = []
            for t in part.split():
                start_hl = t.startswith("*")
                if start_hl:
                    t, hl = t[1:], True
                # the closing * may sit before or after punctuation: *diệp_lục,* and *diệp_lục*, both work
                em = re.match(r"^(.*)\*([.,!?;:…\"'”’)]*)$", t)
                end_hl = bool(em)
                if end_hl:
                    t = em.group(1) + em.group(2)
                show = SUB.sub(r"\1", t).replace("_", NBSP)
                say = SUB.sub(r"\2", t).replace("_", " ")
                toks.append({"show": show, "say": say, "hl": hl, "n": len(say.split())})
                if end_hl:
                    hl = False
            if toks:
                cues.append({"tokens": toks})
        beats.append({"id": bid, "cues": cues})
    if not beats:
        sys.exit("script is empty")
    return beats


def spoken_words(beats):
    """Every spoken word in order (what the voice says)."""
    return [w for b in beats for c in b["cues"] for t in c["tokens"] for w in t["say"].split()]


def spoken_text(beats):
    return "\n".join(" ".join(t["say"] for c in b["cues"] for t in c["tokens"]) for b in beats)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    b = parse(open(sys.argv[1], encoding="utf-8").read())
    print(json.dumps(b, ensure_ascii=False, indent=1)[:2000])
    print(len(spoken_words(b)), "spoken words,", len(spoken_text(b)), "characters")
