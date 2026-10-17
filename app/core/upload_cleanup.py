"""Free uploaded files that Streamlit keeps in memory for sessions that are gone.

Streamlit holds every uploaded file in RAM until its session is shut down. A
session that disconnects (tab closed, page refreshed, network drop) is parked for
a 2-minute reconnect window and then dropped *without* being shut down, so its
uploads (and session state) are never freed until the server restarts -- an 8 GB
VCF stays in RAM for good. This background thread shuts down parked sessions once
their reconnect window has passed and removes any other uploads whose session is
gone.

It relies on Streamlit internals (checked against 1.65). If they change, it logs
once and stops instead of breaking the app; uploads then just aren't freed.
"""

from __future__ import annotations

import asyncio
import gc
import threading
import time

SWEEP_INTERVAL_SECONDS = 60

_started = False
_start_lock = threading.Lock()


def _upload_bytes(files, session_id: str) -> int:
    return sum(len(rec.data) for rec in files.file_storage.get(session_id, {}).values())


def _sweep_on_eventloop(runtime) -> tuple[int, int]:
    """Must run on Streamlit's event loop thread, like Streamlit's own session handling."""
    files = runtime._uploaded_file_mgr
    session_mgr = runtime._session_mgr
    freed_sessions = freed_bytes = 0

    # Parked sessions past their reconnect window: Streamlit leaves them in its
    # cache without shutting them down; shutdown() also removes their uploads
    for session_id, info in session_mgr._session_storage._cache.expire():
        freed_bytes += _upload_bytes(files, session_id)
        info.session.shutdown()
        # Streamlit's main loop can keep a stale reference to the last session it
        # served, so empty its state too: that is where the uploader's file lives
        info.session._session_state.clear()
        freed_sessions += 1

    # Uploads whose session is gone some other way (e.g. Streamlit already
    # dropped the expired session from its cache when another one disconnected)
    live = set(session_mgr._active_session_info_by_id)
    live.update(info.session.id for info in session_mgr._session_storage.list())
    for session_id in list(files.file_storage):
        if session_id not in live:
            freed_bytes += _upload_bytes(files, session_id)
            files.remove_session_files(session_id)
            freed_sessions += 1
    return freed_sessions, freed_bytes


async def _sweep_async(runtime) -> tuple[int, int]:
    return _sweep_on_eventloop(runtime)


def sweep() -> tuple[int, int]:
    """Free uploads of dead sessions; return (sessions freed, bytes freed)."""
    from streamlit.runtime import Runtime

    if not Runtime.exists():
        return 0, 0
    runtime = Runtime.instance()
    loop = runtime._get_async_objs().eventloop
    freed = asyncio.run_coroutine_threadsafe(_sweep_async(runtime), loop).result(timeout=60)
    if freed[0]:
        gc.collect()  # sessions hold reference cycles; free them now, not whenever gc runs
    return freed


def _loop() -> None:
    while True:
        time.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            sessions, n_bytes = sweep()
        except Exception as exc:  # Streamlit internals changed: stop, don't crash the app
            print(f"[upload-cleanup] disabled, Streamlit internals changed: {exc!r}", flush=True)
            return
        if sessions:
            print(f"[upload-cleanup] freed {n_bytes / 1024**3:.2f} GB of uploads "
                  f"from {sessions} closed session(s)", flush=True)


def start_upload_cleanup() -> None:
    """Start the sweeper once per server process (safe to call on every rerun)."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name="upload-cleanup", daemon=True).start()
