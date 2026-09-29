"""نسخة احتياطية: python backup.py  (بتحفظ zip في فولدر backups/ وبتحتفظ بآخر 14 نسخة)"""
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent


def make_backup(target):
    db = BASE / "instance" / "mido.db"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        if db.exists():
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            tmp.close()
            src, dst = sqlite3.connect(str(db)), sqlite3.connect(tmp.name)
            src.backup(dst)
            dst.close()
            src.close()
            z.write(tmp.name, "mido.db")
            os.unlink(tmp.name)
        for f in (BASE / "static" / "uploads").glob("*"):
            if f.is_file() and f.name != ".gitkeep":
                z.write(f, "uploads/" + f.name)


if __name__ == "__main__":
    out = BASE / "backups"
    out.mkdir(exist_ok=True)
    path = out / ("mido-%s.zip" % datetime.now().strftime("%Y%m%d-%H%M"))
    make_backup(str(path))
    for old in sorted(out.glob("mido-*.zip"))[:-14]:
        old.unlink()
    print("saved", path)
