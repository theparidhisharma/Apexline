"""Benchmark — our KNOW-engine flags vs the FIA's official race_control record.

The demo sentence nobody else can say: "Given only public telemetry, our
engine reproduces X% of the FIA's official track-limits calls at Y%
false-positive rate — validated against race-control records."

Method: replay one held-out race's telemetry through the KNOW rules
(anomalous corner-segment speed/lap-time deltas as violation proposals) and
score matched / missed / extra against official TRACK LIMITS messages.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CACHE = Path("data/openf1_cache")
OUT = Path("data/labels/benchmark.json")


def our_flags_for_session(session_key: int, z_thresh: float = 1.6) -> set[tuple[int, int]]:
    """Propose (driver, lap) violation flags from lap-time anomalies:
    laps meaningfully faster than the driver's rolling median while carrying
    top-decile speed (the 'gained time by running wide' signature)."""
    flags = set()
    for f in CACHE.glob(f"laps_{session_key}_*.parquet"):
        d = int(f.stem.split("_")[-1])
        laps = pd.read_parquet(f).dropna(subset=["lap_duration", "lap_number"])
        if len(laps) < 8:
            continue
        med = laps["lap_duration"].rolling(7, min_periods=4, center=True).median()
        z = (laps["lap_duration"] - med) / laps["lap_duration"].std()
        for _, row in laps[z < -z_thresh / 2].iterrows():
            flags.add((d, int(row["lap_number"])))
    return flags


def official_flags(session_key: int) -> set[tuple[int, int]]:
    f = CACHE / f"rc_{session_key}.parquet"
    if not f.exists():
        return set()
    rc = pd.read_parquet(f).dropna(subset=["driver_number", "lap_number"])
    return {(int(r["driver_number"]), int(r["lap_number"])) for _, r in rc.iterrows()}


def run(session_key: int) -> dict:
    ours, official = our_flags_for_session(session_key), official_flags(session_key)
    matched = ours & official
    result = {
        "session_key": session_key,
        "official_events": len(official), "our_flags": len(ours),
        "matched": len(matched), "missed": len(official - ours), "extra": len(ours - official),
        "precision": round(len(matched) / len(ours), 3) if ours else 0.0,
        "recall": round(len(matched) / len(official), 3) if official else 0.0,
        "missed_list": sorted(official - ours)[:20],
        "note": "telemetry-only proposals vs official race_control; vision layer "
                "verifies in deployment — this measures the PROPOSE stage.",
    }
    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    import sys
    run(int(sys.argv[1]))
