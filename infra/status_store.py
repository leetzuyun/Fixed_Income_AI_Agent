"""
infra/status_store.py
Lightweight, dependency-free run history/status tracker for the daily
report pipeline, backed by a local SQLite file (stdlib only — nothing new
to pip install).

這支檔案從專案根目錄搬到 infra/ 底下，邏輯完全不變，唯一改動是 DB_PATH：
原本用 os.path.dirname(os.path.abspath(__file__)) 算路徑，是因為這支檔
案本來就放在專案根目錄，算出來剛好就是根目錄。現在檔案搬進 infra/ 子資
料夾，同樣的算法會讓 run_history.db 跑到 infra/run_history.db 去，跟舊
資料庫對不起來。改成從 infra/paths.py 拿 PROJECT_ROOT，資料庫仍然建立在
專案根目錄，跟搬家前的位置一致，既有的 run_history.db 檔案不用搬動。

This exists so a future status/monitoring API has something to query, and
so a manual-trigger endpoint can check "is a run already in progress?"
before starting another one (Outlook COM + a same-day PDF path don't
handle two overlapping runs well).

Usage:
    import infra.status_store as status

    if status.is_run_in_progress():
        ...

To track quota/429 retries, pass run_id into the summarize node and call
status.bump_retry(run_id) inside the "Quota exceeded" / "429" branch.
"""
import sqlite3
import datetime
import os
import contextlib

from infra.paths import PROJECT_ROOT

DB_PATH = os.path.join(PROJECT_ROOT, "run_history.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
    provider TEXT,
    bbg_count INTEGER,
    sinopac_count INTEGER,
    output_path TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0
);
"""


@contextlib.contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def is_run_in_progress() -> bool:
    """True if a run is currently marked 'running'.

    A crashed process (e.g. machine sleep, Outlook COM hang) can leave a
    stale 'running' row behind with no matching finish_run() call. If you
    hit that, either clear it manually or add a staleness check here
    (e.g. treat 'running' rows older than N hours as failed).
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM runs WHERE status = 'running' LIMIT 1"
        ).fetchone()
        return row is not None


def start_run(provider: str = None) -> int:
    """Call at the top of run(). Returns a run_id to pass to finish_run()."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO runs (started_at, status, provider) VALUES (?, 'running', ?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), provider),
        )
        return cursor.lastrowid


def bump_retry(run_id: int):
    """Call each time safe_summarize hits a 429/quota retry."""
    with _connect() as conn:
        conn.execute(
            "UPDATE runs SET retry_count = retry_count + 1 WHERE id = ?",
            (run_id,),
        )


def finish_run(run_id: int, success: bool, output_path: str = None,
               bbg_count: int = None, sinopac_count: int = None,
               error: str = None):
    with _connect() as conn:
        conn.execute(
            """UPDATE runs SET finished_at = ?, status = ?, output_path = ?,
               bbg_count = ?, sinopac_count = ?, error = ? WHERE id = ?""",
            (
                datetime.datetime.now().isoformat(timespec="seconds"),
                "success" if success else "failed",
                output_path, bbg_count, sinopac_count, error, run_id,
            ),
        )


def latest_status() -> dict:
    """Most recent run, regardless of status. Returns None if no runs yet."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def history(limit: int = 10) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
