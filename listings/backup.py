import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "db-"
BACKUP_SUFFIX = ".sqlite3"
_lock = threading.Lock()
_last_check = 0.0


def sqlite_path() -> Path | None:
    db = settings.DATABASES["default"]
    if "sqlite" not in db.get("ENGINE", ""):
        return None
    return Path(db["NAME"])


def backup_dir() -> Path:
    return Path(settings.BACKUP_DIR)


def list_backups() -> list[Path]:
    folder = backup_dir()
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.name.startswith(BACKUP_PREFIX) and p.name.endswith(BACKUP_SUFFIX)]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def create_backup(label: str = "") -> Path | None:
    source = sqlite_path()
    if source is None or not source.exists():
        return None

    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"-{label}" if label else ""
    target = folder / f"{BACKUP_PREFIX}{stamp}{suffix}{BACKUP_SUFFIX}"
    partial = target.with_suffix(".partial")

    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(partial))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    os.replace(partial, target)
    prune_backups()
    logger.info("Database backup created: %s", target)
    return target


def prune_backups() -> None:
    keep = settings.BACKUP_KEEP
    for old in list_backups()[keep:]:
        try:
            old.unlink()
        except OSError:
            logger.warning("Could not delete old backup %s", old)


def latest_backup_age_seconds() -> float | None:
    backups = list_backups()
    if not backups:
        return None
    return time.time() - backups[0].stat().st_mtime


def maybe_backup_async() -> None:
    """Start a background backup if the newest one is older than BACKUP_INTERVAL_HOURS."""
    global _last_check
    now = time.monotonic()
    if now - _last_check < 600:
        return
    _last_check = now

    age = latest_backup_age_seconds()
    if age is not None and age < settings.BACKUP_INTERVAL_HOURS * 3600:
        return
    if not _lock.acquire(blocking=False):
        return

    def run():
        from .analytics import prune_analytics

        try:
            create_backup("auto")
            prune_analytics()
        except Exception:  # noqa: BLE001 - never break requests because of backups
            logger.exception("Automatic database backup failed")
        finally:
            _lock.release()

    threading.Thread(target=run, name="radison-db-backup", daemon=True).start()
