"""Pre-bake the backup session end-to-end from a golden clip, then freeze it.

Usage: python scripts/preprocess_demo.py data/clips_src/golden.mp4 data/calibrations/corner_1.json
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")
from server import models as M
from server.jobs import process_video_job

video, calib = sys.argv[1], sys.argv[2]
M.init_db()
s = M.SessionLocal()
e = M.Event(name="Backup Demo", venue="pre-baked")
s.add(e); s.commit()
sess = M.Session(event_id=e.id, name="Golden clip", type="race", status="created")
s.add(sess); s.commit()
process_video_job(sess.id, video, calib, corner_id=1, weights="yolov8n.pt")
shutil.copy("data/apexline.db", "data/backup_session.db")
print(f"Backup baked: session {sess.id} -> data/backup_session.db")
