# Solo runbook — one person, one demo

## Setup (once)
```bash
unzip apexline.zip && cd apexline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p weights && cp /path/to/your/best.pt weights/apexline_yolov8n_ft.pt   # YOUR trained model
python3 tests/test_core.py            # 8/8
```
The model is auto-detected — no config edit. Confirm with:
`curl localhost:8000/model` → `"fine_tuned": true`. The rail in the UI shows
`model: fine-tuned ✓`.

## Run (two terminals)
```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000      # T1
cd web && npm install && npm run dev                     # T2 → http://localhost:5173
```

## Demo path (what you click on stage)
1. **Landing** — let it breathe 3 s, then *Enter ops centre*.
2. **Calibrate** — click points, save, note the residual (skip live if nervous;
   a fallback calibration ships in `data/calibrations/corner_1.json`).
3. **Ingest video** — drop your real corner clip → *Start processing*.
   Incidents stream into the Review queue over WebSocket as they're found.
4. **Review queue** — open the highest-confidence card. Show: cropped
   evidence clip (boundary + call burned in), **taxonomy** (V2 + plain-English
   rule), **accuracy score** with ±cm band, and the **human-in-loop panel**
   saying whether the system will or won't decide alone.
5. **Approve violation** (penalty dropdown: ledger default or override) →
   ledger strike animates. Open a needs-review card → **Mark wrong**.
6. **Learning loop** screen — the rejection just moved the flag threshold;
   history line explains why; `review_labels.csv` row count ticked up.
   Say: "every steward verdict retrains the triage — bounded, audited,
   and the formula itself never mutates."
7. `python scripts/demo_reset.py` between rehearsals.

## Recording the F1-24 clip yourself (when you have the game)
Time Trial at the Red Bull Ring -> run wide at T9/T10 on 3-4 laps -> Replay ->
static trackside camera at the corner -> OBS screen record 1080p. Calibrate
that view in the Calibrate tab (4+ points on the white line area), then ingest.
Disclose the game in DISCLOSURES.md. Until then:

## The shipped broadcast demo (guaranteed to run, offline)
```bash
python scripts/make_synthetic_clip.py --fetch-sample
python -m pipeline.runner --video data/clips_src/synth.mp4 \
       --calibration data/calibrations/corner_synth.json
```
Three passes: clean · tyre-on-line (must NOT flag) · violation. The homography
is exact by construction, so this doubles as a correctness proof on stage:
"we know the ground truth of this scene — the system flags exactly the one
real violation and refuses to flag the tyre-on-line pass."
A pre-generated `data/clips_src/synth.mp4` + `corner_synth.json` ship in the
zip, so this works offline out of the box.

```bash
python -m pipeline.runner --video data/clips_src/broadcast.mp4 \
       --calibration data/calibrations/corner_broadcast.json
```
6 passes, 4 scripted violations — verified: exactly 4 incidents, each one
PREDICTED before the crossing (watch the Pit Wall while it processes).
Regenerate with scripts/make_broadcast_clip.py (--cut-from your_f1_image.jpg
to use a car your fine-tune knows).

## Your own F1 footage — the two ways that work
1) GEOMETRY (±cm): the camera view must be FIXED and calibrated. Calibrate
   tab -> pause a frame of YOUR video -> click 4+ points on the white-line
   area with known spacings -> trace the boundary -> save. Then Ingest with
   that calibration selected. If the job ends "N detections, 0 crossings",
   the calibration doesn't match the view — recalibrate.
2) GROQ VISION (any footage, incl. slight pans): set GROQ_API_KEY (.env,
   docs/GROQ_SETUP.md), pick the Groq Vision engine in Ingest, upload. Frame
   judgements are grouped into violation windows; clips + taxonomy +
   confidence + human-in-loop are identical. No ±cm claims in this mode —
   say that out loud in the demo, it's a feature.
