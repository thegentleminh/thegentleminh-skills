"""Clone effects for tach-nguoi. MIT licence.

trail: one take. As the person moves, a copy of them is left behind every `every` seconds and stays,
       so the path fills with clones (分身定格 / "phân thân"). Only the person who moves is copied.
two:   two takes of the same shot (one person playing two roles). The person from take B is cut out and
       laid over take A ("overlay"), or the frame is split along the emptiest column ("split").
Both align every frame to the background first, so a drifting camera doesn't make the copies slide.
"""
import cv2
import numpy as np

import tn_align
import tn_io

STYLES = ("solid", "fade", "ghost")


def components(alpha_u8, min_area):
    n, lab, st, cen = cv2.connectedComponentsWithStats((alpha_u8 > 128).astype(np.uint8))
    return lab, [(k, cen[k], st[k]) for k in range(1, n) if st[k][4] >= min_area]


def moving_mask(a_now, a_later, W):
    """Soft mask of the person who moved between two frames (None if nobody did)."""
    min_area = a_now.size * 0.004
    lab, now = components(a_now, min_area)
    _, later = components(a_later, min_area)
    if not now or not later:
        return None, 0.0
    best, dist = None, 0.0
    for k, c, st in now:
        d = min(np.hypot(*(c - c2)) for _, c2, _ in later)
        if d > dist:
            best, dist = k, d
    if best is None or dist < W * 0.012:  # nothing really moved
        return None, dist
    m = (lab == best).astype(np.uint8)
    m = cv2.dilate(m, np.ones((9, 9), np.uint8))  # keep the soft hair edge just outside the hard blob
    return (a_now.astype(np.float32) / 255) * m, dist


def crop_box(mask, pad):
    ys, xs = np.nonzero(mask > 0.02)
    H, W = mask.shape
    return max(0, xs.min() - pad), max(0, ys.min() - pad), min(W, xs.max() + pad + 1), min(H, ys.max() + pad + 1)


def warp_crop(rgb, a, x0, y0, M, W, H):
    """Warp a crop (taken at x0,y0 in its own frame) by M into another frame. Returns crop, alpha, X0, Y0."""
    h, w = a.shape
    corners = np.float32([[x0, y0], [x0 + w, y0], [x0, y0 + h], [x0 + w, y0 + h]])
    pts = corners @ M[:, :2].T + M[:, 2]
    X0, Y0 = max(0, int(pts[:, 0].min()) - 1), max(0, int(pts[:, 1].min()) - 1)
    X1, Y1 = min(W, int(pts[:, 0].max()) + 2), min(H, int(pts[:, 1].max()) + 2)
    if X1 <= X0 or Y1 <= Y0:
        return None
    # crop pixel -> its frame (+x0,y0) -> M -> target, minus the target crop origin
    Mc = M.copy()
    Mc[:, 2] = M[:, 2] + M[:, :2] @ np.float32([x0, y0]) - np.float32([X0, Y0])
    size = (X1 - X0, Y1 - Y0)
    return (cv2.warpAffine(rgb, Mc, size, flags=cv2.INTER_LINEAR),
            cv2.warpAffine(a, Mc, size, flags=cv2.INTER_LINEAR), X0, Y0)


