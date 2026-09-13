"""KNOW / advantage — 'gained 0.21 s' quantification (the V5 heuristic).

Empirical: corner-segment time vs the driver's own compliant-lap median.
Optional QSS counterfactual cross-check (physics.qss_corner_time): agreement
raises confidence; disagreement routes to human. Neither is ground truth.
Steward working heuristic for 'lasting advantage' is ~0.2-0.3 s.
"""
from __future__ import annotations

import statistics

ADVANTAGE_HEURISTIC_S = (0.2, 0.3)


def advantage_gained_s(segment_time_s: float, compliant_times_s: list[float]) -> float | None:
    clean = [t for t in compliant_times_s if t > 0]
    if len(clean) < 3:
        return None
    return round(statistics.median(clean) - segment_time_s, 3)


def advantage_flags(adv: float | None) -> list[str]:
    if adv is None:
        return ["advantage-unknown"]
    lo, _hi = ADVANTAGE_HEURISTIC_S
    return ["lasting-advantage"] if adv >= lo else []
