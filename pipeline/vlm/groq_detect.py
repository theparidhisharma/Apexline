"""VLM engine — track-limits detection with Groq's vision models.

WHY THIS EXISTS: the geometry engine needs a fixed camera + a 5-minute
calibration and pays you back with ±cm measurements. Arbitrary footage
(your F1 24 recording before you calibrate, a clip with a slow pan) fails
that contract. This engine trades precision for universality: it samples
frames, asks a Groq-hosted multimodal model a strictly-scoped question about
each one, and groups the answers into violation windows. No homography, no
calibration, works on any footage where a human could make the call.

HONESTY CONTRACT (say this on stage): the VLM DETECTS and SCORES; it still
does not DECIDE. Windows flow into the exact same review queue, confidence
bands (including the self-improving thresholds), taxonomy, human-in-loop
decisions, penalty ledger, and evidence-clip cutter as the geometry engine.
Incidents are tagged engine="vlm_groq" so nobody can confuse a vibes-based
detection with a measured one — there are no ±cm claims in this mode.

Setup: docs/GROQ_SETUP.md (free key -> .env). Model defaults to Llama-4
Scout on Groq; override with GROQ_VISION_MODEL if the catalog moves.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import cv2

MODEL_CANDIDATES = [
    os.environ.get("GROQ_VISION_MODEL", ""),
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]
DEFAULT_MODEL = next(m for m in MODEL_CANDIDATES if m)
SAMPLE_FPS = float(os.environ.get("VLM_SAMPLE_FPS", 1.5))   # frames/sec sent
FRAME_WIDTH = 768         # downscale before upload
MIN_CONF = 0.5            # frame-level threshold to count as "beyond"
JOIN_GAP_S = 1.6          # windows closer than this merge (sparser sampling)
CALL_SLEEP_S = 60.0 / float(os.environ.get("GROQ_RPM", 28))  # free tier ≈30 RPM
MAX_SAMPLES = int(os.environ.get("VLM_MAX_SAMPLES", 240))    # ≈ 2.5 min of video

PROMPT = """You are a motorsport track-limits spotter looking at ONE frame
from a fixed trackside camera. The track boundary is the painted white line
at the edge of the track surface (kerbs are OUTSIDE the line).

