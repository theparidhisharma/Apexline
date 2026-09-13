"""APEXLINE physics core — every number computed, none vibed.

This module is the single source of truth for the physical constants and
bounds quoted on stage. Each function docstring carries the derivation so
Q&A answers come straight from the code.

Authority hierarchy consequence encoded here:
  telemetry position carries ~0.5 m mid-sample ambiguity  -> telemetry PROPOSES
  homography vision carries ~cm-scale boundary error      -> vision VERIFIES
"""
from __future__ import annotations

import numpy as np

G = 9.80665  # m/s^2

# ---------------------------------------------------------------------------
# 1. Telemetry sampling geometry (OpenF1 car_data ~= 3.7 Hz)
# ---------------------------------------------------------------------------
OPENF1_HZ = 3.7
DT_TELEMETRY = 1.0 / OPENF1_HZ  # ~= 0.270 s


def distance_per_sample(speed_kmh: float, hz: float = OPENF1_HZ) -> float:
    """Metres travelled between telemetry samples.

    200 km/h -> 15.0 m/sample ; 300 km/h -> 22.5 m/sample.
    (Deck claim: "a car covers 15-22 m between telemetry samples".)
    """
    return (speed_kmh / 3.6) / hz


def interpolation_bound(a_max: float = 60.0, dt: float = DT_TELEMETRY) -> float:
    """Max deviation of the true path from straight-line interpolation
    between two samples dt apart, with |a| <= a_max:

        delta = a_max * dt^2 / 8

    a_max = 60 m/s^2 (~6 g) and dt = 0.27 s  ->  delta ~= 0.55 m.

    This is THE number that justifies the fusion hierarchy: half-metre
    ambiguity between samples is two orders of magnitude too coarse for a
    wheel-on-line call (~cm), and exactly precise enough to gate which
    camera windows deserve vision analysis.
    """
    return a_max * dt * dt / 8.0


# ---------------------------------------------------------------------------
# 2. Plausibility (friction-circle) filter for tracker glitches
# ---------------------------------------------------------------------------
A_PLAUSIBLE_MAX = 7.0 * G  # 7 g combined — deliberately loose engineering bound


def implied_acceleration(p0, p1, p2, dt: float) -> float:
    """Magnitude of acceleration implied by three consecutive track-plane
    positions via central second difference. Used to reject physically
    impossible frame-to-frame 'teleports' (ByteTrack ID switches, blur).
    Peak real-world combined loads are ~4-6 g; 7 g is an unarguably
    conservative rejection threshold, labelled as such.
    """
    p0, p1, p2 = (np.asarray(p, dtype=float) for p in (p0, p1, p2))
    a = (p2 - 2.0 * p1 + p0) / (dt * dt)
    return float(np.linalg.norm(a))


def is_plausible_step(p0, p1, p2, dt: float, a_max: float = A_PLAUSIBLE_MAX) -> bool:
    return implied_acceleration(p0, p1, p2, dt) <= a_max


# ---------------------------------------------------------------------------
# 3. Distance-dependent ground-plane error bars
# ---------------------------------------------------------------------------
def pixel_error_band_m(H_inv: np.ndarray, u: float, v: float) -> float:
    """Local ground-plane uncertainty (metres) for +-1 px image error at (u,v).

    Reprojects the 4-neighbourhood (u+-1, v+-1) through H^-1 and returns the
    max spread from the centre point. Perspective makes this grow with
    distance from the camera: typically +-2-4 cm near-field, +-10-15 cm
    far-field. Shown per-incident on the card instead of a flat +-6 cm.
    """
    def project(px, py):
        p = H_inv @ np.array([px, py, 1.0])
        return p[:2] / p[2]

    c = project(u, v)
    spread = 0.0
    for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        spread = max(spread, float(np.linalg.norm(project(u + du, v + dv) - c)))
    return spread


# ---------------------------------------------------------------------------
# 4. Path curvature and lateral acceleration (a_y = v^2 * kappa)
# ---------------------------------------------------------------------------
def smooth_savgol(x: np.ndarray, window: int = 9, poly: int = 3) -> np.ndarray:
    """Savitzky-Golay smoothing. Raw double-differencing of 3.7 Hz positions
    is noise amplification — smooth first, always."""
    from scipy.signal import savgol_filter

    window = min(window if window % 2 == 1 else window + 1, len(x) - (1 - len(x) % 2))
    if window < poly + 2:
        return x
    return savgol_filter(x, window, poly)


