"""SEE / footprint — ground-contact point estimation per car.

v0: bottom edge of the bbox (corners + midpoint) as contact proxies.
v1: lowest-contour points of the seg mask (truer on angled cars).
Known, stated limitation: true wheel-contact estimation from one oblique
view has irreducible error — that is WHY the marginal band routes to humans.
"""
from __future__ import annotations

import numpy as np


def footprint_points_px(det) -> np.ndarray:
    """Return (N,2) image-space candidate ground-contact points."""
    if det.mask is not None and len(det.mask) >= 3:
        pts = det.mask
        ymax = pts[:, 1].max()
        low = pts[pts[:, 1] >= ymax - 6.0]          # lowest ~6px band of the contour
        if len(low) >= 2:
            return low
    x1, y1, x2, y2 = det.xyxy
    return np.array([[x1, y2], [(x1 + x2) / 2.0, y2], [x2, y2]])


def innermost_signed_distance(points_world: np.ndarray, boundary: np.ndarray) -> float:
    """Signed distance of the MOST-INSIDE contact point to the boundary polyline.

    Convention: positive = inside the track, negative = beyond the boundary.
    Conservative by construction: if 1% of tyre is on the line, the innermost
    point is inside -> legal. The system structurally cannot false-flag the
    'tyre on the line' case.
    """
    from shapely.geometry import LineString, Point
    line = LineString(boundary)
    # Track side sign: use the polyline's left normal as 'inside' (calibration
    # wizard orders the polyline so the racing surface is on its left).
    best = -1e9
    for p in points_world:
        pt = Point(p)
        d = pt.distance(line)
        seg_i = int(np.argmin([Point(b).distance(pt) for b in boundary]))
        a = boundary[max(seg_i - 1, 0)]
        b = boundary[min(seg_i + 1, len(boundary) - 1)]
        t = np.array(b) - np.array(a)
        n = np.array([-t[1], t[0]])  # left normal
        sign = 1.0 if np.dot(np.array(p) - np.array(a), n) >= 0 else -1.0
        best = max(best, sign * d)
    return float(best)


def per_wheel_distances(points_world: np.ndarray, boundary: np.ndarray) -> list[float]:
    """Signed distance for every contact point — feeds the per-wheel timeline
    on the incident card ('FR out at t1, all four out t2-t3')."""
    out = []
    for p in points_world:
        out.append(innermost_signed_distance(np.asarray([p]), boundary))
    return out
