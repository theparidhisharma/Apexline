"""KNOW / identity — vision track-ID <-> car-number binding.

Demo path: position correlation against telemetry `location` streams
(nearest-trajectory matching over the zone window). Production path: the
transponder timing feed every timed event already runs.
"""
from __future__ import annotations

import numpy as np


def bind_by_position(track_world_xy: np.ndarray, telemetry_by_car: dict[str, np.ndarray]) -> tuple[str | None, float]:
    """Return (car_number, mean-distance score). Lower score = better bind.
    Caller should treat score > ~5 m as unbound (label the incident 'car ?')."""
    best, best_d = None, float("inf")
    for car, traj in telemetry_by_car.items():
        n = min(len(track_world_xy), len(traj))
        if n < 3:
            continue
        d = float(np.mean(np.linalg.norm(track_world_xy[:n] - traj[:n], axis=1)))
        if d < best_d:
            best, best_d = car, d
    return best, best_d
