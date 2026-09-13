#!/usr/bin/env bash
# Run TONIGHT on home Wi-Fi. Bulk-pulls and caches OpenF1 data so the entire
# demo runs offline. Venue Wi-Fi is a demo-killer; this script is the antidote.
set -e
cd "$(dirname "$0")/.."
python3 - << 'PY'
from pipeline.mining.openf1_client import sessions, pull_session_bundle
# 2023-2025 race sessions; grab the last 6 with track-limits activity
for year in (2023, 2024, 2025):
    df = sessions(year)
    if df.empty: continue
    for sk in df["session_key"].tolist()[-2:]:
        try:
            info = pull_session_bundle(int(sk))
            print(info)
        except Exception as e:
            print(f"session {sk}: {e}")
PY
python3 -c "
from pipeline.mining.label_join import build_labels
from pathlib import Path
keys = sorted({int(f.stem.split('_')[1]) for f in Path('data/openf1_cache').glob('rc_*.parquet')})
build_labels(keys)
"
echo 'Done. data/openf1_cache + data/labels/labels.parquet are demo-ready offline.'
