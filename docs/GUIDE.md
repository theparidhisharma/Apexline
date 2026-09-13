# APEXLINE — Phase-by-phase build guide (2 machines, no GPU, 24 h)

Machines: **L1 = Intel i7** (API + pipeline + ffmpeg), **L2 = MacBook**
(frontend + OpenF1 mining + FORESEE — all CPU; Ultralytics uses Apple MPS if
you ever run vision on it). Free GPU = **Colab/Kaggle**, only for the gated
fine-tune. Sync spine: GitHub; fallback `git bundle` over a USB stick.

The inversion that saves you: the most differentiating layers (KNOW, FORESEE,
benchmark) are CPU-only data engineering. A CUDA error at 3 a.m. cannot kill
your standout feature.

---

## Phase 0 — Both machines, first 30 minutes

```bash
unzip apexline.zip && cd apexline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # ~5-8 min; torch CPU wheels are big
python3 pipeline/physics.py              # prints the deck numbers — verify:
# dt 0.270 s · 15.0 m @200 · 22.5 m @300 · bound 0.55 m · 7g = 68.6 m/s²
python3 tests/test_core.py               # 8/8 must pass before anything else
```

Frontend (L2):

```bash
cd web && npm install && npm run dev     # http://localhost:5173 — renders on fixtures immediately
echo "VITE_API=http://<L1-LAN-IP>:8000" > .env.local   # once L1's API is up
```

API (L1):

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000     # /docs shows OpenAPI to judges
```

Docker alternative (either box): `docker compose up` runs API + web together.

**Do tonight, on home Wi-Fi, before anything else:** `bash scripts/pull_openf1.sh`
— caches races + builds `data/labels/labels.parquet`. The venue Wi-Fi rule is
absolute: nothing in the demo may touch the internet.

---

## Phase 1 — Parallel split (hours 0–6)

**Person A (L1) — SEE on the golden clip.**
1. Record/collect footage: sim replay from a fixed trackside camera (export the
   sim's off-track flags = ground truth) or your own kart/RC/toy-track clip.
   Put it at `data/clips_src/golden.mp4`. No broadcast footage in anything
   recorded or published.
2. Fallback calibration exists already (`scripts/make_demo_calibration.py` ran
   at scaffold time). Replace it with a real one via the Calibrate screen.
3. Run: `python -m pipeline.runner --video data/clips_src/golden.mp4 --calibration data/calibrations/corner_1.json`
4. **H+2 gate:** are cars detected and tracked? Count incidents by hand on the
   clip; runner must match ±1 over 3 consecutive runs.
   - Recall bad on open-wheelers/karts → hand `notebooks/colab_finetune_yolov8n.ipynb`
     to whoever is free. Cap it at 2 hours. Meanwhile the pipeline keeps
     shipping on zero-shot — the merge of COCO {car, truck, motorcycle} is
     already in `pipeline/see/detect.py`.

**Person B (L2) — the data coup.**
1. `bash scripts/pull_openf1.sh` (if not done at home).
2. `python -m pipeline.foresee.train_f1` → AUC + feature importances into
   `data/labels/foresee_report.json`. Screenshot into the deck the moment it exists.
3. `python -m pipeline.benchmark.replay <session_key>` on the held-out race →
   precision/recall vs the FIA's own race-control record. This powers the two
   demo beats nobody else has.

**Person C (L2) — console.** It already renders on fixtures. Wire it live:
start L1's API, set `web/.env.local`, confirm the rail badge flips from
`fixtures` to `live`. Then polish IncidentDetail first (it wins the demo),
Calibrate second.

**Person D — footage, labels, deck.** Label `data/labels/vision_eval.csv`
(columns: `clip,expected_incidents,class`) with ~40 events across
clear/marginal. Fill the Roboflow rows of `DISCLOSURES.md`. Confirm the
submission format with organisers. Start the deck from `docs/references.md`.

---

## Phase 2 — Integration (hours 6–14)

1. Full loop on stage hardware: upload via `POST /sessions/1/ingest` (or the
   UI) → incidents stream over WebSocket into the queue → open one → Approve →
   ledger strike animates → export evidence zip from `/sessions/1/export`.
2. `python -m pipeline.eval.vision_eval` → freeze precision/recall per class.
   Those are your only claimable numbers.
3. Bake the safety net: `python scripts/preprocess_demo.py data/clips_src/golden.mp4 data/calibrations/corner_1.json`
   → creates `data/backup_session.db`. From now on `python scripts/demo_reset.py`
   restores a known-good state in one keystroke.

**T-12 gate (non-negotiable):** end-to-end loop AND benchmark replay both
green, or all four people converge on whichever is red. Nothing else exists.

---

## Phase 3 — The standout layer (hours 14–20)

- FORESEE live replay on the Pit Wall screen (predictions endpoint already
  serves them; C renders the ticker).
- Distance-dependent error bars are already computed per incident — make sure
  the card shows `±X cm at this range`, not a flat number.
- Optional Groq report prose: follow `docs/GROQ_SETUP.md` exactly. Skip freely.
- Cut order if bleeding (top first): tabletop live camera → F-2 strike
  forecast → report polish → Pit Wall screen (keep the endpoint) → live-session
  extras. **Never cut:** benchmark beat, F-1 demo, queue + incident detail +
  ledger, calibration, honesty beat.

---

## Phase 4 — Freeze and rehearse (last 4–6 hours)

1. Feature freeze. `python scripts/demo_reset.py`, run the golden path 3×,
   Wi-Fi OFF.
2. Record the phone backup video after the FIRST clean run, not after polish.
3. Rehearse both failure paths: pipeline stalls → `demo_reset.py` + narrate the
   pre-baked queue; laptop dies → phone video.
4. Q&A owners: A geometry/vision · B data/benchmark/FORESEE · C demo driving ·
   D product/business. Each answers their 5 hardest questions out loud once.

## Demo script pointers (the 5-minute spine)

Hook (Austria: 1,200 cases, 5 hours) → live calibration with stopwatch →
processing fills the queue → open an auto-flag (overlay clip, ±cm band,
"gained 0.21 s") → approve → strike animates → **benchmark beat** (our flags vs
FIA race-control messages, precision/recall on screen) → **FORESEE beat**
("Car 27 entering T4 — 78%") → **honesty beat** (0.51-confidence marginal call
routed to the human, steward rejects, audit log shown) → close on the
taxonomy + ROC-as-a-Service slide.

Three sentences to deliver verbatim:
- "Telemetry carries a computed half-metre ambiguity between samples —
  δ = a·Δt²/8 ≈ 0.55 m — so telemetry proposes and only vision verifies."
- "One percent of tyre on the line is legal by construction: we measure the
  innermost contact point, so the system structurally cannot false-flag it."
- "There is no LLM in the decision path. Detection is AI; adjudication is
  deterministic sporting law. In officiating, determinism is the sophistication."
