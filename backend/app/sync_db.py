"""Durable, idempotent staging for offline visit drafts (not confirmed visits)."""

import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
DB_PATH = Path(__file__).resolve().parent.parent / "sahayak.db"


def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    return db
@contextmanager
def database_connection():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()

def init_sync_db():
    with database_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_sync_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_record_id TEXT NOT NULL UNIQUE,
                payload_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_offline_sync_status "
            "ON offline_sync_jobs(status)"
        )


def canonical_payload(payload):
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def submit(client_record_id, payload):
    serialized = canonical_payload(payload)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    with database_connection() as db:
        # The UNIQUE constraint prevents duplicate rows even on concurrent retries.
        db.execute(
            """
            INSERT OR IGNORE INTO offline_sync_jobs
                (client_record_id, payload_sha256, payload_json)
            VALUES (?, ?, ?)
            """,
            (str(client_record_id), digest, serialized),
        )

        row = db.execute(
            """
            SELECT id, client_record_id, payload_sha256,
                   status, created_at, updated_at
            FROM offline_sync_jobs
            WHERE client_record_id = ?
            """,
            (str(client_record_id),),
        ).fetchone()

    result = dict(row)

    if result.pop("payload_sha256") != digest:
        return None

    return result


def get_status(client_record_id):
    with database_connection() as db:
        row = db.execute(
            """
            SELECT id, client_record_id, status, created_at, updated_at
            FROM offline_sync_jobs
            WHERE client_record_id = ?
            """,
            (str(client_record_id),),
        ).fetchone()

    return dict(row) if row else None