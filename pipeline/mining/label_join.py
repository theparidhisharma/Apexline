"""Mining / label join — race_control TRACK LIMITS msgs ⨝ telemetry windows.

Output: data/labels/labels.parquet — one row per (violation event | matched
compliant control lap) with FORESEE features. The timestamp alignment across
three async endpoints is the genuinely fiddly part; everything is joined on
(driver_number, lap_number) first and refined by date proximity.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("data/openf1_cache")
OUT = Path("data/labels/labels.parquet")


def _features_for_lap(car: pd.DataFrame, lap_row) -> dict:
    lap_start = pd.to_datetime(lap_row.get("date_start"))
    if pd.isna(lap_start):
        return {}
    w = car[(car["date"] >= lap_start) & (car["date"] <= lap_start + pd.Timedelta(seconds=150))]
    if len(w) < 10:
        return {}
    spd = w["speed"].astype(float)
    thr = w["throttle"].astype(float)
    brk = w["brake"].astype(float)
    return {
        "speed_max": spd.max(), "speed_mean": spd.mean(),
        "speed_p90": spd.quantile(0.9),
        "throttle_full_frac": float((thr >= 99).mean()),
        "brake_frac": float((brk > 0).mean()),
        "n_samples": len(w),
    }


def build_labels(session_keys: list[int]) -> pd.DataFrame:
    rows = []
    for sk in session_keys:
        rc_f = CACHE / f"rc_{sk}.parquet"
        if not rc_f.exists():
            continue
        rc = pd.read_parquet(rc_f)
        rc["lap_number"] = pd.to_numeric(rc.get("lap_number"), errors="coerce")
        for d in rc["driver_number"].dropna().unique().astype(int):
            car_f, laps_f = CACHE / f"car_{sk}_{d}.parquet", CACHE / f"laps_{sk}_{d}.parquet"
            if not (car_f.exists() and laps_f.exists()):
                continue
            car = pd.read_parquet(car_f)
            car["date"] = pd.to_datetime(car["date"])
            laps = pd.read_parquet(laps_f)
            bad_laps = set(rc[rc["driver_number"] == d]["lap_number"].dropna().astype(int))
            for _, lap in laps.iterrows():
                ln = lap.get("lap_number")
                if pd.isna(ln):
                    continue
                feats = _features_for_lap(car, lap)
                if not feats:
                    continue
                is_violation = int(ln) in bad_laps
                # controls: same driver, compliant laps only, downsampled 1:2
                if not is_violation and (int(ln) % 2 == 0):
                    continue
                rows.append({"session_key": sk, "driver_number": d,
                             "lap_number": int(ln), "label": int(is_violation),
                             "tyre_age": lap.get("tyre_age_at_start", np.nan),
                             "lap_duration": lap.get("lap_duration", np.nan),
                             **feats})
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    print(f"[labels] {len(df)} rows ({df['label'].sum() if len(df) else 0} violations) -> {OUT}")
    return df
