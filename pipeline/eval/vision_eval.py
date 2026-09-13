"""Vision eval — precision/recall of SEE on labelled clips.

Ground truth: (a) sim exports where the sim's own off-track flag is truth,
(b) ~40 hand-labelled real clips (data/labels/vision_eval.csv with columns:
clip,expected_incidents,class[clear|marginal]). Report per-class: >=95%
recall target on 'clear'; marginal reported separately — honesty as a feature.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from ..runner import process_video


def main(eval_csv: str = "data/labels/vision_eval.csv",
         calibration: str = "data/calibrations/golden.json",
         weights: str = "yolov8n.pt"):
    rows = list(csv.DictReader(open(eval_csv)))
    results, agg = [], {"clear": {"tp": 0, "fn": 0, "fp": 0}, "marginal": {"tp": 0, "fn": 0, "fp": 0}}
    for r in rows:
        incs = process_video(r["clip"], calibration, out_dir="data/clips/eval", weights=weights)
        got, exp, cls = len(incs), int(r["expected_incidents"]), r.get("class", "clear")
        tp, fn, fp = min(got, exp), max(exp - got, 0), max(got - exp, 0)
        for k, v in (("tp", tp), ("fn", fn), ("fp", fp)):
            agg[cls][k] += v
        results.append({"clip": r["clip"], "class": cls, "expected": exp, "detected": got})
    report = {"per_clip": results, "per_class": {}}
    for cls, m in agg.items():
        p = m["tp"] / (m["tp"] + m["fp"]) if m["tp"] + m["fp"] else None
        rc = m["tp"] / (m["tp"] + m["fn"]) if m["tp"] + m["fn"] else None
        report["per_class"][cls] = {**m, "precision": p, "recall": rc}
    Path("data/labels/vision_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report["per_class"], indent=2))


if __name__ == "__main__":
    main(*sys.argv[1:])
