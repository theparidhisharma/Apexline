"""Background jobs: video processing, benchmark runs."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import models as M
from .ws import manager


def process_video_job(session_id: int, video: str, calibration: str,
                      corner_id: int, weights: str, engine: str = "geometry"):
    from pipeline.runner import process_video
    s = M.SessionLocal()
    sess = s.get(M.Session, session_id)

    def on_incident(inc: dict):
        row = M.Incident(session_id=session_id, corner_id=corner_id,
                         track_id=inc["track_id"], type_code=inc["type_code"],
                         context_tags=inc["context_tags"],
                         t_start_ms=inc["t_start_ms"], t_end_ms=inc["t_end_ms"],
                         max_overshoot_m=inc["max_overshoot_m"],
                         error_band_m=inc["error_band_m"],
                         duration_ms=inc["duration_ms"],
                         confidence=inc["confidence"], band=inc["band"],
                         clip_path=inc["clip_path"], clip_sha256=inc["clip_sha256"],
                         explain=inc["explain"])
        s.add(row); s.commit()
        from .main import serialize_incident
        manager.broadcast_threadsafe(session_id, {"type": "incident",
                                                  "payload": serialize_incident(row)})

    def on_prediction(pr: dict):
        row = M.Prediction(session_id=session_id, corner_id=corner_id,
                           t_ms=pr["t_ms"], kind="pre_corner_prob",
                           value=pr["risk"], model_version=pr["model_version"],
                           features={k: pr[k] for k in
                                     ("track_id", "eta_ms", "slope_m_s", "sd_now_m")})
        s.add(row); s.commit()
        manager.broadcast_threadsafe(session_id, {"type": "prediction", "payload": {
            "id": row.id, "t_ms": pr["t_ms"], "kind": "pre_corner_prob",
            "value": pr["risk"], "car": pr["track_id"], "model_version": pr["model_version"],
            "detail": f'crossing in ~{pr["eta_ms"]} ms', "features": row.features}})

    last = {"detections": 0, "incidents": 0}

    def on_progress(pr: dict):
        last.update({"detections": pr["detections"], "incidents": pr["incidents"]})
        manager.broadcast_threadsafe(session_id, {"type": "progress", "payload": pr})

    try:
        stype = sess.type if sess else "race"
        if engine == "vlm_groq":
            from pipeline.vlm.groq_detect import process_video_vlm
            process_video_vlm(video, session_type=stype,
                              on_incident=on_incident,
                              on_prediction=on_prediction,
                              on_progress=on_progress)
        else:
            if not Path(calibration).exists():
                raise FileNotFoundError(f"calibration missing: {calibration} — run the wizard first")
            process_video(video, calibration, weights=weights,
                          session_type=stype, on_incident=on_incident,
                          on_prediction=on_prediction, on_progress=on_progress)
        sess.status = "processed"
        hint = None
        if last["incidents"] == 0 and last["detections"] == 0:
            hint = ("no vehicles detected at all — check the video actually shows "
                    "cars large enough (>~80 px), and that the camera is FIXED; "
                    "panning broadcast footage will not work")
        elif last["incidents"] == 0 and engine == "vlm_groq":
            hint = (f"the vision model saw cars in {last['detections']} frame(s) "
                    "but never judged one FULLY beyond the white line — check the "
                    "boundary is clearly visible in frame, or try the geometry "
                    "engine with a calibration for tighter measurement")
        elif last["incidents"] == 0:
            hint = (f"{last['detections']} vehicle detections but zero boundary "
                    "crossings — the calibration does not match this camera view. "
                    "Open Calibrate, click points on THIS video's frame, trace the "
                    "white line, save, then re-ingest with that calibration")
        manager.broadcast_threadsafe(session_id, {"type": "job_done", "payload": {
            "incidents": last["incidents"], "detections": last["detections"],
            "status": "processed", "hint": hint}})
    except Exception as e:
        sess.status = f"error: {e}"
        manager.broadcast_threadsafe(session_id, {"type": "job_error",
                                                  "payload": {"error": str(e)}})
    sess.ended_at = dt.datetime.utcnow()
    s.commit()
