# APEXLINE

**FIA-grade track-limits stewarding from a single camera.**
Built for TrackShift 2026 (Plaksha University, 12–13 Sep 2026) · Theme: AI Motorsport Intelligence — Track Limits Detection

> The FIA proved this category works — at the top 1% of the sport, with installed camera arrays, per-car telemetry, and a staffed operations centre. APEXLINE unbundles that architecture from its infrastructure and delivers it to the tier that inherited F1's circuits but not F1's tools.

---

## Table of Contents

1. [The Problem, With Receipts](#1-the-problem-with-receipts)
2. [Why the Obvious Build Loses](#2-why-the-obvious-build-loses)
3. [The Product](#3-the-product)
4. [Architecture — SEE · KNOW · FORESEE](#4-architecture--see--know--foresee)
5. [The Violation Taxonomy](#5-the-violation-taxonomy)
6. [What Makes This Defensible](#6-what-makes-this-defensible)
7. [Data Sources](#7-data-sources)
8. [Tech Stack](#8-tech-stack)
9. [The Math We'll Be Grilled On](#9-the-math-well-be-grilled-on)
10. [Repository Structure](#10-repository-structure)
11. [MVP Scope & Build Plan](#11-mvp-scope--build-plan)
12. [Demo Script](#12-demo-script)
13. [Honest Constraints & Red-Team Findings](#13-honest-constraints--red-team-findings)
14. [Business Model](#14-business-model)
15. [Judge Q&A Bank](#15-judge-qa-bank)
16. [Disclosures](#16-disclosures)
17. [References](#17-references)

---

## 1. The Problem, With Receipts

Track-limits enforcement is currently a function of **infrastructure budget**, not algorithmic difficulty.

| Event | What happened | Source |
|---|---|---|
| **Austria 2023** | 1,200+ potential violations in a 71-lap race; race control couldn't keep up; 12 penalties issued ~5 hours after the flag; podium-adjacent classification changed post-race; 47 laps deleted in qualifying alone | Crash.net, Autosport, ESPN |
| **Austin (COTA) 2023** | Haas's right-of-review showed four rival cars exceeding limits, unpunished; stewards' own verdict called enforcement *"completely unsatisfactory"*; the corner's CCTV was badly positioned | Motorsport.com, RaceFans, ESPN |
| **Silverstone 2026** | One driver collected three separate track-limits penalties in nine laps — even at the top of the sport, the notify-team-then-warn-driver loop is that slow | worldofspeed.org |
| **GB4 Championship, Silverstone 2026** | Race-three classification amended *post-race* — the Austria failure mode, reproduced at junior-series level | — |

The FIA's own diagnosis after Austria: timing loops were **"insufficiently accurate"**; the most accurate detector was **"a data analyst looking at the video itself."** That's why the fix is vision-first, and it's why APEXLINE is vision-first too.

**Where the fix stops.** Catapult's RaceWatch/ECAT platform — GPU-accelerated, verifies every lap in real time — serves F1, WEC, WRC, Formula E, SuperGT, and NASCAR. Permanent installs are cited at exactly **four circuits, all in Japan**. Everything below that — FIA F4, regional and national championships (India: MRF MMSC at Madras International Circuit, JK Tyre NRC), karting, club racing, track days — is still stewarded the pre-2023 way: marshals, a handful of static cameras, human eyeballs, arguments afterwards.

**Root cause:** the algorithm (vehicle detection + boundary geometry) is commodity in 2026. What has never been productised is the *delivery mechanism* — enforcement that works with the cameras a club already owns, calibrated in minutes, at a price a national series can actually pay.

---

## 2. Why the Obvious Build Loses

Most hackathon teams that hear "track limits" will ship "YOLO detects a car crossing a white line." That's a solved problem at the top of the sport and a toy everywhere else — and any judge who follows motorsport will clock it in the first 30 seconds.

APEXLINE's answer to *"doesn't the FIA already do this?"* is: **yes, and that's our proof of demand.** We're not building a better detector. We're building the workflow layer the FIA proved was necessary and productising it for the ~99% of motorsport that can't buy it.

The detector is the engine. **The steward console is the product.**

---

## 3. The Product

**One-line positioning:** APEXLINE turns any fixed camera — a ₹5,000 webcam, a GoPro, an existing CCTV feed — into an automated track-limits steward.

Point it at a corner, calibrate in five minutes by clicking the track boundary, and get:

- Automatic violation detection with per-corner confidence scores and distance-dependent error bars
- A **triaged steward review queue**: auto-clear the obvious ~80%, surface the marginal ~20% for a human — the FIA's own stated triage philosophy
- Boundary-overlay evidence clips, hashed and timestamped, generated in under 10 seconds
- An automatic penalty ledger implementing the real sporting-code escalation (warning → warning → black-and-white flag → 5 s → 10 s)
- A full audit trail that survives a protest
- **Advantage quantification**: "Car 27, T4 exit, all four wheels out, gained 0.21 s vs. own median" — using the stewards' actual decision heuristic, not a proxy for it

**Target user (primary):** the Clerk of the Course / steward team at national-championship, club, karting, and track-day events. **Secondary:** teams and driver academies (Pit Wall Mode — evidence review, strike-risk alerts), circuit operators (per-corner analytics for redesign decisions).

**Why now:** the FIA spent 2023–2026 proving the workflow and publicising it (triage, clips-to-teams, geofencing); commodity models (YOLOv8/11, ByteTrack) made the detection layer free; the tier below has visibly identical failures and zero tooling.

---

## 4. Architecture — SEE · KNOW · FORESEE

The build follows a strict **authority hierarchy**: prediction may warn, telemetry may propose, only vision may verify, only a human may decide.

```
DATA SOURCES                    APEXLINE CORE                              CONSOLES
─────────────                   ─────────────                              ────────
Video (upload/RTSP) ──────▶  SEE:    YOLO/RF-DETR → ByteTrack →   ──────▶  Steward Console
                              homography → per-wheel footprint →           (queue · clip · decide)
                              hysteresis FSM

OpenF1 / FastF1 ───────────▶ KNOW:   identity bind · taxonomy    ──────▶  Pit Wall Mode
(race_control, car_data,     V1–V7 · context tags · advantage             (strikes · warnings ·
 location)                   Δt · penalty ledger FSM ·                     evidence packs)
                              evidence packaging

Sim telemetry ─────────────▶ FORESEE: pre-corner violation      ──────▶  Report / Export
(ground truth)                probability · strike-risk forecast ──────▶  Eval / FIA-Benchmark Page
                               trained on OpenF1-mined labels

                              SQLite → (Postgres-ready) · /data/clips · audit log
```

### Layer 1 — SEE (the verifier)
Vehicle detector (YOLOv8/RF-DETR) → ByteTrack persistent IDs → per-wheel ground-contact points projected through a calibrated homography → signed distance to the boundary polyline (conservative: 1% of tyre on the line = legal) → hysteresis FSM (k consecutive frames fully outside → violation candidate). Output: verified crossings with confidence **and an uncertainty band**.

### Layer 2 — KNOW (the context engine)
Ingests synchronised telemetry (OpenF1/FastF1 for F1 data, exported sim telemetry, or transponder/GPS in production) alongside the SEE event stream: identity binding, taxonomy classification (V1–V7, below), advantage quantification, the penalty ledger state machine, and hashed evidence packaging.

### Layer 3 — FORESEE (the standout)
Two classical-ML predictive models, deliberately **not** deep learning or an LLM, because officiating decisions must be explainable:

- **F-1 (pre-corner violation probability):** gradient-boosted classifier on entry-speed delta vs. the driver's own compliant envelope, lateral-position trend, throttle/brake shape, tyre stint age, and traffic proximity. Output: *"Car 27 entering T4, 11 km/h over compliant envelope → 78% violation probability"* — a warning fired **before** the crossing, attacking the FIA's own documented notify-then-warn latency loop.
- **F-2 (strike-risk forecasting):** per-driver, per-corner margin-trend regression — *"violation likely within ~3 laps at T9."*

**Training data — the standout move:** the OpenF1 API exposes historical F1 `race_control` messages, including literal track-limits rulings (*"BLACK AND WHITE FLAG FOR CAR 1 — TRACK LIMITS"*) with car, lap, and timestamp, joined to per-car telemetry at ~3.7 Hz. We mine every officially-adjudicated violation since 2023 to build a labelled dataset of **real, FIA-ruled violations**, train FORESEE against it, hold out entire races, and report the number no rival team can produce:

> *"Given only public telemetry, our engine reproduces X% of the FIA's official track-limits calls at a Y% false-positive rate — validated against race-control records from 2023–2026."*

**Zero generative models sit in the decision path.** Detection is AI; adjudication is deterministic geometry and a rules engine, on purpose — a learned judge is an unappealable one.

---

## 5. The Violation Taxonomy

"Track limits" is not one violation. Most rival builds will detect exactly one (V1/V2 geometry) and not know the rest exist.

| Type | Rule logic | Vision alone | Telemetry adds | Human required? |
|---|---|---|---|---|
| **V1** Lap-time deletion | All four wheels beyond the line at a monitored corner | Primary signal | — | Only marginal band |
| **V2** Repeated infringement (strikes) | Per-driver count → escalating penalty | Primary signal | — | Only marginal band |
| **V3** Overtaking off track | Pass completed with any part outside limits | Detects the crossing | Relative position change classifies it as V3 | Yes — final call |
| **V4** Keeping/defending position off track | Running wide to retain position; mitigation considered | Detects crossing | Detects proximity of rival | Yes |
| **V5** Lasting advantage | ≈0.2–0.3 s lap-time gain heuristic | Weak alone | Primary — mini-sector time vs. driver's compliant median | Threshold call |
| **V6** Unsafe rejoin | Endangering others on return to track | Trajectory + proximity | Closing speeds → risk score | Yes, always |
| **V7** Forcing another off | Racecraft offence adjacent to track limits | — | — | Investigation |
| **X** Context exceptions | Avoiding collision, lost control, gave place back | Proximity → "possible forced-off" tag | Speed/brake anomaly annotation | Yes — routes to human by design |

**The system never auto-decides V3–V7 or anything context-tagged.** It classifies, quantifies, packages evidence, and prioritises. Only clean, high-confidence, context-free V1/V2 geometry is eligible for auto-triage — exactly the FIA's own "throw out the 80%" doctrine, stated by FIA deputy race director Tim Malyon: *they don't want computer vision to diagnose cancer — they want it to throw out the 80% of cases where there clearly is no cancer.*

---

## 6. What Makes This Defensible

| Layer | vs. FIA/Catapult ECAT-RaceWatch | vs. a rival hackathon team |
|---|---|---|
| **Deployment** | Installed camera arrays + per-car telemetry + weeks of integration | Single commodity camera, ≤5 min calibration |
| **Cost shape** | Enterprise contract, top ~1% of the sport | Priced like the timing services grassroots already buys |
| **Validation** | Internal, proprietary | **Public, reproducible benchmark against OpenF1's real race-control decisions** |
| **Prediction** | Positioning-based flagging (2026 update) | FORESEE — pre-corner probability and strike-risk forecasting, trained on real FIA rulings |
| **Scope** | One violation type well-covered by infra | Seven-type taxonomy + context exceptions |
| **Honesty** | Internal accuracy figures not public | Measured precision/recall published, marginal band routed to humans on stage |

A rival can copy a bounding box overlaid on a line by tomorrow morning. They cannot copy the OpenF1 label-mining pipeline, the taxonomy rules engine, the advantage-quantification math, or the fusion authority hierarchy overnight — because each of those requires actual data engineering, not a demo trick.

---

## 7. Data Sources

| Source | What it gives us | Access | Use |
|---|---|---|---|
| **OpenF1 API** | Historical F1 `race_control` (incl. literal TRACK LIMITS flags/deletions), `car_data` (speed/throttle/brake/gear/DRS @ ~3.7 Hz), `location`, `laps`, `position`, `intervals`, `weather` — free, no auth for historical data | Rate-limited (~30 req/10s) → bulk-pulled and cached locally | Labelled violation dataset, FORESEE training, the FIA-benchmark demo |
| **FastF1** | Convenient session/telemetry joins over the same ecosystem | Free (pip) | Faster data engineering for the mining pipeline |
| **Sim exports** (Assetto Corsa / ACC / F1 24) | Fixed trackside-camera video + exported car coordinates/off-track flags = pixel-perfect ground truth | Free | Vision-layer eval set, calibration validation |
| **Roboflow Universe** | Open F1-car detection datasets (116-image and 442-image team-class sets) | Free, YOLO-format export | Optional 30–40 min fine-tune, gated on measured zero-shot recall |
| **Ultralytics YOLOv8/YOLO11, ByteTrack, RF-DETR** | Pretrained detection + tracking, used as-is | Free/open | The SEE layer |
| **Own footage** | Phone/GoPro of a marked boundary | Free | Live-calibration demo beat |

**Broadcast footage is never used in anything recorded or published** — copyright risk, and it isn't needed: our own footage plus sim exports plus OpenF1's public telemetry cover every demo beat.

---

## 8. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + Vite + Tailwind, `<video>`/`<canvas>` overlays | Canvas overlay *is* the review UX; no SSR needed |
| Backend API | FastAPI (Python) | Same language as the CV pipeline; async; auto OpenAPI docs |
| CV pipeline | YOLOv8s/YOLO11 (detection, seg only if needed) → ByteTrack → OpenCV homography + shapely geometry | Every component battle-proven, installable in minutes |
| Violation logic | Deterministic geometry + hysteresis FSM — no LLM | The rule is written law; determinism is a maturity signal, stated explicitly to judges |
| Prediction | LightGBM/XGBoost/GBM (FORESEE) | Explainable, retrains in minutes on CPU, no GPU risk on the standout feature |
| Jobs | FastAPI `BackgroundTasks` + in-process queue, `ffmpeg` for clip cutting | One box, hackathon scale |
| DB | SQLite via SQLAlchemy, Postgres-ready schema | Zero-ops, file-backed, migration path stated not built |
| Deployment | Local machine, GPU if available else CPU @ 720p/10fps | Zero external dependency = zero demo-day Wi-Fi failure mode |

**Pretrained, used as-is:** YOLOv8n/s COCO weights, ByteTrack. **Trained by us:** the FORESEE GBM only, on OpenF1-mined labels, held out **by session** (a race is never split across train/test).

---

## 9. The Math We'll Be Grilled On

- **Homography:** pixel `(u,v)` → track-plane `(X,Y)` via a 3×3 matrix from ≥4 correspondences; per-point error band = spread of a ±1 px reprojection through H⁻¹ — distance-dependent, larger far from camera, shown per incident.
- **Why 3.7 Hz telemetry can't adjudicate a wheel-on-line call:** Δt ≈ 0.27 s at 3.7 Hz ⇒ 15–22.5 m travelled between samples at 200–300 km/h. Bounding acceleration at |a| ≤ 6g, the maximum mid-interval position ambiguity is δ = a·Δt²/8 ≈ **0.55 m** — two orders of magnitude coarser than a centimetre-scale wheel-on-line call. This one computed number is the entire "telemetry proposes, vision verifies" defence.
- **7g plausibility filter:** frame-to-frame implied acceleration > 7×9.81 m/s² is physically impossible for a race car (peak real loads run ~4–6g) → the frame is dropped as a tracking glitch before it ever reaches the FSM.
- **Advantage quantification (V5):** corner-segment Δt vs. the driver's own compliant-lap median, cross-checked (optionally) against a quasi-steady-state point-mass recomputation of the clipped, in-bounds trajectory — the same family of model used in published racing-trajectory research (Heilmeier et al. 2020, Christ et al. 2021). Disagreement between the two routes the incident to a human.
- **Spatial gating:** geometry is evaluated only inside a monitored zone polygon, in curvilinear (s, d) coordinates — the Frenet-frame formalism from autonomous-racing literature (Werling et al. 2010) — with a rolling ±3 s buffer preserving evidence after a car leaves frame.
- **The boundary-reference correction:** the operative limit at a corner is not always the white line — race directors sometimes redefine it to the kerb edge for a specific corner (e.g. Silverstone's Copse/Stowe). APEXLINE's calibration wizard exposes this as a per-corner dropdown (white line / kerb edge / custom polyline), matching how limits are actually published rather than hard-coding one rule.

---

## 10. Repository Structure

```
apexline/
├── README.md
├── DISCLOSURES.md              # every pretrained model, lib, dataset, API + license
├── CHANGELOG.md                # updated at every mentor checkpoint — delta-growth score
├── docs/
│   ├── dossier/                # the four planning documents this README distills
│   ├── deck/                   # judged presentation + one-pager
│   └── references.md
├── data/                       # git-ignored except manifests
│   ├── openf1_cache/           # race_control / car_data / location / laps
│   ├── labels/                 # labels.parquet — mined violations + controls
│   ├── sim/                    # recorded sim video + exported ground-truth telemetry
│   ├── clips_src/               # demo source videos (own/kart/sim only — never broadcast)
│   └── calibrations/           # per-corner homography, boundary polyline, reference choice
├── pipeline/
│   ├── see/                    # detect.py · track.py · calibrate.py · footprint.py · geometry.py · fsm.py
│   ├── know/                   # identity.py · taxonomy.py · advantage.py · ledger.py · evidence.py
│   ├── foresee/                # features.py · train_f1.py · predict.py
│   ├── mining/                 # openf1_client.py · label_join.py
│   ├── benchmark/               # replay.py — our flags vs. official race_control
│   └── eval/                   # vision_eval.py — precision/recall, confusion matrix
├── server/                     # FastAPI: routes, models, websocket push, background jobs
├── web/                        # React + Vite + Tailwind consoles
│   └── src/screens/            # Setup / Calibrate / Live / ReviewQueue / IncidentDetail /
│                                #   PitWall / Ledger / Benchmark / Eval / Report
└── scripts/                    # pull_openf1.sh · preprocess_demo.py · demo_reset.py
```

---

## 11. MVP Scope & Build Plan

**P0 (must exist to demo at all):** calibration wizard · detection pipeline on uploaded video · incident generation with confidence + severity bands · steward review queue with clip player + overlay + approve/reject · penalty ledger with live escalation.

**P1:** the OpenF1 mining pipeline and FIA-benchmark page, session report/evidence export, distance-dependent error bars, the 7g glitch filter, per-wheel signed-distance timeline, FORESEE live-replay ticker.

**P2 (cut first under time pressure):** tabletop live-camera demo, F-2 strike forecasting, occluded-wheel inference, report-export polish.

**Explicitly out of scope:** auth beyond a role switcher, multi-camera fusion, real telemetry ingest (mocked and labelled "simulated" in the UI), mobile app, custom-trained detection models unless zero-shot recall forces it.

**Hard rule:** if the FIA-benchmark replay is not running end-to-end against real `race_control` data by the T-12h mark, everything else stops until it is.

---

## 12. Demo Script (5 minutes)

1. **Hook (0:00–0:30):** Austria's 1,200 unreviewed cases, 5-hour result delay, 12 late penalties. *"The FIA fixed this with GPU clusters and a staffed operations centre. Here's how everyone else still does it."*
2. **Live calibration (0:30–1:10):** four reference points, boundary polyline, confirm — on a corner angle the judges pick. Stopwatch on screen. *"That's the entire installation."*
3. **SEE + KNOW (1:10–2:10):** live processing, queue fills, an auto-flagged incident opens with the boundary overlay, 31 cm overshoot, 0.94 confidence, +0.21 s advantage — approve, and the ledger strike animates in.
4. **The benchmark beat (2:10–3:00):** a real Grand Prix session replayed from public telemetry, our flags scrolling next to the FIA's actual race-control messages in real time, with a live recall/precision number on screen.
5. **FORESEE + Pit Wall (3:00–3:40):** a pre-corner violation-probability warning fires *before* the crossing appears on screen; the evidence pack — *"the pack Haas didn't have in Austin."*
6. **The honesty beat (3:40–4:20):** a marginal, 0.51-confidence incident, context-tagged "possible forced-off," routed to a human, rejected on stage, logged. *"We automate the obvious, quantify the debatable, and never replace the judge."*
7. **Close (4:20–5:00):** the taxonomy slide, the ROC-as-a-service model, one line — *"FIA-grade calls, one camera, and an operations centre any championship can rent."*

Live vs. mocked, stated plainly: calibration and processing are live; a fully pre-processed backup session is one keystroke away; broadcast footage never appears in anything recorded.

---

## 13. Honest Constraints & Red-Team Findings

We red-teamed our own pitch before the judges could. What survived, and what changed:

- **The grassroots-pain inference had a hole.** F1's epidemic is partly an artefact of paved-runoff Grade 1–2 circuits (grass/gravel edges self-police). **Correction:** the ICP is not "clubs broadly" — it's championship promoters of junior/national series racing on the *same* paved-runoff circuits F1 uses, plus the operators of those circuits, plus teams. *"The tier that inherited F1's circuits but not F1's tools."*
- **Automated detection can create liability, not just relief.** A volunteer Clerk of the Course who now has 200 logged violations must act on them or explain why not — some officials may prefer ambiguity. **Mitigation, built into the product, not bolted on:** advisory-mode framing, an organiser-configurable monitored-corner list, and an audit log pitched as protecting officials in a protest, not exposing them.
- **Regulatory admissibility is not automatic.** Third-party tool output has no formal standing under sporting codes until a federation homologates it. **Consequence:** we sell *decision support*, never "automated enforcement," until an ASN homologation — which we name as the real long-term moat, not a blocker.
- **Hardware isn't free.** Many lower-tier venues have sparse or zero per-corner CCTV — the same failure mode that burned F1 at Austin. We say "commodity camera kit," never "zero hardware."
- **TAM, stated honestly:** organised circuit racing is a small world — a focused vertical on the order of ₹10–100 crore/year at maturity, not venture scale. We say this on stage; judges hear a hundred fake TAMs a day, and the honest number is a pattern interrupt that builds trust rather than costing it.
- **Technical failure modes, ranked by demo-day danger:** monocular footprint error at marginal-call scale (mitigated by the human-routed band, quantified with a published error bar); pack-racing occlusion (occluded frames never auto-flag, sim/kart footage only — never pack racing — on stage); the sim-to-reality gap (heat haze, dust, monsoon — the line-quality index refuses corners it can't see reliably); cross-lap identity persistence (ByteTrack holds IDs across seconds, not laps — production identity comes from the transponder feed every timed event already has).

---

## 14. Business Model

**GTM ladder (the sentence for the pitch):** *"We land with one national series promoter, expand to their circuits, and scale through timing providers — teams are a second product on the same pipeline."*

| Tier | What | Buyer | Verdict |
|---|---|---|---|
| Per-season license | Full-series stewarding software | Championship promoter | **Best wedge** — one buyer covers 15–30 races |
| Circuit annual license | Permanent per-corner install | Circuit operator (MIC, Kari, BIC) | Good ARR complement — calibrate once, monetise year-round |
| OEM licensing | CV+FORESEE layer inside existing timing/race-control suites | MYLAPS/Al Kamel/TSL-class vendors | **Best scale path** — they own distribution and the transponder identity feed |
| Team seat (Pit Wall) | Strike-risk alerts + rival evidence packs | Teams/academies | Small volume, high judge-legible ROI |
| Managed stewarding (ROC-as-a-Service) | Software + a shared remote analyst pod | Promoters without officiating staff | The margin layer — triage economics make a multi-tenant ops centre viable, the Mphasis-shaped business |
| Direct SaaS to individual clubs | Self-serve subscriptions | Volunteer club committees | **Weak** — tiny budgets, no procurement authority, possible preference for ambiguity |

**Milestones:** 0–3 months — free pilot, publish the mined benchmark + eval harness openly. 3–12 months — 2–3 paid per-season licenses, first circuit annual, shared-ROC pilot. 12–24 months — ASN homologation as an advisory tool, OEM conversation with a timing vendor, FIA-pyramid entry via F4/regional series.

---

## 15. Judge Q&A Bank

| Question | Answer |
|---|---|
| Doesn't the FIA already do this? | Yes, since 2023 — and it's our proof of demand. It's available to ~1% of motorsport. We productise it for the rest. |
| Why would single-camera accuracy be trusted? | We don't ask for trust on marginal calls — those route to humans by design, with a published error bar. We ask for trust on the obvious majority, proven with measured recall. |
| Why no LLM in the decision path? | The rule is written law; geometry is auditable. A learned judge is an unappealable one. Detection is AI; adjudication is deterministic on purpose. |
| Why GBM, not deep learning, for FORESEE? | Explainability is a feature in officiating — feature importances are shown on stage. With hundreds of labelled events, a deep net would overfit; that would be malpractice, not sophistication. |
| How is 3.7 Hz telemetry enough? | It isn't, for adjudication — that's precisely why the authority hierarchy exists (see §9). Telemetry proposes and predicts; only vision verifies. |
| What's your biggest technical weakness? | Monocular footprint uncertainty on oblique views — stated, measured, and designed around via the marginal band. We'd rather show our error bars than hide them. |
| Won't Catapult just add this? | Their business is enterprise integration with elite series; down-market self-serve SaaS is a different company. If they descend, that's an acquisition conversation — and we'd have the installed base. |
| Did you train on the test set? | No — held out by entire session; a race is never split across train and test. |

---

## 16. Disclosures

Per the hackathon's original-work rule, this project uses the following pretrained/external components, disclosed in full:

- **Pretrained models:** YOLOv8n/s and YOLO11 (Ultralytics, COCO checkpoints), ByteTrack (bundled via `model.track`), optionally RF-DETR (Apache 2.0)
- **Libraries:** Ultralytics, OpenCV, shapely, FastAPI, SQLAlchemy, React/Vite/Tailwind
- **Data:** OpenF1 API (unofficial, unaffiliated with Formula 1 — attributed as such everywhere), FastF1, optional Roboflow Universe racing-vehicle datasets
- **No F1/FOM logos or broadcast footage** appear in any recorded or published material — sim exports and own footage only

All build logic — the violation FSM, the homography and error-band math, the taxonomy engine, the advantage-quantification heuristic, the confidence-scoring formula, and the FORESEE feature design — was written and is understood end-to-end by the team, per the "don't AI-generate your differentiating logic" rule: these are exactly the parts Q&A probes.

---

## 17. References

1. Heilmeier, Wischnewski, Hermansdorfer, Betz, Lienkamp, Lohmann (2020). *Minimum curvature trajectory planning and control for an autonomous race car.* Vehicle System Dynamics 58(10):1497–1527.
2. Christ, Wischnewski, Heilmeier, Lohmann (2021). *Time-optimal trajectory planning for a race car considering variable tyre-road friction.* Vehicle System Dynamics 59(4):588–612.
3. Betz et al. (2022). *Autonomous Vehicles on the Edge: A Survey on Autonomous Vehicle Racing.* IEEE OJ-ITS.
4. Kabzan et al. (2019). *AMZ Driverless: The Full Autonomous Racing System.* arXiv:1905.05150.
5. Werling, Ziegler, Kammel, Thrun (2010). *Optimal trajectory generation for dynamic street scenarios in a Frenét frame.* IEEE ICRA.
6. Zhang et al. (2022). *ByteTrack: Multi-Object Tracking by Associating Every Detection Box.* ECCV, arXiv:2110.06864.
7. OpenF1 API documentation (openf1.org) — public, unofficial, unaffiliated with Formula 1.
8. FIA and Catapult public statements, 2023–2026 (FIA Insights, Motorsport.com, Engadget, Catapult blog) — cited throughout as sourced or vendor-claimed, never invented.

---

*The detector is the engine. The steward console is the product. The honesty is the differentiator.*
