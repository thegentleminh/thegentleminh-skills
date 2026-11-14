"""Sound effects made from scratch (no samples, so no licences): whoosh, hit, shutter, flash. MIT licence.

All return mono float32 arrays at SR, peak about -6 dBFS.
"""
import numpy as np

SR = 48000
_rng = np.random.default_rng(7)  # fixed seed: the same sound every render


def _norm(x, peak=0.5):
    m = np.abs(x).max()
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


def _onepole(x, cutoff_hz):
    """Low-pass with a cutoff that can change per sample (array) or stay fixed (number)."""
    c = np.broadcast_to(np.asarray(cutoff_hz, np.float64), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(dur=0.45):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = _rng.standard_normal(n)
    sweep = 300 + 5200 * np.sin(np.pi * t) ** 2          # brightens in the middle, like air rushing past
    lp = _onepole(noise, sweep)
    band = lp - _onepole(lp, 180)                          # drop the rumble
    env = np.sin(np.pi * np.clip(t * 1.15, 0, 1)) ** 1.5
    return _norm(band * env, 0.45)


def hit(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 45 + 95 * np.exp(-t * 18)                          # pitch drops: a punchy low thump
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    click = _rng.standard_normal(n) * np.exp(-t * 400) * 0.6
    return _norm(body + click, 0.55)


def shutter(dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for start, gain in ((0.0, 1.0), (0.075, 0.7)):        # mirror up, shutter closes
        s = int(start * SR)
        k = n - s
        burst = _rng.standard_normal(k) * np.exp(-np.arange(k) / SR * 260) * gain
        out[s:] += np.diff(burst, prepend=0)               # high-passed: a crisp click
    return _norm(out, 0.5)


def flash(dur=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tss = np.diff(_rng.standard_normal(n), prepend=0) * np.exp(-t * 14)
    return _norm(tss, 0.25)


SOUNDS = {"whoosh": whoosh, "hit": hit, "shutter": shutter, "flash": flash}


def mix_into(track, sound, at_s, gain=1.0):
    """Add a mono sound into a (n, 2) float track at at_s seconds."""
    s = int(round(at_s * SR))
    if s >= len(track):
        return
    e = min(len(track), s + len(sound))
    track[s:e] += sound[:e - s, None] * gain