def ease_out_cubic(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


class Trail:
    """Plan and draw a clone trail over [start, end]; copies fade out over `fade` seconds after end."""

    def __init__(self, clip, matte, item, size, fps):
        self.item, self.fps = item, fps
        self.W, self.H = size
        self.start, self.end = float(item["start"]), float(item["end"])
        self.fade = float(item.get("fade", 0.4))
        self.every = float(item.get("every", 0.6))
        self.style = item.get("style", "fade")
        n = int(round((self.end + self.fade - self.start) * fps)) + 1
        look = int(round(0.4 * fps))  # compare with 0.4 s later to see who moves
        # pass 1, streamed at alignment size: camera transforms + small mattes (no full frames kept in memory)
        aw = min(self.W, tn_align.WORK_W)
        ah = int(round(self.H * aw / self.W))
        rf = tn_io.Reader(clip, size=(aw, ah), start=self.start or None, frames=n + look)
        ra = tn_io.Reader(matte, size=(aw, ah), gray=True, start=self.start or None, frames=n + look)
        al, T, small = None, [], []
        for fr, a in zip(rf, ra):
            if al is None:
                al = tn_align.Aligner(fr, a)
            T.append(al.to_ref(fr, a))
            small.append(a)
        k = self.W / aw  # alignment ran at aw wide: translations to output pixels
        T = [np.float32([[M[0, 0], M[0, 1], M[0, 2] * k], [M[1, 0], M[1, 1], M[1, 2] * k]]) for M in tn_align.smooth(T)]
        n = min(n, len(small) - look)
        self.T, self.n = T, n
        self.drift = tn_align.drift_px(T)
        # pass 2: full-size frames only at the stamp moments
        self.stamps = []  # (time, rgb crop, alpha crop, x0, y0, T at stamp)
        step = max(1, int(round(self.every * fps)))
        for i in range(0, int(round((self.end - self.start) * fps)) + 1, step):
            if i >= n:
                break
            m_small, _ = moving_mask(small[i], small[i + look], aw)
            if m_small is None:
                continue
            t = self.start + i / fps
            fr = next(iter(tn_io.Reader(clip, size=size, start=t, frames=1)))
            a = next(iter(tn_io.Reader(matte, size=size, gray=True, start=t, frames=1)))
            # the same blob at full size: the component that overlaps the small moving mask the most
            lab, comps = components(a, a.size * 0.004)
            hint = cv2.resize(m_small, (self.W, self.H), interpolation=cv2.INTER_LINEAR) > 0.3
            if not comps:
                continue
            best = max(comps, key=lambda c: int((hint & (lab == c[0])).sum()))[0]
            m = (a.astype(np.float32) / 255) * cv2.dilate((lab == best).astype(np.uint8), np.ones((9, 9), np.uint8))
            x0, y0, x1, y1 = crop_box(m, 4)
            self.stamps.append((t, fr[y0:y1, x0:x1].astype(np.float32) / 255, m[y0:y1, x0:x1].copy(), x0, y0, T[i]))

    def active(self, t):
        return self.start <= t <= self.end + self.fade

    def render(self, frame, alpha_u8, t):
        """Draw the copies made before t into this frame (behind everyone live)."""
        i = int(round((t - self.start) * self.fps))
        if i < 0 or i >= self.n:
            return frame
        Tc_inv = tn_align.invert(self.T[i])
        out = frame.astype(np.float32) / 255
        live = alpha_u8.astype(np.float32)[..., None] / 255
        older = [s for s in self.stamps if s[0] <= t - 1.0 / self.fps]  # the live person isn't copied onto itself
        k_end = 1.0 if t <= self.end else max(0.0, 1 - (t - self.end) / self.fade)
        for rank, (ts, rgb, a, x0, y0, Ts) in enumerate(older):
            M = tn_align.compose(Tc_inv, Ts)  # stamp frame -> reference -> this frame
            w = warp_crop(rgb, a, x0, y0, M, self.W, self.H)
            if w is None:
                continue
            crgb, ca, X0, Y0 = w
            if self.style == "fade":
                op = 0.35 + 0.65 * (rank + 1) / max(1, len(older))
            elif self.style == "ghost":
                op = 0.55
                g = crgb.mean(axis=2, keepdims=True)
                crgb = g * 0.5 + crgb * 0.5
            else:
                op = 1.0
            age = t - ts
            pop = max(0.0, 1 - age / 0.15) * 0.35  # brief bright flash as each copy appears
            crgb = np.clip(crgb + pop, 0, 1)
            aa = (ca * op * k_end)[..., None]
            h, w_ = aa.shape[:2]
            reg = out[Y0:Y0 + h, X0:X0 + w_]
            reg[:] = reg * (1 - aa) + crgb * aa
        # everyone live (the walker and anyone else) stays in front of their copies
        out = out * (1 - live) + (frame.astype(np.float32) / 255) * live
        return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)

    def stamp_times(self):
        return [s[0] for s in self.stamps]


