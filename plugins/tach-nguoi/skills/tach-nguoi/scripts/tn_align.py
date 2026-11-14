"""Camera alignment for tach-nguoi: map every frame onto one reference frame using the background only.
MIT licence.

Clone effects stamp the person from one moment into later frames. On a tripod that just works; with a
handheld or drifting camera the stamps would slide, so each frame gets a 2x3 similarity transform
(frame -> reference) estimated from background features (people masked out).
"""
import cv2
import numpy as np

WORK_W = 960


def _prep(rgb, alpha_u8):
    h, w = rgb.shape[:2]
    s = WORK_W / w
    g = cv2.cvtColor(cv2.resize(rgb, (WORK_W, int(round(h * s))), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    a = cv2.resize(alpha_u8, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_AREA)
    mask = (cv2.dilate(a, np.ones((25, 25), np.uint8)) < 20).astype(np.uint8) * 255  # background only, with margin
    return g, mask, s


class Aligner:
    def __init__(self, ref_rgb, ref_alpha):
        self.orb = cv2.ORB_create(4000, fastThreshold=10)
        g, m, self.s = _prep(ref_rgb, ref_alpha)
        self.kp, self.des = self.orb.detectAndCompute(g, m)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.prev = np.float32([[1, 0, 0], [0, 1, 0]])

    def to_ref(self, rgb, alpha):
        """2x3 transform (full-resolution pixels) from this frame to the reference frame."""
        g, m, s = _prep(rgb, alpha)
        kp, des = self.orb.detectAndCompute(g, m)
        if des is None or self.des is None or len(kp) < 12:
            return self.prev.copy()
        ms = self.matcher.match(des, self.des)
        if len(ms) < 12:
            return self.prev.copy()
        src = np.float32([kp[x.queryIdx].pt for x in ms])
        dst = np.float32([self.kp[x.trainIdx].pt for x in ms])
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=3000)
        if M is None or inl is None or inl.sum() < 10:
            return self.prev.copy()
        M = M.astype(np.float32)
        M[:, 2] /= s  # work-resolution translation -> full resolution (scale/rotation are unchanged)
        self.prev = M
        return M


def smooth(transforms, k=5):
    """Average transforms over a small window: kills frame-to-frame jitter from feature noise."""
    T = np.stack(transforms)
    out = T.copy()
    for i in range(len(T)):
        lo, hi = max(0, i - k), min(len(T), i + k + 1)
        out[i] = T[lo:hi].mean(axis=0)
    return list(out)


def invert(M):
    return cv2.invertAffineTransform(M).astype(np.float32)


def compose(A, B):
    """A after B (both 2x3)."""
    A3 = np.vstack([A, [0, 0, 1]])
    B3 = np.vstack([B, [0, 0, 1]])
    return (A3 @ B3)[:2].astype(np.float32)


def drift_px(transforms):
    """How far the camera wanders over the window (pixels at full resolution): 0-1 = locked."""
    t = np.array([[M[0, 2], M[1, 2]] for M in transforms])
    sc = np.array([np.hypot(M[0, 0], M[1, 0]) for M in transforms])
    return float(np.ptp(t, axis=0).max()), float(np.ptp(sc))
