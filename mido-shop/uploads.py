import os
from uuid import uuid4
from flask import current_app

ALLOWED = {"png", "jpg", "jpeg", "webp"}


def _magic_ok(head, ext):
    if ext == "png":
        return head.startswith(b"\x89PNG")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8")
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def save_upload(f, max_mb=8):
    """Returns (filename, error). (None, None) when no file was sent."""
    if not f or not f.filename:
        return None, None
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED:
        return None, "الصورة لازم تكون png أو jpg أو webp"
    head = f.stream.read(16)
    f.stream.seek(0, 2)
    size = f.stream.tell()
    f.stream.seek(0)
    if not _magic_ok(head, ext):
        return None, "الملف ده مش صورة صالحة"
    if size > max_mb * 1024 * 1024:
        return None, "الصورة أكبر من %d ميجا" % max_mb
    name = "%s.%s" % (uuid4().hex, ext)
    f.save(os.path.join(current_app.config["UPLOAD_DIR"], name))
    return name, None


def remove_upload(name):
    if not name:
        return
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], name))
    except OSError:
        pass
