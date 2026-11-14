"""Voice for a video-giai-thich script: make it (ElevenLabs) or time your own recording (Whisper).

python vgt_voice.py tts   SCRIPT --voice VOICE_ID --out voice/ [--model eleven_v4] [--tag "[calm]"]
python vgt_voice.py align SCRIPT RECORDING --out voice/ [--whisper small]

Both write voice/voice.wav (mono, levelled to -14 LUFS with a two-pass measurement) and
voice/voice.json (the time of every spoken word), which `vgt.py sync` uses to time scenes and text.
The ElevenLabs key comes from the ELEVENLABS_API_KEY environment variable and is never printed.
"""
import argparse, base64, difflib, json, os, re, subprocess, sys, unicodedata, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vgt_script

API = "https://api.elevenlabs.io/v1"


def norm(w):
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[^\w]", "", w)


# ---------- loudness ----------
def level(src, dst, target=-14.0):
    """Two-pass loudnorm to `target` LUFS, mono 48 kHz (one linear gain, no pumping)."""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-ac", "1", "-af",
                        f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    js = json.loads(m.stderr[m.stderr.rindex("{"):m.stderr.rindex("}") + 1])
    f = (f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
         f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-af", f, "-ar", "48000", str(dst)], check=True)
    return float(js["input_i"])


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


# ---------- ElevenLabs ----------
def eleven_key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not k:
        sys.exit("Set ELEVENLABS_API_KEY first (ElevenLabs > Developers > API keys). Or record the script yourself and use `align`.")
    return k


def eleven_tts(text, voice, model, stability=0.5, speed=1.0, timestamps=True):
    body = {"text": text, "model_id": model,
            "voice_settings": {"stability": stability, "similarity_boost": 0.8, "style": 0.0, "speed": speed}}
    ep = "/with-timestamps" if timestamps else ""
    req = urllib.request.Request(f"{API}/text-to-speech/{voice}{ep}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": eleven_key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs said {e.code}: {e.read().decode(errors='replace')[:500]}")
    return json.loads(raw) if timestamps else raw


def cmd_audition(a):
    """'Show all for comparison' for voices: the same line in each voice, joined with a pause (costs credits)."""
    voices = [v.strip() for v in a.voices.split(",") if v.strip()]
    print(f"{len(voices)} voices x {len(a.line)} characters = about {len(voices) * len(a.line)} credits", flush=True)
    out = Path(a.out); tmp = out.with_suffix(""); tmp.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, v in enumerate(voices, 1):
        f = tmp / f"{i}-{v}.mp3"
        f.write_bytes(eleven_tts(a.line, v, a.model, timestamps=False))
        parts.append(f)
        print(f"  {i}: {v}")
    inputs, chain = [], ""
    for i, f in enumerate(parts):
        inputs += ["-i", str(f)]
        chain += f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,apad=pad_dur=0.8[a{i}];"
    chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", chain, "-map", "[o]",
                    "-c:a", "aac", "-b:a", "128k", str(out)], check=True)
    print("wrote", out, "(voices in the order listed above)")


