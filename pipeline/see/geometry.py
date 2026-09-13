"""SEE / geometry — (s,d) curvilinear transform and zone gating.

Frenet-style coordinates (distance-along-track s, lateral offset d) are the
standard representation in the autonomous-racing literature (Werling et al.
2010). Detailed geometry runs only while a tracked car is inside the zone
polygon; a rolling +-3 s frame buffer produces evidence after the car has gone.
"""
from __future__ import annotations

import numpy as np


class TrackFrame:
    def __init__(self, centerline_world: np.ndarray):
        self.pts = np.asarray(centerline_world, float)
        seg = np.diff(self.pts, axis=0)
        self.seg_len = np.linalg.norm(seg, axis=1)
        self.s_cum = np.concatenate([[0.0], np.cumsum(self.seg_len)])
        self.tangents = seg / np.maximum(self.seg_len[:, None], 1e-9)

    def to_sd(self, xy) -> tuple[float, float]:
        xy = np.asarray(xy, float)
        d2 = np.linalg.norm(self.pts[:-1] - xy, axis=1)
        i = int(np.argmin(d2))
        rel = xy - self.pts[i]
        t = self.tangents[i]
        s = self.s_cum[i] + float(np.clip(np.dot(rel, t), 0.0, self.seg_len[i]))
        n = np.array([-t[1], t[0]])
        return s, float(np.dot(rel, n))
