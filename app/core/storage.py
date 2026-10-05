"""
Per-session result folders and automatic deletion of old results.

Every analysis writes to RESULTS_DIR/<session UUID>/. Folders whose newest file is
older than RESULTS_RETENTION_DAYS are deleted by `cleanup_old_results()`, which
entrypoint.sh runs once an hour:

    python -m core.storage            # delete expired session folders
"""

import os
import shutil
import time
import uuid
from pathlib import Path

RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/app/session_results"))
RETENTION_DAYS = float(os.environ.get("RESULTS_RETENTION_DAYS", "7"))


def is_valid_session_id(session_id: str) -> bool:
    """Only canonical UUIDs are accepted, so user input can never point outside RESULTS_DIR."""
    try:
        return str(uuid.UUID(session_id)) == session_id.strip().lower()
    except (ValueError, AttributeError, TypeError):
        return False


def new_session_id() -> str:
    return str(uuid.uuid4())


def session_dir(session_id: str, create: bool = False) -> Path:
    if not is_valid_session_id(session_id):
        raise ValueError(f"Invalid session UUID: {session_id!r}")
    path = RESULTS_DIR / session_id.strip().lower()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _last_modified(path: Path) -> float:
    times = [p.stat().st_mtime for p in path.rglob("*") if p.is_file()]
    return max(times, default=path.stat().st_mtime)


def cleanup_old_results(days: float = RETENTION_DAYS) -> list[str]:
    """Delete session folders not modified for `days` days. Returns the deleted folder names."""
    if not RESULTS_DIR.is_dir():
        return []
    cutoff = time.time() - days * 86400
    deleted = []
    for child in RESULTS_DIR.iterdir():
        if child.is_dir() and is_valid_session_id(child.name) and _last_modified(child) < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            deleted.append(child.name)
    return deleted


if __name__ == "__main__":
    removed = cleanup_old_results()
    print(f"[cleanup] removed {len(removed)} session folder(s) older than {RETENTION_DAYS:g} days")