def cmd_tts(a):
    beats = vgt_script.parse(open(a.script, encoding="utf-8").read())
    spoken = vgt_script.spoken_text(beats)
    text = (a.tag.strip() + " " if a.tag else "") + spoken
    print(f"ElevenLabs: {len(text)} characters with {a.model} (about {len(text)} credits on v4-class models)...", flush=True)
    data = eleven_tts(text, a.voice, a.model, a.stability, a.speed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    raw = out / "voice-raw.mp3"
    raw.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment")
    (out / "eleven-alignment.json").write_text(json.dumps(al, ensure_ascii=False), encoding="utf-8")
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    joined = "".join(chars)
    words, pos = [], (len(a.tag.strip()) + 1 if a.tag else 0)
    for w in vgt_script.spoken_words(beats):
        i = joined.find(w, pos)
        if i < 0:  # the service changed the text (rare): fall back to Whisper timing
            sys.exit("Could not match the voice's timing to the script; run `align` on voice-raw.mp3 instead.")
        words.append({"say": w, "s": round(st[i], 3), "e": round(en[i + len(w) - 1], 3)})
        pos = i + len(w)
    finish(out, raw, words, beats)


# ---------- own recording ----------
def _cuda_dlls():
    """On Windows, pip's nvidia-cublas/cudnn packages keep their DLLs in site-packages/nvidia/*/bin."""
    if os.name != "nt":
        return
    import site
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        for b in Path(sp).glob("nvidia/*/bin"):
            os.add_dll_directory(str(b))
            os.environ["PATH"] = str(b) + os.pathsep + os.environ["PATH"]


def transcribe(audio, size, prompt):
    """Word timings from faster-whisper: GPU if it works, otherwise CPU (slower, same result)."""
    from faster_whisper import WhisperModel
    _cuda_dlls()
    for device, ctype in (("cuda", "float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(size, device=device, compute_type=ctype)
            segs, _ = model.transcribe(str(audio), language="vi", word_timestamps=True, vad_filter=True,
                                       initial_prompt=prompt)
            return [(w.word.strip(), w.start, w.end) for s in segs for w in s.words if norm(w.word)]
        except Exception as e:  # missing CUDA libraries show up only when decoding starts
            if device == "cpu":
                raise
            print(f"GPU Whisper unavailable ({str(e)[:80]}); using the CPU.", flush=True)


def cmd_align(a):
    from faster_whisper import WhisperModel
    beats = vgt_script.parse(open(a.script, encoding="utf-8").read())
    script = vgt_script.spoken_words(beats)
    heard = transcribe(a.recording, a.whisper, " ".join(script)[:400])
    sm = difflib.SequenceMatcher(a=[norm(w) for w in script], b=[norm(h[0]) for h in heard], autojunk=False)
    times = [None] * len(script)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            times[blk.a + k] = (h[1], h[2])
    matched = sum(t is not None for t in times)
    # fill gaps by spreading the missing words evenly between their matched neighbours
    i = 0
    while i < len(times):
        if times[i] is None:
            j = i
            while j < len(times) and times[j] is None:
                j += 1
            t0 = times[i - 1][1] if i > 0 else 0.0
            t1 = times[j][0] if j < len(times) else (heard[-1][2] if heard else t0 + 0.4 * (j - i))
            step = max(t1 - t0, 0.01) / (j - i)
            for k in range(i, j):
                times[k] = (t0 + step * (k - i), t0 + step * (k - i + 1))
            i = j
        i += 1
    print(f"Whisper matched {matched}/{len(script)} script words ({100 * matched / len(script):.0f} %).")
    if matched / len(script) < 0.8:
        print("Warning: under 80 % matched. Is it the same script? Check the timings in the stills.")
    words = [{"say": w, "s": round(t[0], 3), "e": round(t[1], 3)} for w, t in zip(script, times)]
    finish(Path(a.out), Path(a.recording), words, beats)


def cmd_silent(a):
    """No voice: time each sentence for reading (about 0.3 s a word, at least 2.2 s on screen)."""
    beats = vgt_script.parse(open(a.script, encoding="utf-8").read())
    words, t = [], 0.4
    for b in beats:
        for c in b["cues"]:
            ws = [w for tok in c["tokens"] for w in tok["say"].split()]
            hold = max(2.2, 0.9 + a.per_word * len(ws))
            step = min(0.24, (hold - 0.9) / max(1, len(ws)))
            for i, w in enumerate(ws):
                words.append({"say": w, "s": round(t + i * step, 3), "e": round(t + (i + 1) * step, 3)})
            t += hold + 0.25
        t += 0.35  # a breath between scenes
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "voice.json").write_text(json.dumps({"duration": round(t, 3), "audio": False, "words": words},
                                               ensure_ascii=False, indent=0), encoding="utf-8")
    if (out / "voice.wav").exists():
        (out / "voice.wav").unlink()
    print(f"no voice: {len(words)} words timed for reading, {t:.1f} s -> {out / 'voice.json'}")


def finish(out, src, words, beats):
    out.mkdir(parents=True, exist_ok=True)
    before = level(src, out / "voice.wav")
    d = duration(out / "voice.wav")
    (out / "voice.json").write_text(json.dumps({"duration": round(d, 3), "audio": True, "words": words}, ensure_ascii=False, indent=0),
                                    encoding="utf-8")
    print(f"voice.wav: {d:.1f} s, levelled from {before:.1f} to -14 LUFS (mono). {len(words)} words timed -> {out / 'voice.json'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("tts"); s.add_argument("script"); s.add_argument("--voice", required=True)
    s.add_argument("--model", default="eleven_v4"); s.add_argument("--tag", default="")
    s.add_argument("--stability", type=float, default=0.5); s.add_argument("--speed", type=float, default=1.0)
    s.add_argument("--out", required=True)
    s = sub.add_parser("align"); s.add_argument("script"); s.add_argument("recording")
    s.add_argument("--whisper", default="small"); s.add_argument("--out", required=True)
    s = sub.add_parser("silent"); s.add_argument("script"); s.add_argument("--out", required=True)
    s.add_argument("--per-word", type=float, default=0.3)
    s = sub.add_parser("audition"); s.add_argument("--voices", required=True, help="comma-separated voice ids")
    s.add_argument("--line", required=True); s.add_argument("--model", default="eleven_v4"); s.add_argument("--out", required=True)
    a = ap.parse_args()
    {"tts": cmd_tts, "align": cmd_align, "silent": cmd_silent, "audition": cmd_audition}[a.cmd](a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
