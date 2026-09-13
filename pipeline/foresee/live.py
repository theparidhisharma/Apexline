"""FORESEE / live — pre-corner violation risk from vision alone.

The F-1 model scores telemetry laps; this module gives the same beat LIVE on
the video feed with zero telemetry: for every tracked car still inside the
line, fit a linear trend on its recent signed distance to the boundary and
project it a short horizon ahead. If the projection crosses the line, emit a
risk event BEFORE the wheels do.

risk = sigmoid(-(projected_sd) / SOFT_M)   gated on an approaching slope.

Deterministic, explainable, and honest about what it is: extrapolation of
measured geometry, not clairvoyance. Every event carries its slope and
projection so a steward can audit the claim. One event per approach
(hysteresis re-arms only after the car pulls clearly back inside or an
incident closes), so the pit wall isn't spammed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

HORIZON_S = 0.7        # how far ahead we project
SOFT_M = 0.22          # sigmoid softness on projected distance
ARM_MARGIN_M = 0.45    # must be at least this far inside to re-arm
MIN_RISK = 0.55        # emission threshold
WINDOW = 5             # samples in the trend fit


@dataclass
class _TrackPred:
    hist: list = field(default_factory=list)   # (t_s, sd_m)
    armed: bool = True
    cooldown_until_ms: int = 0


class LivePredictor:
    def __init__(self, horizon_s: float = HORIZON_S):
        self.h = horizon_s
        self.tracks: dict[int, _TrackPred] = {}

    def step(self, track_id: int, t_ms: int, sd_m: float) -> dict | None:
        tp = self.tracks.setdefault(track_id, _TrackPred())
        t_s = t_ms / 1000.0
        tp.hist.append((t_s, sd_m))
        if len(tp.hist) > WINDOW:
            tp.hist.pop(0)

        if sd_m > ARM_MARGIN_M and t_ms >= tp.cooldown_until_ms:
            tp.armed = True                      # safely inside again
        if sd_m <= 0.0:
            tp.armed = False                     # already outside — too late
            return None
        if not tp.armed or len(tp.hist) < WINDOW:
            return None

        # least-squares slope of sd over time (m/s toward the line if < 0)
        ts = [h[0] for h in tp.hist]
        ds = [h[1] for h in tp.hist]
        tm, dm = sum(ts) / WINDOW, sum(ds) / WINDOW
        denom = sum((t - tm) ** 2 for t in ts) or 1e-9
        slope = sum((t - tm) * (d - dm) for t, d in zip(ts, ds)) / denom
        if slope >= -0.05:
            return None                          # not approaching
        proj = sd_m + slope * self.h
        risk = 1.0 / (1.0 + math.exp(proj / SOFT_M))
        if risk < MIN_RISK:
            return None
        tp.armed = False                         # one call per approach
        tp.cooldown_until_ms = t_ms + 2500
        eta_s = sd_m / -slope if slope < 0 else self.h
        return {
            "track_id": track_id,
            "t_ms": t_ms,
            "risk": round(risk, 3),
            "eta_ms": int(min(eta_s, 3.0) * 1000),
            "slope_m_s": round(slope, 3),
            "sd_now_m": round(sd_m, 3),
            "kind": "pre_corner_prob",
            "model_version": "vision-trend-0.1",
        }

    def resolve(self, track_id: int):
        """Called when a violation window closes for this track."""
        tp = self.tracks.get(track_id)
        if tp:
            tp.armed = True