class Two:
    """Take B's person over take A (overlay) or A|B split at the emptiest column (split)."""

    def __init__(self, clip_a, matte_a, clip_b, matte_b, item, size, fps):
        self.item, self.fps = item, fps
        self.W, self.H = size
        self.start, self.end = float(item.get("start", 0)), float(item["end"])
        self.mode = item.get("mode", "overlay")
        self.b_start = float(item.get("b_start", 0))
        self.clip_b, self.matte_b = clip_b, matte_b
        n = int(round((self.end - self.start) * fps))
        # pass 1, streamed at alignment size: B -> A transform per frame, through A's first frame
        aw = min(self.W, tn_align.WORK_W)
        ah = int(round(self.H * aw / self.W))
        readers = [tn_io.Reader(c, size=(aw, ah), gray=g, start=s or None, frames=n) for c, g, s in
                   ((clip_a, False, self.start), (matte_a, True, self.start), (clip_b, False, self.b_start), (matte_b, True, self.b_start))]
        al, Ta, Tb, occ_a, occ_b = None, [], [], 0, 0
        for fa, aa, fb, ab in zip(*readers):
            if al is None:
                al = tn_align.Aligner(fa, aa)
            Ta.append(al.to_ref(fa, aa))
            Tb.append(al.to_ref(fb, ab))
            occ_a = occ_a + aa.astype(np.float32)
            occ_b = occ_b + ab.astype(np.float32)
        self.n = len(Ta)
        k = self.W / aw
        fix = lambda M: np.float32([[M[0, 0], M[0, 1], M[0, 2] * k], [M[1, 0], M[1, 1], M[1, 2] * k]])
        Ta, Tb = [fix(M) for M in tn_align.smooth(Ta)], [fix(M) for M in tn_align.smooth(Tb)]
        self.M = [tn_align.compose(tn_align.invert(Ta[i]), Tb[i]) for i in range(self.n)]
        if self.mode == "split":  # seam where neither take has a person, on average
            col = (occ_a + occ_b).mean(axis=0)
            lo, hi = int(aw * 0.2), int(aw * 0.8)
            seam_small = lo + int(np.argmin(col[lo:hi]))
            self.seam = seam_small * k
            self.b_side = "right" if occ_b[:, seam_small:].mean() > occ_b[:, :seam_small].mean() else "left"
        self._rb = None
        self._next = 0

    def _b(self, i):
        """B frame + matte i at output size: streamed when frames come in order, else read on their own."""
        if self._rb is None or i != self._next:
            for r in getattr(self, "_readers", []):
                r.close()
            t = self.b_start + i / self.fps
            self._readers = [tn_io.Reader(self.clip_b, size=(self.W, self.H), start=t or None, frames=self.n - i),
                             tn_io.Reader(self.matte_b, size=(self.W, self.H), gray=True, start=t or None, frames=self.n - i)]
            self._rb = zip(*self._readers)
        self._next = i + 1
        return next(self._rb)

    def active(self, t):
        return self.start <= t < self.start + self.n / self.fps

    def render(self, frame, alpha_u8, t):
        i = int(round((t - self.start) * self.fps))
        if i < 0 or i >= self.n:
            return frame
        fb_raw, ab_raw = self._b(i)
        b = cv2.warpAffine(fb_raw, self.M[i], (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        fa = frame.astype(np.float32) / 255
        fb = b.astype(np.float32) / 255
        if self.mode == "split":
            x = np.arange(self.W, dtype=np.float32)
            feather = self.W * 0.03
            w = np.clip((x - self.seam) / feather + 0.5, 0, 1)
            if self.b_side == "left":
                w = 1 - w
            out = fa * (1 - w[None, :, None]) + fb * w[None, :, None]
        else:
            ab = cv2.warpAffine(ab_raw, self.M[i], (self.W, self.H), flags=cv2.INTER_LINEAR).astype(np.float32)[..., None] / 255
            out = fa * (1 - ab) + fb * ab
            if self.item.get("front", "b") == "a":  # A's person stays in front where they overlap
                aa = alpha_u8.astype(np.float32)[..., None] / 255
                out = out * (1 - aa) + fa * aa
        return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