def path_curvature(xs: np.ndarray, ys: np.ndarray, dt: float) -> np.ndarray:
    """kappa = |x'y'' - y'x''| / (x'^2 + y'^2)^(3/2), from smoothed positions."""
    xs = smooth_savgol(np.asarray(xs, float))
    ys = smooth_savgol(np.asarray(ys, float))
    dx, dy = np.gradient(xs, dt), np.gradient(ys, dt)
    ddx, ddy = np.gradient(dx, dt), np.gradient(dy, dt)
    denom = np.power(dx * dx + dy * dy, 1.5)
    denom[denom < 1e-9] = 1e-9
    return np.abs(dx * ddy - dy * ddx) / denom


def lateral_acceleration(speed_ms: np.ndarray, kappa: np.ndarray) -> np.ndarray:
    """a_y = v^2 * kappa (standard centripetal relation)."""
    return np.asarray(speed_ms, float) ** 2 * np.asarray(kappa, float)


def curvature_agreement(kappa_vision: np.ndarray, kappa_tel: np.ndarray,
                        tol: float = 0.35) -> float:
    """Cross-modal reconstruction-confidence in [0,1]: how well the
    vision-derived path curvature agrees with the telemetry-derived one.
    Two independent signals agreeing is the governed-AI story; disagreement
    lowers confidence and routes the incident to a human.
    """
    n = min(len(kappa_vision), len(kappa_tel))
    if n < 3:
        return 0.5
    kv, kt = np.asarray(kappa_vision[:n]), np.asarray(kappa_tel[:n])
    scale = np.maximum(np.abs(kt), 1e-4)
    rel = np.abs(kv - kt) / scale
    return float(np.clip(1.0 - np.median(rel) / tol, 0.0, 1.0))


# ---------------------------------------------------------------------------
# 5. Quasi-steady-state counterfactual (advantage cross-check, P2)
# ---------------------------------------------------------------------------
def qss_corner_time(kappas: np.ndarray, ds: float, a_lat_max: float = 4.5 * G,
                    v_cap: float = 95.0) -> float:
    """Time to traverse a path sampled every ds metres under v <= sqrt(a_lat_max/kappa).
    Point-mass, friction-limited — the model family of Heilmeier/Christ et al.
    Used only as a consistency flag against the empirical delta-t, never as
    ground truth.
    """
    kappas = np.maximum(np.asarray(kappas, float), 1e-6)
    v = np.minimum(np.sqrt(a_lat_max / kappas), v_cap)
    return float(np.sum(ds / v))


if __name__ == "__main__":  # print the deck numbers
    print(f"dt telemetry           : {DT_TELEMETRY:.3f} s")
    print(f"m/sample @200 km/h     : {distance_per_sample(200):.1f} m")
    print(f"m/sample @300 km/h     : {distance_per_sample(300):.1f} m")
    print(f"interpolation bound    : {interpolation_bound():.2f} m  (a_max=60 m/s^2)")
    print(f"plausibility threshold : {A_PLAUSIBLE_MAX:.1f} m/s^2 (7 g)")


def is_plausible_step_t(p1, t1_s: float, p2, t2_s: float, p3, t3_s: float,
                        a_max: float = A_PLAUSIBLE_MAX) -> bool:
    """Non-uniform-dt plausibility: central difference with REAL timestamps,
    so a missed detection frame no longer inflates apparent acceleration.
    a ≈ 2·(v2 − v1)/(dt1 + dt2) with v over the actual intervals."""
    import numpy as _np
    p1, p2, p3 = _np.asarray(p1, float), _np.asarray(p2, float), _np.asarray(p3, float)
    dt1, dt2 = max(t2_s - t1_s, 1e-6), max(t3_s - t2_s, 1e-6)
    v1, v2 = (p2 - p1) / dt1, (p3 - p2) / dt2
    a = 2.0 * (v2 - v1) / (dt1 + dt2)
    return float(_np.linalg.norm(a)) <= a_max
