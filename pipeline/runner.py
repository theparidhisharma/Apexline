"""End-to-end video processor: SEE -> KNOW -> incidents in SQLite.

Usage:
    python -m pipeline.runner --video data/clips_src/golden.mp4 \
        --calibration data/calibrations/t4_exit.json --session-id 1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from .physics import path_curvature, curvature_agreement
from .see.calibrate import CornerCalibration
from .see.detect import Detector
from .see.footprint import footprint_points_px, innermost_signed_distance, per_wheel_distances
from .see.fsm import ViolationFSM
from .know.confidence import score, band
from .know.taxonomy import Context, classify
from .know.evidence import cut_clip, burn_overlay
from .foresee.live import LivePredictor


def process_video(video: str, calibration: str, out_dir: str = "data/clips",
                  weights: str = "auto", sample_stride: int = 3,
                  session_type: str = "race", on_incident=None,
                  on_prediction=None, on_progress=None) -> list[dict]:
    calib = CornerCalibration.load(calibration)
    cap = cv2.VideoCapture(video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    total_samples = max(total_frames // sample_stride, 1)
    n_detections = 0
    dt = sample_stride / src_fps

    from pipeline.weights import resolve_weights
    det = Detector(weights=resolve_weights(weights))
    fsm = ViolationFSM(k_out=3, m_in=2, dt_s=dt)
    tracks_world: dict[int, list] = {}
    peak_sample: dict[int, dict] = {}   # deepest excursion per open window
    last_seen: dict[int, int] = {}      # track_id -> last t_ms with a detection
    predictor = LivePredictor()
    last_pred: dict[int, dict] = {}
    incidents: list[dict] = []
    pending: list = [None]              # online churn-merge buffer
    n_clips = 0
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def emit(inc):
        incidents.append(inc)
        if on_incident:
            on_incident(inc)

    def pending_push(inc):
        if pending[0] is not None and inc["t_start_ms"] - pending[0]["t_end_ms"] <= 1200:
            pending[0] = merge_two(pending[0], inc)
        else:
            if pending[0] is not None:
                emit(pending[0])
            pending[0] = inc

    def pending_tick(t_now_ms):
        if pending[0] is not None and t_now_ms - pending[0]["t_end_ms"] > 1400:
            emit(pending[0]); pending[0] = None

    def make_incident(cand, fpm: str, closure: str | None = None) -> dict:
        nonlocal n_clips
        peak = peak_sample.pop(cand.track_id, None)
        lp = last_pred.get(cand.track_id)
        lead = (cand.t_start_ms - lp["t_ms"]) \
            if lp and 0 <= cand.t_start_ms - lp["t_ms"] <= 4000 else None
        traj = np.asarray(tracks_world.get(cand.track_id, [(0, 0)] * 2)[-40:])
        stability = min(len(traj) / 40.0, 1.0)
        kv = path_curvature(traj[:, 0], traj[:, 1], dt) if len(traj) > 6 else np.array([])
        xm = curvature_agreement(kv, kv) if len(kv) else 0.5
        conf = score(cand.max_overshoot_m, cand.error_band_m, stability,
                     cand.occlusion_ratio, calib.residual_px, xm)
        code, tags, _auto = classify(Context(session_type=session_type))
        b = band(conf, cand.occlusion_ratio, tags)
        n_clips += 1
        raw = str(Path(out_dir) / f"inc_{n_clips}_raw.mp4")
        final = str(Path(out_dir) / f"inc_{n_clips}.mp4")
        try:
            cut_clip(video, cand.t_start_ms, cand.t_end_ms, raw)
            boundary_px = cv2.perspectiveTransform(
                calib.boundary_world.reshape(-1, 1, 2), calib.H_img_from_world).reshape(-1, 2)
            clip_hash = burn_overlay(raw, boundary_px, final,
                                     label=f"{code} · overshoot {cand.max_overshoot_m:.2f} m ± {cand.error_band_m:.2f}")
        except Exception as e:   # clip failure never kills detection
            final, clip_hash = "", f"clip-error:{e}"
        return {
            "track_id": cand.track_id, "type_code": code, "context_tags": tags,
            "t_start_ms": cand.t_start_ms, "t_end_ms": cand.t_end_ms,
            "max_overshoot_m": cand.max_overshoot_m,
            "error_band_m": cand.error_band_m,
            "duration_ms": cand.duration_ms, "confidence": conf, "band": b,
            "clip_path": final, "clip_sha256": clip_hash,
            "explain": {"frames_fully_outside": cand.n_frames_outside,
                        "homography_residual_px": calib.residual_px,
                        "cross_modal_agreement": round(float(xm), 3),
                        "footprint_method": fpm,
                        **({"closure": closure} if closure else {}),
                        **({"predicted_lead_ms": lead,
                            "predicted_risk": lp["risk"]} if lead is not None else {}),
                        **({"peak_t_ms": peak["t_ms"],
                            "peak_bbox_px": peak["bbox_px"],
                            "peak_world_m": peak["world_m"],
                            "wheel_distances_m": peak["wheels_m"]} if peak else {})},
        }

    def close_stale(t_now_ms):
        """A car that vanished while beyond the line (left frame, occlusion,
        tracker re-id) is closed after 600 ms of absence — its half of a
        churn split then reaches the merge buffer IN TIME ORDER."""
        for tid, c in list(fsm.cars.items()):
            if c.state == "VIOLATING" and t_now_ms - last_seen.get(tid, t_now_ms) > 600:
                for cand in fsm.close_track(tid):
                    pending_push(make_incident(cand, "bbox_bottom",
                                               closure="track_lost_while_outside"))

    for i, frame_dets in enumerate(det.track_video(video, sample_stride)):
        t_ms = int(i * dt * 1000)
        close_stale(t_ms)
        pending_tick(t_ms)
        n_detections += len(frame_dets)
        if on_progress and i % 25 == 0:
            on_progress({"frames_done": i, "total": total_samples,
                         "pct": round(100 * i / total_samples, 1),
                         "detections": n_detections, "incidents": len(incidents),
                         "t_ms": t_ms})
        for d in frame_dets:
            u, v = (d.xyxy[0] + d.xyxy[2]) / 2.0, d.xyxy[3]
            if not calib.in_zone(u, v):
                continue
            last_seen[d.track_id] = t_ms
            fp_px = footprint_points_px(d)
            fp_world = cv2.perspectiveTransform(
                fp_px.reshape(-1, 1, 2).astype(np.float64), calib.H).reshape(-1, 2)
            tracks_world.setdefault(d.track_id, []).append(fp_world.mean(axis=0))
            sd = innermost_signed_distance(fp_world, calib.boundary_world)
            eb = calib.error_band_m(u, v)
            ps = peak_sample.get(d.track_id)
            if ps is None or sd < ps["sd"]:
                peak_sample[d.track_id] = {
                    "sd": sd, "t_ms": t_ms,
                    "bbox_px": [round(v_, 1) for v_ in d.xyxy],
                    "world_m": [round(float(c), 3) for c in fp_world.mean(axis=0)],
                    "wheels_m": [round(float(w), 3) for w in
                                 per_wheel_distances(fp_world, calib.boundary_world)],
                }
            pred = predictor.step(d.track_id, t_ms, sd)
            if pred is not None:
                last_pred[d.track_id] = pred
                if on_prediction:
                    on_prediction(pred)
            cand = fsm.step(d.track_id, t_ms, sd, fp_world.mean(axis=0), eb)
            if cand is None:
                continue
            predictor.resolve(d.track_id)
            fpm = "seg_mask" if d.mask is not None else "bbox_bottom"
            pending_push(make_incident(cand, fpm))

    for cand in fsm.finalize():
        pending_push(make_incident(cand, "bbox_bottom",
                                   closure="track_lost_while_outside"))
    if pending[0] is not None:
        emit(pending[0]); pending[0] = None

    incidents = merge_churn(incidents)  # idempotent safety pass
    if on_progress:
        on_progress({"frames_done": total_samples, "total": total_samples,
                     "pct": 100.0, "detections": n_detections,
                     "incidents": len(incidents), "t_ms": -1, "done": True})
    print(f"[runner] {len(incidents)} incidents in {time.time()-t0:.1f}s")
    return incidents


def merge_two(prev: dict, inc: dict) -> dict:
    deeper = inc if (inc["max_overshoot_m"] or 0) > (prev["max_overshoot_m"] or 0) else prev
    merged = dict(deeper)
    merged["t_start_ms"] = min(prev["t_start_ms"], inc["t_start_ms"])
    merged["t_end_ms"] = max(prev["t_end_ms"], inc["t_end_ms"])
    merged["duration_ms"] = merged["t_end_ms"] - merged["t_start_ms"]
    ex = dict(deeper["explain"])
    ex["frames_fully_outside"] = (prev["explain"].get("frames_fully_outside", 0)
                                  + inc["explain"].get("frames_fully_outside", 0))
    ex["merged_windows"] = (prev["explain"].get("merged_windows", 1)
                            + inc["explain"].get("merged_windows", 1))
    for e in (prev["explain"], inc["explain"]):
        if "predicted_lead_ms" in e and "predicted_lead_ms" not in ex:
            ex["predicted_lead_ms"] = e["predicted_lead_ms"]
            ex["predicted_risk"] = e.get("predicted_risk")
    merged["explain"] = ex
    merged["clip_path"] = merged["clip_path"] or prev["clip_path"] or inc["clip_path"]
    return merged


def merge_churn(incidents: list[dict], max_gap_ms: int = 1200) -> list[dict]:
    """One physical excursion can split into two windows when the tracker
    re-identifies a car mid-violation (ID churn). At a single corner camera,
    outside-windows within ~1.2 s are the same excursion (a genuine separate re-entry needs ≥0.6 s of hysteresis by construction): merge them,
    keeping the union window, the deeper peak, and the earliest prediction.
    Known limit (disclosed): two DIFFERENT cars beyond the line in the same
    half-second would also merge — accepted for v1, split by identity once
    telemetry binding is active."""
    if not incidents:
        return incidents
    incidents = sorted(incidents, key=lambda i: i["t_start_ms"])
    out = [incidents[0]]
    for inc in incidents[1:]:
        prev = out[-1]
        if inc["t_start_ms"] - prev["t_end_ms"] <= max_gap_ms:
            out[-1] = merge_two(prev, inc)
        else:
            out.append(inc)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--weights", default="auto")
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--out", default="data/clips")
    a = ap.parse_args()
    incs = process_video(a.video, a.calibration, a.out, a.weights, a.stride)
    print(json.dumps(incs, indent=2)[:4000])
