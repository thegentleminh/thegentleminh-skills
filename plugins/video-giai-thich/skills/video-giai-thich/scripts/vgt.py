"""video-giai-thich: helper commands around a HyperFrames explainer project.

python vgt.py doctor                                  check what's installed
python vgt.py check FOLDER                            HyperFrames' check (pinned), expected warnings hidden
python vgt.py settings [set key=value ... | reset]    the saved setup answers
python vgt.py new FOLDER                              a new video project with the saved settings
python vgt.py sync FOLDER                             time scenes and words to voice/voice.json
python vgt.py stills FOLDER --look poster --at 2,9,20 still frames (contact sheet)
python vgt.py sample FOLDER --window 17,26 [--var look|reveal --values a,b] --out sample.mp4
                                                      the same seconds in every option, side by side
python vgt.py render FOLDER --look poster --out video.mp4 [--music song.mp3]
python vgt.py looks | setup-project FOLDER | finish IN OUT

Renders use HyperFrames (Apache-2.0, https://github.com/heygen-com/hyperframes) through npx.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LOOKS_DIR = HERE.parent / "looks"
HF_VERSION = "0.8.112"
VALUE_NAMES = {"reveal": {"word": "Từng chữ", "sentence": "Cả câu"}}
LOOKS = {  # id: Vietnamese name shown to the user
    "in-riso": "In riso",
    "bang-phan": "Bảng phấn",
    "bao-giay": "Báo giấy",
    "ban-ve": "Bản vẽ",
    "poster": "Poster",
}


def npx():
    exe = shutil.which("npx")
    if not exe:
        sys.exit("Node.js is not installed (npx not found). Install Node 20+ from https://nodejs.org and try again.")
    return exe


def hf(*args, cwd=None):
    cmd = [npx(), "-y", f"hyperframes@{HF_VERSION}", *map(str, args)]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        sys.exit(f"HyperFrames failed: {' '.join(args[:2])}")
    return r.stdout


def ffmpeg(*args, cwd=None):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-2000:])


def check_look(look):
    if look not in LOOKS:
        sys.exit(f"Unknown look '{look}'. Choose from: {', '.join(LOOKS)}")


def cmd_looks(a):
    for k, v in LOOKS.items():
        print(f"{k:10s} {v}")


def cmd_setup_project(a):
    for src, name in ((LOOKS_DIR, "looks"), (HERE.parent / "runtime", "vgt")):
        dst = Path(a.project) / name
        keep = (dst / "vgt-timing.js").read_bytes() if (dst / "vgt-timing.js").exists() else None
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        if keep:
            (dst / "vgt-timing.js").write_bytes(keep)
        print(name, "copied to", dst)


EXPECTED_WARNINGS = ("nested_structure_needs_subcomposition", "timeline_track_too_dense", "connector_orphan")


def cmd_check(a):
    """HyperFrames' own check at the pinned version; hides warnings that every project of this skill gets."""
    r = subprocess.run([npx(), "-y", f"hyperframes@{HF_VERSION}", "check"], cwd=a.project, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    txt = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    lines, skip = [], False
    for ln in txt.splitlines():
        if any(w in ln for w in EXPECTED_WARNINGS):
            skip = True
            continue
        if skip and ln.startswith("    "):  # the indented detail lines of a hidden warning
            continue
        skip = False
        lines.append(ln)
    print("\n".join(lines))
    print(f"(hidden: expected warnings {', '.join(EXPECTED_WARNINGS)}; scenes live in one file on purpose)")
    sys.exit(r.returncode)


def cmd_doctor(a):
    """Check everything this skill needs; say what's missing and what turns off without it."""
    ok = True

    def line(good, name, detail, need=True):
        nonlocal ok
        ok &= good or not need
        print(f"  {'OK ' if good else ('MISSING' if need else 'optional, not found')}  {name}: {detail}")

    print("video-giai-thich doctor")
    v = sys.version_info
    line(v >= (3, 10), "Python", f"{v.major}.{v.minor} (needs 3.10+)")
    for exe in ("ffmpeg", "ffprobe"):
        p = shutil.which(exe)
        line(bool(p), exe, p or "install it (Windows: winget install --id Gyan.FFmpeg -e; macOS: brew install ffmpeg)")
    node = shutil.which("node")
    nv = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip() if node else ""
    major = int(nv.lstrip("v").split(".")[0]) if nv else 0
    line(major >= 20, "Node.js", (nv or "not found") + " (needs 20+, https://nodejs.org)")
    try:
        import fontTools  # noqa: F401
        line(True, "fontTools", "installed")
    except ImportError:
        line(False, "fontTools", "pip install fonttools  (font checks)")
    try:
        import faster_whisper  # noqa: F401
        line(True, "faster-whisper", "installed (timing your own recording)", need=False)
    except ImportError:
        line(False, "faster-whisper", "pip install faster-whisper  (only to time your own recording)", need=False)
    line(bool(os.environ.get("ELEVENLABS_API_KEY")), "ElevenLabs key",
         "set" if os.environ.get("ELEVENLABS_API_KEY") else "ELEVENLABS_API_KEY not set (only for ElevenLabs voices)", need=False)
    if major >= 20:
        print("  ...asking HyperFrames to check itself (first run downloads it and a headless Chrome)")
        r = subprocess.run([npx(), "-y", f"hyperframes@{HF_VERSION}", "doctor"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        txt = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
        for want in ("FFmpeg", "Chrome"):
            m = re.search(rf"([✓✗])\s+{want}\s+(.*)", txt)
            line(bool(m and m.group(1) == "✓"), f"HyperFrames {want}", m.group(2).strip()[:90] if m else "not reported")
    print("All set." if ok else "Something required is missing (see above).")
    sys.exit(0 if ok else 1)


def cmd_settings(a):
    import vgt_settings as S
    if a.action == "reset":
        print("settings removed:", S.reset())
        return
    if a.action == "set":
        upd = dict(p.split("=", 1) for p in a.pairs)
        print("saved:", S.save(upd))
    s = S.load()
    print("Settings", "(saved)" if s["_saved"] else "(NOT saved yet: run the setup questions)", "-", S.path())
    for k, (d, allowed, what) in S.OPTIONS.items():
        print(f"  {k:10s} = {s[k]!s:24s} {what}" + (f"  [{', '.join(allowed)}]" if allowed else ""))


def cmd_new(a):
    """A new video project from the template, with the saved settings as its defaults."""
    import vgt_settings as S
    proj = Path(a.project).resolve()
    if proj.exists() and any(proj.iterdir()):
        sys.exit(f"{proj} already exists and isn't empty")
    proj.parent.mkdir(parents=True, exist_ok=True)
    hf("init", proj.name, "--non-interactive", "--example=blank", cwd=proj.parent)
    for f in ("CLAUDE.md", "AGENTS.md"):  # generic HyperFrames notes; this skill's SKILL.md is the guide
        if (proj / f).exists():
            (proj / f).unlink()
    s = S.load()
    tpl = (HERE.parent / "templates" / "index.html").read_text(encoding="utf-8")
    handle = s["handle"].replace('"', "").replace("'", "’")
    tpl = tpl.replace("{{LOOK}}", s["look"]).replace("{{REVEAL}}", s["reveal"]).replace("{{HANDLE}}", handle)
    (proj / "index.html").write_text(tpl, encoding="utf-8")
    shutil.copy(HERE.parent / "templates" / "script.txt", proj / "script.txt")
    cmd_setup_project(argparse.Namespace(project=str(proj)))
    print(f"new project {proj} (look {s['look']}, text {s['reveal']}, voice {s['voice']})")


def set_attr(tag, name, value):
    if re.search(rf'\s{name}="[^"]*"', tag):
        return re.sub(rf'(\s{name}=")[^"]*(")', rf"\g<1>{value}\g<2>", tag)
    return tag[:-1] + f' {name}="{value}">'


def cmd_sync(a):
    """Time scenes and on-screen words to the voice: writes vgt/vgt-timing.js and updates index.html."""
    import vgt_script
    proj = Path(a.project)
    beats = vgt_script.parse((proj / "script.txt").read_text(encoding="utf-8"))
    voice = json.loads((proj / "voice" / "voice.json").read_text(encoding="utf-8"))
    words = voice["words"]
    if len(words) != len(vgt_script.spoken_words(beats)):
        sys.exit("voice.json doesn't match script.txt (word count differs): re-run vgt_voice.py after editing the script")
    end = round(max(words[-1]["e"] + a.tail, 0.0 if voice.get("audio", True) else voice["duration"]), 2)
    cues, flat, k = [], [], 0
    for b in beats:
        for c in b["cues"]:
            toks = []
            for t in c["tokens"]:
                ws = words[k:k + t["n"]]
                for w in ws:
                    flat.append({"beat": b["id"], "say": w["say"], "s": w["s"], "e": w["e"]})
                k += t["n"]
                toks.append({"show": t["show"], "hl": t["hl"], "s": ws[0]["s"], "e": ws[-1]["e"]})
            cues.append({"beat": b["id"], "start": round(max(0.0, toks[0]["s"] - 0.08), 3), "tokens": toks})
    for i, c in enumerate(cues):
        c["end"] = round(cues[i + 1]["start"] - 0.05, 3) if i + 1 < len(cues) else end
        c["out"] = i + 1 < len(cues)
    starts = {}
    for c in cues:
        starts.setdefault(c["beat"], c["start"])
    ids = [b["id"] for b in beats]
    bt = {}
    for i, bid in enumerate(ids):
        s = 0.0 if i == 0 else max(0.0, starts[bid] - 0.2)
        bt[bid] = {"start": round(s, 3)}
    for i, bid in enumerate(ids):
        bt[bid]["end"] = bt[ids[i + 1]]["start"] if i + 1 < len(ids) else end
    timing = {"duration": end, "beats": bt, "cues": cues, "words": flat}
    (proj / "vgt").mkdir(exist_ok=True)
    (proj / "vgt" / "vgt-timing.js").write_text(
        "// written by vgt.py sync from script.txt + voice/voice.json; do not edit by hand\nwindow.VGT = "
        + json.dumps(timing, ensure_ascii=False) + ";\n", encoding="utf-8")

    html = (proj / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<div[^>]*data-composition-id="[^"]*"[^>]*>', html)
    if not m:
        sys.exit("index.html has no root <div data-composition-id=...>")
    html = html.replace(m.group(0), set_attr(m.group(0), "data-duration", end), 1)
    missing = []
    for bid in ids:
        sm = re.search(rf'<section[^>]*\sid="{re.escape(bid)}"[^>]*>', html)
        if not sm:
            missing.append(bid)
            continue
        tag = set_attr(set_attr(sm.group(0), "data-start", bt[bid]["start"]), "data-duration",
                       round(bt[bid]["end"] - bt[bid]["start"], 3))
        html = html.replace(sm.group(0), tag, 1)
    audio = f'<audio id="vgt-voice" src="voice/voice.wav" data-start="0" data-duration="{voice["duration"]}" data-track-index="9"></audio>'
    if not voice.get("audio", True):  # no-voice video: text timed for reading, music only
        html = re.sub(r'\s*<audio id="vgt-voice"[^>]*></audio>', "", html)
    elif 'id="vgt-voice"' in html:
        html = re.sub(r'<audio id="vgt-voice"[^>]*></audio>', audio, html)
    else:
        m2 = re.search(r'<div[^>]*data-composition-id="[^"]*"[^>]*>', html)
        html = html[:m2.end()] + "\n      " + audio + html[m2.end():]
    (proj / "index.html").write_text(html, encoding="utf-8")
    extra = [s for s in re.findall(r'<section[^>]*\sid="([^"]+)"', html) if s not in ids]
    print(f"synced {len(ids)} scenes, {len(cues)} sentences, {len(flat)} words; video {end:.2f} s")
    for bid in ids:
        print(f"  {bid}: {bt[bid]['start']:6.2f} - {bt[bid]['end']:6.2f}")
    if missing:
        print("WARNING: no <section> in index.html for:", ", ".join(missing))
    if extra:
        print("WARNING: sections not in the script (never shown):", ", ".join(extra))


LOOK_DECL = re.compile(r'("id":"look"[^\]]*?"default":")([^"]+)(")')


def project_look(project):
    """The look the project was made with (its default), else the saved setting, else in-riso."""
    m = LOOK_DECL.search((Path(project) / "index.html").read_text(encoding="utf-8"))
    if m:
        return m.group(2)
    import vgt_settings
    return vgt_settings.load()["look"]


def project_copy_with_look(project, look, tmp):
    """Snapshots can't take variables, so make a throwaway copy whose default look is `look`."""
    src = Path(project)
    dst = Path(tmp) / f"p-{look}"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", "renders", "snapshots", "node_modules", ".git"))
    html = (dst / "index.html").read_text(encoding="utf-8")
    if not LOOK_DECL.search(html):
        sys.exit("index.html has no 'look' variable declaration (start projects with `vgt.py new`)")
    html = LOOK_DECL.sub(lambda m: m.group(1) + look + m.group(3), html, count=1)
    (dst / "index.html").write_text(html, encoding="utf-8")
    return dst


def cmd_stills(a):
    a.look = a.look or project_look(a.project)
    check_look(a.look)
    out = Path(a.out or Path(a.project) / "snapshots" / a.look).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        p = project_copy_with_look(a.project, a.look, tmp)
        hf("snapshot", p, "--at", a.at, "--no-end", "--describe", "false", "-o", out)
    print("stills in", out)


def render_look(project, look, out, fps=None, quality=None, variables=None):
    v = {"look": look} if look else {}
    v.update(variables or {})
    args = ["render", Path(project).resolve(), "--variables", json.dumps(v, ensure_ascii=False), "-o", Path(out).resolve()]
    if fps:
        args += ["--fps", fps]
    if quality:
        args += ["--quality", quality]
    hf(*args)


def loudness(path):
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-ac", "1", "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(m.stderr[m.stderr.rindex("{"):m.stderr.rindex("}") + 1])


def music_mix(video, music, out_wav, has_voice):
    """Music bed: looped to the video length, faded, about 16 dB under the voice and ducked further
    while the voice speaks (sidechain). Without a voice the music is the whole soundtrack."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout.strip())
    gain = (-30.0 if has_voice else -14.0) - float(loudness(music)["input_i"])
    bed = (f"aloop=loop=-1:size=2e9,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,aformat=channel_layouts=mono,"
           f"volume={gain:.2f}dB,afade=t=in:d=0.6,afade=t=out:st={max(0.0, dur - 1.5):.3f}:d=1.5")
    if has_voice:
        chain = ("[1:a]" + bed + "[m];[0:a]aformat=channel_layouts=mono,asplit[v][sc];"
                 "[m][sc]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=400[md];"
                 "[v][md]amix=inputs=2:normalize=0:duration=first[o]")
        ffmpeg("-i", video, "-i", music, "-filter_complex", chain, "-map", "[o]", "-ar", "48000", out_wav)
    else:
        ffmpeg("-i", music, "-filter_complex", "[0:a]" + bed + "[o]", "-map", "[o]", "-ar", "48000", out_wav)


def finish_audio(src, dst, target=-14.0, music=None):
    """HyperFrames mixes in stereo at its own level: make the final mono at -14 LUFS (two-pass, one linear gain).
    Phones and TikTok sum stereo anyway, and one level keeps every video equally loud."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                        str(src)], capture_output=True, text=True)
    has_voice = bool(r.stdout.strip())
    if not has_voice and not music:  # no voice and no music: nothing to level
        shutil.copy(src, dst)
        return None
    with tempfile.TemporaryDirectory() as tmp:
        audio_src = src
        if music:
            audio_src = Path(tmp) / "mix.wav"
            music_mix(src, music, audio_src, has_voice)
        js = loudness(audio_src)
        f = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
             f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
        if music:
            ffmpeg("-i", src, "-i", audio_src, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-ac", "1", "-af", f,
                   "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dst)
        else:
            ffmpeg("-i", src, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-ac", "1", "-af", f, "-ar", "48000",
                   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst)
    return float(js["input_i"])


def cmd_render(a):
    a.look = a.look or project_look(a.project)
    check_look(a.look)
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_name(out.stem + ".raw" + out.suffix)
    render_look(a.project, a.look, raw)
    before = finish_audio(raw, out, music=a.music or None)
    raw.unlink()
    if before is None:
        print("NOTE: this video has no sound (no voice and no --music). Add --music <file> for a music bed.")
    print("wrote", out, "" if before is None else f"(audio {before:.1f} -> -14 LUFS, mono)")


def cmd_finish(a):
    before = finish_audio(Path(a.src), Path(a.out), music=a.music or None)
    print("wrote", a.out, "" if before is None else f"(audio {before:.1f} -> -14 LUFS, mono)")


def cmd_sample(a):
    var = a.var
    if var == "look":
        values = a.values.split(",") if a.values else (a.looks.split(",") if a.looks else list(LOOKS))
        for l in values:
            check_look(l)
        names = {l: LOOKS[l] for l in values}
    else:
        if not a.values:
            sys.exit("--values is required with --var (e.g. --var reveal --values word,sentence)")
        values = a.values.split(",")
        names = {v: VALUE_NAMES.get(var, {}).get(v, v) for v in values}
    looks = values
    t0, t1 = map(float, a.window.split(","))
    tw, th = 360, 640
    cols = 3 if len(looks) > 2 else len(looks)
    rows = -(-len(looks) // cols)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(LOOKS_DIR / "fonts" / "BeVietnamPro-ExtraBold.ttf", Path(tmp) / "label.ttf")
        inputs, filters = [], []
        for i, l in enumerate(looks):
            print(f"rendering {names[l]} ({i + 1}/{len(looks)})...", flush=True)
            clip = Path(tmp) / f"{l}.mp4"
            if var == "look":
                render_look(a.project, l, clip, fps=15, quality="draft")
            else:
                render_look(a.project, a.look, clip, fps=15, quality="draft", variables={var: l})
            label = names[l]
            (Path(tmp) / f"{l}.txt").write_text(label, encoding="utf-8")
            inputs += ["-i", clip.name]
            filters.append(
                f"[{i}:v]trim={t0}:{t1},setpts=PTS-STARTPTS,fps=15,scale={tw}:{th},"
                f"drawbox=x=0:y=0:w={tw}:h=58:color=black@0.72:t=fill,"
                f"drawtext=fontfile=label.ttf:textfile={l}.txt:fontsize=34:fontcolor=white:x=(w-tw)/2:y=12[v{i}]")
        n = len(looks)
        cells = rows * cols
        for j in range(n, cells):  # fill empty grid cells with black
            filters.append(f"color=c=black:s={tw}x{th}:r=15:d={t1 - t0}[v{j}]")
        layout = "|".join(f"{(k % cols) * tw}_{(k // cols) * th}" for k in range(cells))
        filters.append("".join(f"[v{k}]" for k in range(cells)) + f"xstack=inputs={cells}:layout={layout}:fill=black[out]")
        # keep the voice (same in every tile) so timing choices can be judged by ear too
        has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                    "-of", "csv=p=0", str(Path(tmp) / f"{looks[0]}.mp4")], capture_output=True, text=True).stdout.strip()
        amap = []
        if has_audio:
            filters.append(f"[0:a]atrim={t0}:{t1},asetpts=PTS-STARTPTS,aformat=channel_layouts=mono[aout]")
            amap = ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k"]
        ffmpeg(*inputs, "-filter_complex", ";".join(filters), "-map", "[out]", *amap, "-c:v", "libx264", "-crf", "24",
               "-pix_fmt", "yuv420p", *([] if amap else ["-an"]), "sample.mp4", cwd=tmp)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(Path(tmp) / "sample.mp4"), a.out)
    print("wrote", a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("looks")
    s = sub.add_parser("setup-project"); s.add_argument("project")
    s = sub.add_parser("stills"); s.add_argument("project"); s.add_argument("--look", default=None, help="default: the project's look")
    s.add_argument("--at", required=True); s.add_argument("--out")
    s = sub.add_parser("sample"); s.add_argument("project"); s.add_argument("--window", required=True)
    s.add_argument("--looks"); s.add_argument("--var", default="look"); s.add_argument("--values")
    s.add_argument("--look", default=None, help="look to use when comparing another option"); s.add_argument("--out", required=True)
    s = sub.add_parser("render"); s.add_argument("project"); s.add_argument("--look", default=None, help="default: the project's look")
    s.add_argument("--out", required=True); s.add_argument("--music", default="")
    s = sub.add_parser("sync"); s.add_argument("project"); s.add_argument("--tail", type=float, default=0.6)
    s = sub.add_parser("finish"); s.add_argument("src"); s.add_argument("out"); s.add_argument("--music", default="")
    s = sub.add_parser("settings"); s.add_argument("action", nargs="?", default="show", choices=["show", "set", "reset"])
    s.add_argument("pairs", nargs="*", help="key=value")
    s = sub.add_parser("new"); s.add_argument("project")
    sub.add_parser("doctor")
    s = sub.add_parser("check"); s.add_argument("project")
    a = ap.parse_args()
    {"looks": cmd_looks, "setup-project": cmd_setup_project, "stills": cmd_stills, "sample": cmd_sample,
     "render": cmd_render, "sync": cmd_sync, "finish": cmd_finish, "settings": cmd_settings, "new": cmd_new, "doctor": cmd_doctor, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
