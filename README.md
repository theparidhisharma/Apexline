# APEXLINE — FIA-grade track-limits stewarding from a single camera

**SEE verifies · KNOW classifies · FORESEE predicts · humans decide.**

Below F1, track limits are policed by eyeballs on static monitors. The FIA
fixed this with camera arrays, per-car telemetry, and a staffed operations
centre; APEXLINE unbundles the *decision architecture* from the
infrastructure: one commodity camera, a five-minute calibration, a triage-first
steward console, evidence clips that survive protests, and predictive models
validated against the FIA's own published race-control record.

## Architecture

```
Video ──▶ SEE   : YOLOv8+ByteTrack → homography → per-wheel footprint →
                  signed distance → hysteresis FSM (+7g plausibility gate)
OpenF1 ─▶ KNOW  : identity bind · V1–V7 taxonomy + context exceptions ·
                  advantage Δt · penalty-ledger FSM · SHA-256 evidence packs
labels ─▶ FORESEE: F-1 pre-corner violation GBM · F-2 strike-risk trend
                  (trained on FIA-adjudicated events mined from race_control)
          ──▶ FastAPI + SQLite + WebSocket ──▶ React race-control console
```

Authority hierarchy, quantified: telemetry position carries a computed
δ = a·Δt²/8 ≈ **0.55 m** mid-sample ambiguity (3.7 Hz) — it proposes; calibrated
vision carries **±cm, distance-dependent** error bars — it verifies; anything
inside its error band, occluded, or context-tagged routes to a **human**.

## Run it

```bash
pip install -r requirements.txt
python3 tests/test_core.py                     # 8/8
uvicorn server.main:app --host 0.0.0.0        # API + /docs
cd web && npm install && npm run dev          # console (renders on fixtures instantly)
bash scripts/pull_openf1.sh                   # tonight, on real Wi-Fi
```

Full phased plan: **docs/GUIDE.md** · rules compliance: **DISCLOSURES.md** ·
optional LLM report prose: **docs/GROQ_SETUP.md** (no LLM in the decision path).

## What's deliberately NOT here
Real-time 20-car grids (the FIA's GPU problem, not our customer's), autonomous
penalties (nobody wants an unappealable judge), broadcast footage (copyright),
learned adjudication (the rule is written law; determinism is the feature).
