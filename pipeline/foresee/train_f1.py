"""FORESEE F-1 — gradient-boosted pre-corner violation probability.

Held-out split BY RACE (never random rows: that leaks driver-session state
and judges will ask). Reports AUC + precision@recall + feature importances.

Run:  python -m pipeline.foresee.train_f1
Out:  data/labels/foresee_f1.joblib + data/labels/foresee_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_recall_curve, roc_auc_score

from .features import FEATURES, xy

LABELS = Path("data/labels/labels.parquet")
MODEL = Path("data/labels/foresee_f1.joblib")
REPORT = Path("data/labels/foresee_report.json")
MODEL_VERSION = "f1-gbm-0.1"


def main():
    df = pd.read_parquet(LABELS)
    sessions = sorted(df["session_key"].unique())
    if len(sessions) < 2:
        raise SystemExit("need >=2 races for a held-out split — pull more data")
    holdout = sessions[-1]
    X, y, df = xy(df)
    tr, te = df["session_key"] != holdout, df["session_key"] == holdout

    clf = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05)
    clf.fit(X[tr], y[tr])
    p = clf.predict_proba(X[te])[:, 1]
    auc = roc_auc_score(y[te], p) if y[te].nunique() > 1 else float("nan")
    prec, rec, _ = precision_recall_curve(y[te], p)

    report = {
        "model_version": MODEL_VERSION,
        "holdout_session": int(holdout),
        "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "auc": round(float(auc), 3),
        "precision_at_recall_0.8": round(float(prec[np.argmin(np.abs(rec - 0.8))]), 3),
        "feature_importances": dict(sorted(
            zip(FEATURES, np.round(clf.feature_importances_, 3).tolist()),
            key=lambda kv: -kv[1])),
    }
    joblib.dump({"model": clf, "version": MODEL_VERSION, "features": FEATURES}, MODEL)
    REPORT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