Answer ONLY with minified JSON, no prose, exactly these keys:
{"car_visible": bool,
 "beyond_line": bool,   // true only if some car appears FULLY beyond the white line (all four wheels / entire contact patch outside)
 "on_line": bool,        // any car touching the line but not fully beyond
 "approaching": bool,    // a car inside the track clearly drifting toward the line
 "confidence": float,    // 0..1, your confidence in beyond_line
 "bbox": [x0,y0,x1,y1] | null  // normalized 0..1 box of the most relevant car
}
If unsure, lower the confidence — do not guess high."""


def _encode_frame(frame) -> str:
    h, w = frame.shape[:2]
    if w > FRAME_WIDTH:
        frame = cv2.resize(frame, (FRAME_WIDTH, int(h * FRAME_WIDTH / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return base64.b64encode(buf).decode()


def make_groq_scorer(model: str = DEFAULT_MODEL):
    """Returns score(frame)->dict using the Groq API. Import-time free."""
    from groq import Groq  # lazy: geometry-only installs never need it
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set — see docs/GROQ_SETUP.md, "
                           "or use the geometry engine instead")
    client = Groq(api_key=key)
    state = {"model": model}

    def score(frame) -> dict:
        b64 = _encode_frame(frame)
        for attempt in range(5):
            try:
                r = client.chat.completions.create(
                    model=state["model"], temperature=0, max_tokens=200,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"}},
                    ]}])
                txt = r.choices[0].message.content.strip()
                txt = txt[txt.find("{"): txt.rfind("}") + 1]
                d = json.loads(txt)
                return {"car_visible": bool(d.get("car_visible")),
                        "beyond_line": bool(d.get("beyond_line")),
                        "on_line": bool(d.get("on_line")),
                        "approaching": bool(d.get("approaching")),
                        "confidence": float(d.get("confidence") or 0.0),
                        "bbox": d.get("bbox")}
            except Exception as e:
                msg = str(e).lower()
                if "model" in msg and ("not found" in msg or "decommission" in msg
                                       or "does not exist" in msg):
                    nxt = [m for m in MODEL_CANDIDATES if m and m != state["model"]]
                    if nxt:
                        state["model"] = nxt[0]
                        continue
                    raise RuntimeError(
                        f"no available Groq vision model ({e}); check the model "
                        "list at console.groq.com and set GROQ_VISION_MODEL")
                if "rate" in msg or "429" in msg:
                    time.sleep(8.0 * (attempt + 1))     # rate limit: back off hard
                elif attempt == 4:
                    return {"car_visible": False, "beyond_line": False,
                            "on_line": False, "approaching": False,
                            "confidence": 0.0, "bbox": None, "error": True}
                else:
                    time.sleep(1.5 * (attempt + 1))
    return score


def process_video_vlm(video: str, out_dir: str = "data/clips",
                      session_type: str = "race", scorer=None,
                      on_incident=None, on_prediction=None,
                      on_progress=None) -> list[dict]:
    """Same output schema as pipeline.runner.process_video."""
    from pipeline.know.confidence import band
    from pipeline.know.taxonomy import Context, classify
    from pipeline.know.evidence import cut_clip, burn_overlay

    scorer = scorer or make_groq_scorer()
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    stride = max(int(round(fps / SAMPLE_FPS)), 1)
    est = total // stride if total else 0
    if est > MAX_SAMPLES:   # keep free-tier runtime sane; stay uniform
        stride = max(int(total / MAX_SAMPLES), stride)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    frames: list[dict] = []        # per-sample verdicts
    last_pred_ms = -10_000
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % stride:
            i += 1
            continue
        ok, frame = cap.retrieve()
        if not ok:
            break
        t_ms = int(i / fps * 1000)
        v = scorer(frame)
        v["t_ms"] = t_ms
        frames.append(v)
        if (v["approaching"] and not v["beyond_line"]
                and t_ms - last_pred_ms > 3000 and on_prediction):
            last_pred_ms = t_ms
            on_prediction({"track_id": 0, "t_ms": t_ms,
                           "risk": round(min(0.9, 0.55 + v["confidence"] * 0.4), 3),
                           "eta_ms": 800, "slope_m_s": None, "sd_now_m": None,
                           "kind": "pre_corner_prob",
                           "model_version": f"vlm:{DEFAULT_MODEL.split('/')[-1]}"})
        if on_progress and len(frames) % 5 == 0:
            on_progress({"frames_done": i // stride,
                         "total": max(total // stride, 1),
                         "pct": round(100 * i / max(total, 1), 1),
                         "detections": sum(f["car_visible"] for f in frames),
                         "incidents": 0, "t_ms": t_ms})
        time.sleep(CALL_SLEEP_S if scorer.__name__ != "fake" else 0)
        i += 1
    cap.release()

    # ---- group beyond-line frames into violation windows ----
    incidents: list[dict] = []
    window: list[dict] = []

    def flush():
        if not window:
            return
        t0, t1 = window[0]["t_ms"], window[-1]["t_ms"]
        conf = round(min(0.95, sum(f["confidence"] for f in window) / len(window)), 3)
        code, tags, _auto = classify(Context(session_type=session_type))
        b = band(conf, 0.0, tags)
        raw = str(Path(out_dir) / f"inc_{len(incidents)+1}_raw.mp4")
        final = str(Path(out_dir) / f"inc_{len(incidents)+1}.mp4")
        try:
            cut_clip(video, t0, t1, raw)
            clip_hash = burn_overlay(raw, None, final,
                                     label=f"{code} · VLM {conf:.2f} · beyond white line")
        except Exception as e:
            final, clip_hash = "", f"clip-error:{e}"
        bb = next((f["bbox"] for f in window if f.get("bbox")), None)
        inc = {"track_id": 0, "type_code": code, "context_tags": tags,
               "t_start_ms": t0, "t_end_ms": max(t1, t0 + 200),
               "max_overshoot_m": None, "error_band_m": None,
               "duration_ms": max(t1 - t0, 200), "confidence": conf, "band": b,
               "clip_path": final, "clip_sha256": clip_hash,
               "explain": {"engine": "vlm_groq", "model": DEFAULT_MODEL,
                           "frames_fully_outside": len(window),
                           "footprint_method": "vlm_judgment",
                           "peak_bbox_norm": bb,
                           "note": "no homography in VLM mode — no metric "
                                   "overshoot; judgement is frame-level and "
                                   "routed to human review by band"}}
        incidents.append(inc)
        if on_incident:
            on_incident(inc)
        window.clear()

    for f in frames:
        hit = f["beyond_line"] and f["confidence"] >= MIN_CONF
        if hit:
            if window and f["t_ms"] - window[-1]["t_ms"] > JOIN_GAP_S * 1000:
                flush()
            window.append(f)
        elif window and f["t_ms"] - window[-1]["t_ms"] > JOIN_GAP_S * 1000:
            flush()
    flush()

    if on_progress:
        on_progress({"frames_done": max(total // stride, 1),
                     "total": max(total // stride, 1), "pct": 100.0,
                     "detections": sum(f["car_visible"] for f in frames),
                     "incidents": len(incidents), "t_ms": -1, "done": True})
    return incidents
