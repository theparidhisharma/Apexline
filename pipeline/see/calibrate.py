"""SEE / calibrate — homography from clicked points, residuals, error bands.

The 5-minute installation. Operator clicks >=4 ground reference points with
known world spacing (cone grid, kerb corners) or uses unknown-scale mode
(relative units, distances reported in 'track widths').
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from ..physics import pixel_error_band_m


class DegeneratePointsError(ValueError):
    pass


def fit_homography(image_points: list[list[float]], world_points: list[list[float]]):
    """Returns (H 3x3 image->world, mean reprojection residual in px)."""
    ip = np.asarray(image_points, dtype=np.float64)
    wp = np.asarray(world_points, dtype=np.float64)
    if len(ip) < 4 or len(wp) != len(ip):
        raise DegeneratePointsError("need >=4 matched points")
    if np.linalg.matrix_rank(np.c_[ip, np.ones(len(ip))]) < 3:
        raise DegeneratePointsError("points are collinear")
    H, _ = cv2.findHomography(ip, wp, method=0)
    if H is None:
        raise DegeneratePointsError("homography fit failed")
    # residual: world points -> back to image via H^-1, px error
    Hinv = np.linalg.inv(H)
    proj = cv2.perspectiveTransform(wp.reshape(-1, 1, 2), Hinv).reshape(-1, 2)
    residual_px = float(np.mean(np.linalg.norm(proj - ip, axis=1)))
    return H, residual_px


def to_world(H: np.ndarray, pts_px: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(np.asarray(pts_px, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


class CornerCalibration:
    """Persisted per-corner: H, boundary polyline (world), reference choice."""

    def __init__(self, H, boundary_world, residual_px,
                 boundary_reference="white_line", zone_polygon_px=None):
        self.H = np.asarray(H, float)
        self.H_img_from_world = np.linalg.inv(self.H)
        self.boundary_world = np.asarray(boundary_world, float)
        self.residual_px = float(residual_px)
        # Race directors declare the operative limit per corner:
        # white_line | kerb_edge | custom. A dropdown, not an exemption polygon.
        self.boundary_reference = boundary_reference
        self.zone_polygon_px = np.asarray(zone_polygon_px, float) if zone_polygon_px is not None else None

    def error_band_m(self, u: float, v: float) -> float:
        """Distance-dependent ±band at an image point (see physics.pixel_error_band_m)."""
        return pixel_error_band_m(self.H, u, v)  # H maps image->world; ±1px spread in metres

    def in_zone(self, u: float, v: float) -> bool:
        if self.zone_polygon_px is None:
            return True
        return cv2.pointPolygonTest(self.zone_polygon_px.astype(np.float32), (u, v), False) >= 0

    def save(self, path: str | Path):
        Path(path).write_text(json.dumps({
            "H": self.H.tolist(),
            "boundary_world": self.boundary_world.tolist(),
            "residual_px": self.residual_px,
            "boundary_reference": self.boundary_reference,
            "zone_polygon_px": self.zone_polygon_px.tolist() if self.zone_polygon_px is not None else None,
        }, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "CornerCalibration":
        d = json.loads(Path(path).read_text())
        return cls(d["H"], d["boundary_world"], d["residual_px"],
                   d.get("boundary_reference", "white_line"), d.get("zone_polygon_px"))
