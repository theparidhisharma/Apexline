"""APEXLINE API — FastAPI on L1 (the Intel i7 / GPU box).

Run:  uvicorn server.main:app --host 0.0.0.0 --port 8000
Docs: http://<L1-ip>:8000/docs  (show judges the OpenAPI page)
"""
from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import models as M
from .ws import manager



def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so `uvicorn server.main:app` just works after
    `cp .env.example .env` — no shell exports, no python-dotenv required.
    Never overrides variables already set in the environment."""
    import os
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


_load_dotenv()

app = FastAPI(title="APEXLINE", version="0.1.0",
              description="SEE verifies · KNOW classifies · FORESEE predicts · humans decide")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

M.init_db()
Path("data/clips").mkdir(parents=True, exist_ok=True)
app.mount("/clips", StaticFiles(directory="data/clips"), name="clips")
Path("data/clips_src").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory="data/clips_src"), name="media")

LEDGER_STEPS = ["warn1", "warn2", "bw_flag", "p5s", "p10s"]


def db():
    return M.SessionLocal()


def audit(s, session_id, actor, action, entity, entity_id, payload=None):
    s.add(M.AuditLog(session_id=session_id, actor=actor, action=action,
                     entity=entity, entity_id=entity_id, payload=payload or {}))


# ---------- containers ----------
class EventIn(BaseModel):
    name: str
    venue: str | None = None


class SessionIn(BaseModel):
    event_id: int
    name: str
    type: str = "race"
    rule_profile: dict = {}


@app.post("/events")
def create_event(body: EventIn):
    s = db()
    e = M.Event(name=body.name, venue=body.venue)
    s.add(e); s.commit()
    return {"id": e.id, "name": e.name, "venue": e.venue}


@app.post("/sessions")
def create_session(body: SessionIn):
    s = db()
    sess = M.Session(event_id=body.event_id, name=body.name, type=body.type,
                     rule_profile=body.rule_profile, status="created")
    s.add(sess); s.commit()
    return {"id": sess.id, "name": sess.name, "type": sess.type}


# ---------- calibration ----------
class CalibrationIn(BaseModel):
    image_points: list[list[float]]
    world_points: list[list[float]]
    boundary: list[list[float]]
    boundary_reference: str = "white_line"
    zone_polygon_px: list[list[float]] | None = None


@app.post("/corners/{corner_id}/calibration")
def save_calibration(corner_id: int, body: CalibrationIn):
    from pipeline.see.calibrate import DegeneratePointsError, fit_homography, to_world
    import numpy as np
    try:
        H, residual = fit_homography(body.image_points, body.world_points)
    except DegeneratePointsError as e:
        raise HTTPException(400, detail=f"DEGENERATE_POINTS: {e}")
    boundary_world = to_world(H, np.asarray(body.boundary)).tolist()
    s = db()
    c = s.get(M.Corner, corner_id)
    if c is None:
        c = M.Corner(id=corner_id, name=f"corner-{corner_id}")
        s.add(c)
    c.homography = H.tolist()
    c.boundary_polyline = boundary_world
    c.boundary_reference = body.boundary_reference
    c.calib_residual_px = residual
    c.calibrated_at = dt.datetime.utcnow()
    c.calib_version = (c.calib_version or 0) + 1
    audit(s, None, "operator", "calibrate", "corner", corner_id,
          {"residual_px": residual, "version": c.calib_version,
           "reference": body.boundary_reference})
    s.commit()
    # persist for the pipeline runner
    Path("data/calibrations").mkdir(parents=True, exist_ok=True)
    Path(f"data/calibrations/corner_{corner_id}.json").write_text(json.dumps({
        "H": H.tolist(), "boundary_world": boundary_world,
        "residual_px": residual, "boundary_reference": body.boundary_reference,
        "zone_polygon_px": body.zone_polygon_px}))
    return {"homography": H.tolist(), "residual_px": residual, "version": c.calib_version}


# ---------- ingest ----------
@app.post("/sessions/{session_id}/ingest")
async def ingest(session_id: int, tasks: BackgroundTasks,
                 file: UploadFile | None = None, corner_id: int = 1,
                 calibration: str | None = None, weights: str = "auto",
                 engine: str = "geometry"):
    s = db()
    sess = s.get(M.Session, session_id)
    if sess is None:
        raise HTTPException(404, "session not found")
    if sess.status == "processing":
        raise HTTPException(409, "already running")
    src = Path(f"data/clips_src/session_{session_id}.mp4")
    src.parent.mkdir(parents=True, exist_ok=True)
    if file is not None:
        src.write_bytes(await file.read())
    elif not src.exists():
        raise HTTPException(422, "upload a video or place it at " + str(src))
    if engine not in ("geometry", "vlm_groq"):
        raise HTTPException(422, "engine must be geometry or vlm_groq")
    calib_path = None
    if engine == "geometry":
        calib_name = calibration or f"corner_{corner_id}.json"
        if "/" in calib_name or ".." in calib_name:
            raise HTTPException(422, "bad calibration name")
        calib_path = Path("data/calibrations") / calib_name
        if not calib_path.exists():
            raise HTTPException(422, f"calibration {calib_name} not found — create it "
                                     "in the Calibrate tab or pick one from /calibrations")
    else:
        import os as _os
        if not _os.environ.get("GROQ_API_KEY"):
            raise HTTPException(422, "GROQ_API_KEY not set — the Groq Vision engine "
                                     "needs a free key: see docs/GROQ_SETUP.md")
    sess.status = "processing"; s.commit()
    from .jobs import process_video_job
    tasks.add_task(process_video_job, session_id, str(src),
                   str(calib_path) if calib_path else "", corner_id, weights, engine)
    return {"job_id": f"session-{session_id}", "status": "processing"}


# ---------- incidents & decisions ----------
@app.get("/sessions/{session_id}/incidents")
def incidents(session_id: int, band: str | None = None, status: str | None = None):
    s = db()
    q = s.query(M.Incident).filter(M.Incident.session_id == session_id)
    if band:
        q = q.filter(M.Incident.band == band)
    if status:
        q = q.filter(M.Incident.status == status)
    return [serialize_incident(i) for i in q.order_by(M.Incident.confidence.desc())]


def serialize_incident(i: M.Incident) -> dict:
    return {"id": i.id, "session_id": i.session_id, "car_id": i.car_id,
            "track_id": i.track_id, "type_code": i.type_code,
            "context_tags": i.context_tags or [],
            "advantage_gained_s": i.advantage_gained_s,
            "t_start_ms": i.t_start_ms, "t_end_ms": i.t_end_ms,
            "max_overshoot_m": i.max_overshoot_m, "error_band_m": i.error_band_m,
            "duration_ms": i.duration_ms, "confidence": i.confidence,
            "band": i.band, "status": i.status, "note": i.note,
            "clip_url": f"/clips/{Path(i.clip_path).name}" if i.clip_path else None,
            "clip_sha256": i.clip_sha256, "explain": i.explain or {},
            "calib_version": i.calib_version}


class DecisionIn(BaseModel):
    decision: str  # approved | rejected | escalated
    note: str | None = None
    actor: str = "steward"
    penalty_step: str | None = None  # steward override of the ledger step


@app.post("/incidents/{incident_id}/decision")
async def decide(incident_id: int, body: DecisionIn):
    s = db()
    inc = s.get(M.Incident, incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    if inc.status != "pending":
        raise HTTPException(409, "already decided")
    if body.decision not in ("approved", "rejected", "escalated"):
        raise HTTPException(422, "decision must be approved|rejected|escalated")
    inc.status = body.decision
    inc.decided_by = body.actor
    inc.decided_at = dt.datetime.utcnow()
    inc.note = body.note
    audit(s, inc.session_id, body.actor, "decision", "incident", inc.id,
          {"decision": body.decision, "note": body.note})
    ledger_entry = None
    if body.penalty_step and body.penalty_step not in LEDGER_STEPS:
        raise HTTPException(422, f"penalty_step must be one of {LEDGER_STEPS}")
    if body.decision == "approved" and (inc.type_code in ("V1", "V2") or body.penalty_step):
        count = s.query(M.Penalty).filter(M.Penalty.session_id == inc.session_id,
                                          M.Penalty.car_id == inc.car_id).count()
        step = body.penalty_step or LEDGER_STEPS[min(count, len(LEDGER_STEPS) - 1)]
        p = M.Penalty(session_id=inc.session_id, car_id=inc.car_id, step=step,
                      triggered_by_incident_id=inc.id)
        s.add(p)
        ledger_entry = {"car_id": inc.car_id, "strike": count + 1, "step": step}
        audit(s, inc.session_id, "system", "ledger_step", "penalty", inc.id, ledger_entry)
    s.commit()
    await manager.broadcast(inc.session_id, {"type": "decision",
                                             "payload": serialize_incident(inc)})
    if ledger_entry:
        await manager.broadcast(inc.session_id, {"type": "ledger", "payload": ledger_entry})
    learning = run_learning_update(s, inc.session_id)
    if learning:
        await manager.broadcast(inc.session_id, {"type": "learning", "payload": learning})
    return {"incident": serialize_incident(inc), "ledger": ledger_entry,
            "learning": learning}


def run_learning_update(s, session_id: int) -> dict | None:
    """Self-improving loop: replay all steward decisions into recalibrated
    confidence bands + a fine-tune label export. Bounded + audited."""
    from pipeline.learn import feedback
    rows = s.query(M.Incident).filter(M.Incident.status.in_(["approved", "rejected"])).all()
    if not rows:
        return None
    state = feedback.update_from_decisions([
        {"id": i.id, "band": i.band, "confidence": i.confidence, "status": i.status,
         "type_code": i.type_code, "clip_path": i.clip_path,
         "t_start_ms": i.t_start_ms, "t_end_ms": i.t_end_ms,
         "max_overshoot_m": i.max_overshoot_m} for i in rows])
    audit(s, session_id, "system", "learning_update", "thresholds", 0,
          {"bands": state["bands"], "n_decisions": state["n_decisions"]})
    s.commit()
    return {"bands": state["bands"], "n_decisions": state["n_decisions"],
            "per_band": state["per_band"]}


@app.get("/learn/state")
def learn_state():
    from pipeline.learn import feedback
    st = feedback.current_state()
    st["labels_csv"] = "data/learned/review_labels.csv"
    return st


@app.get("/calibrations")
def list_calibrations():
    import json as _json
    out = []
    for f in sorted(Path("data/calibrations").glob("*.json")):
        try:
            d = _json.loads(f.read_text())
            out.append({"name": f.name,
                        "residual_px": d.get("residual_px"),
                        "boundary_reference": d.get("boundary_reference"),
                        "note": d.get("note")})
        except Exception:
            continue
    return out


@app.get("/sessions/{session_id}")
def session_status(session_id: int):
    s = db()
    sess = s.get(M.Session, session_id)
    if sess is None:
        raise HTTPException(404, "session not found")
    n = s.query(M.Incident).filter(M.Incident.session_id == session_id).count()
    return {"id": sess.id, "status": sess.status, "incidents": n}


@app.get("/model")
def model_info():
    from pipeline.weights import weights_info
    return weights_info()


@app.post("/bootstrap")
def bootstrap():
    """Ensure event 1 + session 1 exist so the console works out of the box."""
    s = db()
    e = s.get(M.Event, 1)
    if e is None:
        e = M.Event(id=1, name="TrackShift Demo GP", venue="Plaksha Circuit")
        s.add(e)
    sess = s.get(M.Session, 1)
    if sess is None:
        sess = M.Session(id=1, event_id=1, name="Race", type="race",
                         rule_profile={}, status="created")
        s.add(sess)
    s.commit()
    return {"event_id": 1, "session_id": 1, "session_status": sess.status}


# ---------- ledger ----------
@app.get("/sessions/{session_id}/ledger")
def ledger(session_id: int):
    s = db()
    out = {}
    for p in s.query(M.Penalty).filter(M.Penalty.session_id == session_id).order_by(M.Penalty.issued_at):
        e = out.setdefault(p.car_id or p.triggered_by_incident_id, {"car_id": p.car_id, "count": 0, "history": []})
        e["count"] += 1
        e["history"].append({"step": p.step, "incident_id": p.triggered_by_incident_id})
    for e in out.values():
        e["current_step"] = LEDGER_STEPS[min(e["count"] - 1, len(LEDGER_STEPS) - 1)] if e["count"] else None
        e["next_step"] = LEDGER_STEPS[min(e["count"], len(LEDGER_STEPS) - 1)]
    return list(out.values())


# ---------- predictions / benchmark / report ----------
@app.get("/sessions/{session_id}/predictions")
def predictions(session_id: int, kind: str | None = None):
    s = db()
    q = s.query(M.Prediction).filter(M.Prediction.session_id == session_id)
    if kind:
        q = q.filter(M.Prediction.kind == kind)
    return [{"id": p.id, "car_id": p.car_id,
             "car": (p.features or {}).get("track_id", p.car_id),
             "t_ms": p.t_ms, "kind": p.kind,
             "value": p.value, "model_version": p.model_version,
             "detail": (f"crossing in ~{p.features['eta_ms']} ms"
                        if p.features and "eta_ms" in p.features else None),
             "features": p.features} for p in q.order_by(M.Prediction.t_ms)]


@app.get("/sessions/{session_id}/benchmark")
def benchmark(session_id: int):
    f = Path("data/labels/benchmark.json")
    if not f.exists():
        raise HTTPException(404, "run: python -m pipeline.benchmark.replay <session_key>")
    return json.loads(f.read_text())


@app.get("/sessions/{session_id}/report")
def report(session_id: int):
    s = db()
    incs = [serialize_incident(i) for i in s.query(M.Incident)
            .filter(M.Incident.session_id == session_id)]
    from pipeline.explain.groq_explain import explain_incident
    per_band = {}
    for i in incs:
        per_band[i["band"]] = per_band.get(i["band"], 0) + 1
    n = len(incs)
    auto = per_band.get("auto_clear", 0) + per_band.get("auto_flag", 0)
    return {"session_id": session_id, "total_incidents": n,
            "auto_triage_rate": round(auto / n, 3) if n else None,
            "per_band": per_band,
            "ledger": ledger(session_id),
            "incidents": incs,
            "summaries": [explain_incident(i) for i in incs
                          if i["status"] != "pending"][:20]}


@app.get("/sessions/{session_id}/export")
def export(session_id: int):
    s = db()
    incs = s.query(M.Incident).filter(M.Incident.session_id == session_id).all()
    logs = s.query(M.AuditLog).filter(M.AuditLog.session_id == session_id).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("incidents.json", json.dumps([serialize_incident(i) for i in incs], indent=2))
        z.writestr("audit_log.json", json.dumps(
            [{"actor": l.actor, "action": l.action, "entity": l.entity,
              "entity_id": l.entity_id, "payload": l.payload, "at": str(l.at)} for l in logs], indent=2))
        manifest = {Path(i.clip_path).name: i.clip_sha256 for i in incs if i.clip_path}
        z.writestr("hash_manifest.json", json.dumps(manifest, indent=2))
        for i in incs:
            if i.clip_path and Path(i.clip_path).exists():
                z.write(i.clip_path, f"clips/{Path(i.clip_path).name}")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition":
                                      f"attachment; filename=evidence_session_{session_id}.zip"})


@app.get("/health")
def health():
    return {"status": "ok", "clips_dir": str(Path("data/clips").resolve())}


from fastapi import WebSocket, WebSocketDisconnect  # noqa: E402


@app.websocket("/sessions/{session_id}/live")
async def live(ws: WebSocket, session_id: int):
    await manager.connect(session_id, ws)
    try:
        while True:
            await ws.receive_text()  # keepalive pings from client
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
