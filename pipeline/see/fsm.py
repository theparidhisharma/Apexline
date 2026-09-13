"""SEE / fsm — hysteresis violation state machine + plausibility filtering.

INSIDE --(footprint fully beyond boundary, k consecutive samples)--> VIOLATING
VIOLATING --(back inside, m samples)--> INSIDE  => emit incident (peak overshoot)

Hysteresis kills flicker false-positives; the 7g filter kills tracker teleports.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..physics import A_PLAUSIBLE_MAX, is_plausible_step, is_plausible_step_t


@dataclass
class IncidentCandidate:
    track_id: int
    t_start_ms: int
    t_end_ms: int
    max_overshoot_m: float
    duration_ms: int
    n_frames_outside: int
    error_band_m: float
    occlusion_ratio: float = 0.0


@dataclass
class _CarState:
    state: str = "INSIDE"
    out_streak: int = 0
    in_streak: int = 0
    t_start_ms: int = 0
    t_last_ms: int = 0
    peak: float = 0.0
    frames_out: int = 0
    band: float = 0.0
    history: list = field(default_factory=list)  # recent world positions for 7g check


class ViolationFSM:
    def __init__(self, k_out: int = 3, m_in: int = 2, dt_s: float = 0.1):
        self.k_out, self.m_in, self.dt = k_out, m_in, dt_s
        self.cars: dict[int, _CarState] = {}

    def step(self, track_id: int, t_ms: int, signed_dist_m: float,
             world_xy, error_band_m: float) -> IncidentCandidate | None:
        c = self.cars.setdefault(track_id, _CarState())
        c.t_last_ms = t_ms

        # Plausibility gate: drop physically impossible jumps (tracker ID
        # swaps, teleports). Uses REAL timestamps so detection gaps don't
        # inflate acceleration, and slides history on rejection so one bad
        # sample can never poison the window (uniform-dt version deadlocked
        # after a single missed frame — found on the synthetic ground truth).
        c.history.append((float(world_xy[0]), float(world_xy[1]), t_ms / 1000.0))
        if len(c.history) > 3:
            c.history.pop(0)
        if len(c.history) == 3:
            (x1, y1, t1), (x2, y2, t2), (x3, y3, t3) = c.history
            if not is_plausible_step_t((x1, y1), t1, (x2, y2), t2, (x3, y3), t3,
                                       A_PLAUSIBLE_MAX):
                c.history.pop(0)  # slide past the discontinuity, keep newest
                return None

        outside = signed_dist_m < 0.0
        if c.state == "INSIDE":
            if outside:
                c.out_streak += 1
                if c.out_streak == 1:
                    c.t_start_ms, c.peak, c.frames_out, c.band = t_ms, 0.0, 0, error_band_m
                c.peak = max(c.peak, -signed_dist_m)
                c.band = max(c.band, error_band_m)
                c.frames_out += 1
                if c.out_streak >= self.k_out:
                    c.state, c.in_streak = "VIOLATING", 0
            else:
                c.out_streak = 0
        else:  # VIOLATING
            if outside:
                c.in_streak = 0
                c.peak = max(c.peak, -signed_dist_m)
                c.band = max(c.band, error_band_m)
                c.frames_out += 1
            else:
                c.in_streak += 1
                if c.in_streak >= self.m_in:
                    inc = IncidentCandidate(
                        track_id=track_id, t_start_ms=c.t_start_ms, t_end_ms=t_ms,
                        max_overshoot_m=round(c.peak, 3),
                        duration_ms=t_ms - c.t_start_ms,
                        n_frames_outside=c.frames_out, error_band_m=round(c.band, 3))
                    self.cars[track_id] = _CarState(history=c.history)
                    return inc
        return None

    def close_track(self, track_id: int) -> list[IncidentCandidate]:
        """Force-close one track's open window (car unseen while VIOLATING)."""
        c = self.cars.get(track_id)
        out = []
        if c and c.state == "VIOLATING" and c.frames_out >= self.k_out:
            out.append(IncidentCandidate(
                track_id=track_id, t_start_ms=c.t_start_ms, t_end_ms=c.t_last_ms,
                max_overshoot_m=round(c.peak, 3),
                duration_ms=max(c.t_last_ms - c.t_start_ms, 0),
                n_frames_outside=c.frames_out, error_band_m=round(c.band, 3)))
        if c:
            self.cars[track_id] = _CarState(history=c.history)
        return out

    def finalize(self) -> list[IncidentCandidate]:
        """Close any window still OPEN when its track vanished (car left the
        frame, occlusion, tracker swap) — a car that exits the camera while
        beyond the line is still a violation. Called at end of stream."""
        out = []
        for tid, c in list(self.cars.items()):
            if c.state == "VIOLATING" and c.frames_out >= self.k_out:
                out.append(IncidentCandidate(
                    track_id=tid, t_start_ms=c.t_start_ms, t_end_ms=c.t_last_ms,
                    max_overshoot_m=round(c.peak, 3),
                    duration_ms=max(c.t_last_ms - c.t_start_ms, 0),
                    n_frames_outside=c.frames_out, error_band_m=round(c.band, 3)))
                self.cars[tid] = _CarState(history=c.history)
        return out
