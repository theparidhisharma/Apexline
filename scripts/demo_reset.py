"""One keystroke: clean DB + reload the pre-baked backup session.
Run before every rehearsal and immediately before the judged demo."""
import shutil
import sqlite3
from pathlib import Path

DB = Path("data/apexline.db")
BACKUP = Path("data/backup_session.db")

if DB.exists():
    DB.unlink()
if BACKUP.exists():
    shutil.copy(BACKUP, DB)
    print("Backup session loaded.")
else:
    import sys; sys.path.insert(0, ".")
    from server.models import init_db
    init_db()
    print("Fresh DB initialised (no backup found — bake one after a good run:")
    print("  cp data/apexline.db data/backup_session.db)")
