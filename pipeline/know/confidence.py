"""KNOW / confidence — transparent scored formula, printed in the UI.

conf = w1*sigmoid(overshoot/band) + w2*track_stability
     + w3*(1-occlusion_ratio) + w4*calib_quality + w5*cross_modal_agreement

Bands: < 0.35 auto-clear · 0.35-0.75 needs-review · > 0.75 auto-flag.
Weights are fixed constants, not learned — every score is inspectable.
"""
from __future__ import annotations

import json
import math
import os

WEIGHTS = {"overshoot": 0.35, "stability": 0.20, "occlusion": 0.15,
           "calibration": 0.15, "cross_modal": 0.15}
BANDS = {"auto_clear": 0.35, "auto_flag": 0.75}
_LEARNED = "data/learned/thresholds.json"
_cache = {"mtime": None, "bands": dict(BANDS)}


def current_bands() -> dict:
    """Defaults, overridden by the self-improvement loop's recalibrated
    thresholds when data/learned/thresholds.json exists (mtime-cached)."""
    try:
        m = os.path.getmtime(_LEARNED)
        if _cache["mtime"] != m:
            _cache["bands"] = {**BANDS, **json.load(open(_LEARNED)).get("bands", {})}
            _cache["mtime"] = m
        return _cache["bands"]
    except (OSError, ValueError):
        return BANDS


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score(overshoot_m: float, error_band_m: float, track_stability: float,
          occlusion_ratio: float, calib_residual_px: float,
          cross_modal: float = 0.5) -> float:
    ratio = overshoot_m / max(error_band_m, 0.01)
    parts = {
        "overshoot": sigmoid(ratio - 2.0),            # >2 error-bands out -> confident
        "stability": max(0.0, min(track_stability, 1.0)),
        "occlusion": 1.0 - max(0.0, min(occlusion_ratio, 1.0)),
        "calibration": max(0.0, 1.0 - calib_residual_px / 6.0),
        "cross_modal": cross_modal,
    }
    return round(sum(WEIGHTS[k] * v for k, v in parts.items()), 3)


def band(conf: float, occlusion_ratio: float = 0.0, context_tags: list | None = None) -> str:
    if occlusion_ratio > 0.3 or (context_tags and len(context_tags) > 0):
        return "needs_review"  # occluded/context incidents can never auto-flag
    b = current_bands()
    if conf > b["auto_flag"]:
        return "auto_flag"
    if conf < b["auto_clear"]:
        return "auto_clear"
    return "needs_review"
