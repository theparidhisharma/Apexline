"""LEARN — the self-improving loop, done the officiating-safe way.

Every steward decision is ground truth. After each one we:

1. RECALIBRATE the confidence bands (bounded, deterministic, logged):
   - stewards reject auto-flags        -> auto_flag threshold rises (stricter)
   - clean streak of confirmed flags   -> it relaxes a little (never below floor)
   - stewards approve low-conf calls   -> auto_clear threshold drops so fewer
     real violations get silently cleared
   Adjustments are ±0.01-0.02 per update, clamped to hard rails
   (auto_clear ∈ [0.20, 0.45], auto_flag ∈ [0.70, 0.92]), and every change is
   appended to an audit history. The scoring FORMULA never changes — only
   where the triage lines sit. That keeps the loop explainable on stage:
   "the stewards are labelling; the system is recalibrating, not mutating."

2. EXPORT TRAINING DATA for the next model iteration:
   data/learned/review_labels.csv — one row per decided incident (clip path,
   window, taxonomy code, confidence, human verdict). Feed it back into the
   Colab notebook as hard examples: rejected incidents are your false
   positives, approved ones are confirmed positives.

State lives in data/learned/thresholds.json; pipeline.know.confidence reads it
on every band() call (mtime-cached), so recalibration takes effect for the
very next incident without a restart.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

STATE_PATH = Path("data/learned/thresholds.json")
LABELS_PATH = Path("data/learned/review_labels.csv")

DEFAULTS = {"auto_clear": 0.35, "auto_flag": 0.75}
RAILS = {"auto_clear": (0.20, 0.45), "auto_flag": (0.70, 0.92)}
STEP = 0.02
RELAX = 0.01


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"bands": dict(DEFAULTS), "n_decisions": 0, "per_band": {},
            "history": [], "updated_at": None}


def _clamp(name: str, v: float) -> float:
    lo, hi = RAILS[name]
    return round(min(hi, max(lo, v)), 3)


def update_from_decisions(decisions: list[dict]) -> dict:
    """decisions: [{id, band, confidence, status, type_code, clip_path,
                    t_start_ms, t_end_ms, max_overshoot_m}] — decided only.

    Recomputes stats over the full record (idempotent), derives thresholds
    from the defaults by replaying bounded adjustments, writes state + CSV.
    """
    decided = [d for d in decisions if d.get("status") in ("approved", "rejected")]
    state = _load_state()
    bands = dict(DEFAULTS)
    history: list[dict] = []

    per_band: dict[str, dict] = {}
    for b in ("auto_flag", "needs_review", "auto_clear"):
        rows = [d for d in decided if d.get("band") == b]
        app = sum(1 for d in rows if d["status"] == "approved")
        rej = len(rows) - app
        per_band[b] = {"n": len(rows), "approved": app, "rejected": rej,
                       "precision": round(app / len(rows), 3) if rows else None}

    # --- auto_flag calibration: target false-flag rate < 5 % -------------
    af = per_band["auto_flag"]
    if af["n"] >= 5:
        fp_rate = af["rejected"] / af["n"]
        if fp_rate > 0.05:
            steps = min(af["rejected"], 5)  # each rejected flag pushes it up
            bands["auto_flag"] = _clamp("auto_flag", bands["auto_flag"] + STEP * steps)
            history.append({"band": "auto_flag", "to": bands["auto_flag"],
                            "why": f"{af['rejected']}/{af['n']} auto-flags rejected (fp {fp_rate:.0%})"})
        elif af["rejected"] == 0 and af["n"] >= 10:
            bands["auto_flag"] = _clamp("auto_flag", bands["auto_flag"] - RELAX)
            history.append({"band": "auto_flag", "to": bands["auto_flag"],
                            "why": f"{af['n']} confirmed flags, zero rejections — relax 0.01"})

    # --- auto_clear calibration: approved violations near the clear line
    # mean real incidents were nearly silenced -> lower the line ----------
    near_clear_approved = [d for d in decided
                           if d["status"] == "approved"
                           and d.get("confidence", 1.0) < bands["auto_clear"] + 0.10]
    if near_clear_approved:
        steps = min(len(near_clear_approved), 3)
        bands["auto_clear"] = _clamp("auto_clear", bands["auto_clear"] - STEP * steps)
        history.append({"band": "auto_clear", "to": bands["auto_clear"],
                        "why": f"{len(near_clear_approved)} approved violation(s) within 0.10 of the clear line"})

    state.update({
        "bands": bands,
        "n_decisions": len(decided),
        "per_band": per_band,
        "history": (history + state.get("history", []))[:40],
        "defaults": DEFAULTS,
        "updated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1))

    # --- fine-tune label export (the "next model" half of the loop) ------
    with LABELS_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["incident_id", "clip_path", "t_start_ms", "t_end_ms",
                    "type_code", "confidence", "max_overshoot_m",
                    "human_verdict", "label"])
        for d in decided:
            w.writerow([d.get("id"), d.get("clip_path") or "", d.get("t_start_ms"),
                        d.get("t_end_ms"), d.get("type_code"),
                        d.get("confidence"), d.get("max_overshoot_m"),
                        d["status"],
                        1 if d["status"] == "approved" else 0])
    return state


def current_state() -> dict:
    return _load_state()
