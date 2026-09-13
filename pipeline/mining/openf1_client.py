"""Mining / OpenF1 — cached, rate-limit-respecting puller. Offline-first.

OpenF1 (openf1.org): free, no auth for historical data from 2023+. Community
project, unaffiliated with F1/FOM — say "public F1 telemetry via the
open-source OpenF1 project". Rate limit is tight (~30 req/10 s): this client
sleeps between calls and caches every response to parquet so the demo runs
with Wi-Fi OFF. Run scripts/pull_openf1.sh TONIGHT, not at the venue.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.openf1.org/v1"
CACHE = Path("data/openf1_cache")


def _get(endpoint: str, params: dict, sleep_s: float = 0.6) -> list[dict]:
    key = endpoint + "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    key = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in key)
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data))
    time.sleep(sleep_s)  # stay far under the rate limit
    return data


def sessions(year: int) -> pd.DataFrame:
    return pd.DataFrame(_get("sessions", {"year": year, "session_type": "Race"}))


def race_control_track_limits(session_key: int) -> pd.DataFrame:
    df = pd.DataFrame(_get("race_control", {"session_key": session_key}))
    if df.empty:
        return df
    return df[df["message"].str.contains("TRACK LIMITS", na=False)].copy()


def car_data(session_key: int, driver_number: int) -> pd.DataFrame:
    return pd.DataFrame(_get("car_data", {"session_key": session_key,
                                          "driver_number": driver_number}))


def location(session_key: int, driver_number: int) -> pd.DataFrame:
    return pd.DataFrame(_get("location", {"session_key": session_key,
                                          "driver_number": driver_number}))


def laps(session_key: int, driver_number: int | None = None) -> pd.DataFrame:
    p = {"session_key": session_key}
    if driver_number:
        p["driver_number"] = driver_number
    return pd.DataFrame(_get("laps", p))


def pull_session_bundle(session_key: int, out_dir: Path = CACHE) -> dict:
    """Bulk-pull everything a session needs and persist as parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = race_control_track_limits(session_key)
    rc.to_parquet(out_dir / f"rc_{session_key}.parquet")
    drivers = sorted(rc["driver_number"].dropna().unique().astype(int)) if not rc.empty else []
    for d in drivers:
        car_data(session_key, d).to_parquet(out_dir / f"car_{session_key}_{d}.parquet")
        location(session_key, d).to_parquet(out_dir / f"loc_{session_key}_{d}.parquet")
        laps(session_key, d).to_parquet(out_dir / f"laps_{session_key}_{d}.parquet")
    return {"session_key": session_key, "track_limit_msgs": len(rc), "drivers": drivers}
