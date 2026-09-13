"""FORESEE / predict — live replay scorer + F-2 strike-risk forecast.

Every prediction is stamped with model_version (auditability). F-2 is a
robust per-(driver,corner) linear trend on max-margin-per-lap: projected
margin <= 0 within horizon h laps -> attention alert.
"""
from __future__ import annotations

import numpy as np
import joblib


class F1Scorer:
    def __init__(self, model_path: str = "data/labels/foresee_f1.joblib"):
        bundle = joblib.load(model_path)
        self.model, self.version, self.features = bundle["model"], bundle["version"], bundle["features"]

    def score(self, feat_row: dict) -> dict:
        x = np.array([[feat_row.get(f, 0.0) or 0.0 for f in self.features]])
        p = float(self.model.predict_proba(x)[0, 1])
        return {"kind": "pre_corner_prob", "value": round(p, 3),
                "model_version": self.version, "features": feat_row}


def strike_risk(margins_per_lap: list[float], horizon: int = 3) -> dict:
    """Fit slope over recent laps; alert if projected margin <= 0 within horizon."""
    m = np.asarray([v for v in margins_per_lap if v is not None], float)
    if len(m) < 4:
        return {"kind": "strike_risk", "value": 0.0, "alert": False, "model_version": "f2-lin-0.1"}
    x = np.arange(len(m))
    slope, intercept = np.polyfit(x[-6:], m[-6:], 1)
    projected = intercept + slope * (len(m) - 1 + horizon)
    risk = float(np.clip(1.0 - projected / max(m.mean(), 1e-6), 0.0, 1.0)) if slope < 0 else 0.0
    return {"kind": "strike_risk", "value": round(risk, 3),
            "alert": bool(projected <= 0 and slope < 0),
            "projected_margin_m": round(float(projected), 3),
            "model_version": "f2-lin-0.1"}
