# DISCLOSURES — pre-existing assets used in APEXLINE

TrackShift's rules require disclosure of significant reuse. Everything below
is a pretrained model, public dataset, open API, or open-source library —
all product code, geometry, physics, rules engine, UI, and data pipelines in
this repository were written during the event.

| Asset | Role | License / terms |
|---|---|---|
| Ultralytics YOLOv8 (`yolov8n.pt` REDISTRIBUTED IN THIS REPO so the demo runs offline; `yolov8n-seg.pt`, COCO-pretrained) | Car detection (SEE) | AGPL-3.0 (Ultralytics) — redistribution permitted with attribution; this repo is AGPL-compatible for the hackathon |
| ByteTrack (bundled in Ultralytics `model.track`) | Persistent track IDs | MIT (orig.) via Ultralytics |
| OpenCV | Homography, clip overlay | Apache-2.0 |
| Shapely, NumPy, SciPy, pandas, scikit-learn, SQLAlchemy, FastAPI, React, Vite | Substrate libraries | BSD/MIT/Apache |
| OpenF1 API (openf1.org) | Historical F1 race_control + telemetry (labels & benchmark). Community project, unaffiliated with F1/FOM | Free for non-commercial/historical use per site terms |
| Roboflow Universe dataset(s): ___fill in exact dataset name + URL after download___ | Optional fine-tune data | ___record per-dataset license (usually CC BY 4.0)___ |
| Fine-tuned checkpoint `weights/apexline_yolov8n_ft.pt` (if present) | Trained BY US during the event in Colab from `yolov8n.pt` | derivative of AGPL-3.0 weights |
| Udacity CarND-Vehicle-Detection `test_images/test1.jpg` (one frame, used only by `scripts/make_synthetic_clip.py --fetch-sample` to cut a car sprite for the SYNTHETIC demo clip) | Guaranteed-runnable demo footage | MIT-licensed repo (github.com/udacity/CarND-Vehicle-Detection) |
| Groq API (optional) | Two uses, both optional: (1) report prose; (2) the ALTERNATIVE 'Groq Vision' detection engine (Llama-4 Scout multimodal) for uncalibrated footage — incidents from it are tagged engine=vlm_groq, make no metric claims, and still route through human review | Free-tier API terms |

No broadcast footage is included in the repo or any recorded material.
Demo clips are sim exports and our own recordings only.
