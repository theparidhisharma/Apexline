# CHANGELOG — update at every mentor checkpoint (delta-growth is scored)

## v0.1.0 — scaffold
- SEE: YOLOv8+ByteTrack wrapper, homography calibration w/ residuals +
  distance-dependent error bands, per-wheel footprint, hysteresis FSM w/ 7g
  plausibility gate, (s,d) zone gating.
- KNOW: V1–V7 taxonomy + context exceptions, transparent confidence formula,
  penalty-ledger FSM, evidence clips w/ overlay burn-in + SHA-256 manifest,
  advantage quantification.
- FORESEE: F-1 GBM (held-out-by-race split) + F-2 strike-risk trend; OpenF1
  miner + label join; FIA-benchmark replay harness.
- Server: FastAPI + SQLite + WebSocket push + evidence-pack zip export.
- Console: review queue (3 bands), incident detail w/ clip player & per-wheel
  timeline, ledger strike tracks, calibration wizard, pit wall. Fixture
  fallback so UI demos even with the backend down.
- Tests: 8/8 passing (FSM flicker/crossing, tyre-on-line legality, 7g gate,
  bands, taxonomy, ledger escalation, interpolation bound).

## next
- [ ] zero-shot recall number on golden clip (H+2 gate)
- [ ] labels.parquet row count after tonight's pull
- [ ] first benchmark precision/recall screenshot

## v0.2.0 — solo build: landing + HITL + self-improvement
- F1-broadcast UI overhaul (carbon black / F1 red / italic display caps),
  landing page with stat strip → ops centre.
- Ingest screen: drag-drop a real video, live job log, one-click to queue.
- Incident detail: taxonomy mapping + accuracy score + explicit
  human-in-loop verdict panel; approve w/ penalty override or ledger default;
  "mark wrong" feeds the loop; escalate.
- Self-improvement loop: steward verdicts recalibrate confidence bands
  (bounded ±0.02, hard rails, audited history, live via mtime-cached read)
  and export data/learned/review_labels.csv as fine-tune hard examples.
  New: GET /learn/state, Learning screen with threshold visualization.
- Fine-tuned weights auto-detected at weights/apexline_yolov8n_ft.pt
  (GET /model shows which model is live). POST /bootstrap for zero-setup demo.

## v0.3.0 — precision pass + dynamic landing
- FIXED (found via synthetic ground truth): 7g plausibility gate deadlocked
  after a single missed detection frame — now uses real timestamps
  (non-uniform dt) + sliding history. New regression test (9/9 passing).
- FIXED: class filter now inspects the checkpoint's own class names — a
  single-class fine-tune ('racecar') is no longer filtered to zero
  detections by the COCO id filter. Any custom fine-tune now works.
- FSM finalize(): a car leaving the frame while beyond the line still emits
  its violation (closure: track_lost_while_outside).
- Exact coordinates on every incident: peak_bbox_px, peak_world_m (corner
  frame), per-wheel signed distances, peak_t_ms — shown in the incident modal.
- Synthetic demo clip now 6 passes / 4 known violations incl. a marginal
  0.16 m call and a two-car pass; verified: pipeline flags exactly 4.
- Landing page now dynamic: animated live-replay canvas (car 27 runs wide at
  T4, race control catches it), race-control ticker marquee, count-up stats,
  headline shine, optional real-video hero layer served from /media.

## v0.4.0 — broadcast demo + live FORESEE on video
- New broadcast-look demo clip (perspective trackside cam, kerb + blue paint +
  gravel, hoardings, crowd, TV bug/timing strip, 3 liveries): 6 passes, 4
  scripted violations. VERIFIED end-to-end: exactly 4 incidents, clean and
  tyre-on-line passes ignored, evidence clips cut.
- FORESEE now runs LIVE on the video: pipeline/foresee/live.py projects each
  car's boundary-distance trend and emits violation risk BEFORE the wheels
  cross (all 4 demo violations predicted 121-599 ms early). Events persist
  (Prediction rows), stream over WS, animate on the Pit Wall, and stamp the
  incident ("FORESEE called it 240 ms early") in the modal.
- Tracker ID-churn merge: one physical excursion split by re-identification
  now merges into a single incident (limitation disclosed in code).
- Motion pass across the console: card entry stagger, confidence shimmer,
  modal/screen transitions, ledger strike pop, ingest scan-line, live
  prediction slide-ins. Landing hero video now uses the broadcast clip.

## v0.5.0 — the it-actually-works release
- ROOT-CAUSE FIXES for "uploaded my video, nothing happened":
  (1) evidence clips were mp4v — browsers can't play that codec; every clip
      (and the landing video) is now H.264 +faststart and verified playable.
  (2) ingest silently used corner_1.json for every upload — calibration is
      now selectable per-ingest, listed from /calibrations, with a loud UI
      warning that YOUR footage needs YOUR calibration.
  (3) zero feedback during processing — live progress bar (%, frames,
      detections, incidents) over WebSocket, completion summary with
      ACTIONABLE hints (0 detections vs 0 crossings diagnosed differently),
      and errors surfaced instead of swallowed.
  (4) fixtures no longer masquerade as real data: sample data only renders
      when the backend is unreachable, and is labeled as such.
- NEW ENGINE — Groq Vision (pipeline/vlm/groq_detect.py): violation
  detection on ANY footage with zero calibration via Groq multimodal
  (Llama-4 Scout). Frame sampling -> strict-JSON judgement -> window
  grouping -> same clips/taxonomy/bands/HITL/ledger/learning as geometry.
  Approaching-line frames emit FORESEE predictions. Engine selector in the
  Ingest screen. Tagged engine=vlm_groq; no metric claims by design.
- Streamed == stored == returned: churn merge now happens ONLINE (stale
  tracks force-closed after 600 ms, pending buffer), so the queue never
  shows phantom incidents. Verified end-to-end over the real HTTP API:
  4 events = 4 DB rows = 4 in job summary, every one predicted in advance.
- yolov8n.pt ships in the repo — first run needs no internet.

## v0.5.1 — env + liveliness
- server/main.py now loads .env itself (zero-dep parser) — GROQ_API_KEY works
  the moment the file exists; no exports, no python-dotenv needed.
- Groq Vision hardened for the free tier: ~28 requests/min pacing
  (GROQ_RPM to override), 429-aware backoff, model fallback chain with a
  clear error if the catalog moved (GROQ_VISION_MODEL to pin), sample cap
  for long videos (VLM_MAX_SAMPLES).
- macOS "Reduce Motion" was nuking EVERY animation (the "dead" UI): the
  reduced-motion rules are now selective — loops stop, gentle fades stay.
- Alive pass: global processing bar, new-incident red flash, title
  underline sweep, hover motion on ledger/pit-wall/verdicts, live dot pulse.
- GROQ_SETUP.md: load_dotenv(".env") (bare call crashes via heredoc), git
  note for non-repos.
