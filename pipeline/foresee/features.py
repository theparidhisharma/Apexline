"""FORESEE / features — structured features for the pre-corner violation model.

Deliberately classical ML on structured data, no LLM, no deep net: n is
hundreds of labelled events, and feature importances ARE the explainability
slide. Overfitting a deep net here would be malpractice.
"""
from __future__ import annotations

import pandas as pd

FEATURES = ["speed_max", "speed_mean", "speed_p90", "throttle_full_frac",
            "brake_frac", "tyre_age", "lap_duration", "margin_trend_3lap"]


def add_margin_trend(df: pd.DataFrame) -> pd.DataFrame:
    """3-lap trend of lap_duration per driver-session as a leaning-on-the-limit
    proxy (shrinking times while violating -> pushing)."""
    df = df.sort_values(["session_key", "driver_number", "lap_number"]).copy()
    df["margin_trend_3lap"] = (
        df.groupby(["session_key", "driver_number"])["lap_duration"]
        .transform(lambda s: s.diff().rolling(3, min_periods=1).mean())
    )
    return df


def xy(df: pd.DataFrame):
    df = add_margin_trend(df)
    X = df[FEATURES].fillna(df[FEATURES].median(numeric_only=True))
    return X, df["label"].astype(int), df
