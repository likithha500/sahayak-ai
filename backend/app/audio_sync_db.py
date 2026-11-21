
import hashlib
import sqlite3
from contextlib import contextmanager

from . import sync_db


@contextmanager
def connection():
    db = sync_db.connect()
    try:
        with db:
            yield db
    finally:
        db.close()


def init_audio_sync_db():
    with connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS offline_audio_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_record_id TEXT NOT NULL UNIQUE,
                beneficiary_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                audio_sha256 TEXT NOT NULL,
                audio_data BLOB NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_audio(
    client_record_id: str,
    beneficiary_id: str,
    recorded_at: str,
    mime_type: str,
    audio_data: bytes,
):
    digest = hashlib.sha256(audio_data).hexdigest()

    with connection() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO offline_audio_jobs
            (
                client_record_id,
                beneficiary_id,
                recorded_at,
                mime_type,
                audio_sha256,
                audio_data
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client_record_id,
                beneficiary_id,
                recorded_at,
                mime_type,
                digest,
                audio_data,
            ),
        )

        row = db.execute(
            """
            SELECT id, client_record_id, beneficiary_id,
                   recorded_at, mime_type, audio_sha256, status
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    result = dict(row)

    if (
        result["audio_sha256"] != digest
        or result["beneficiary_id"] != beneficiary_id
        or result["recorded_at"] != recorded_at
        or result["mime_type"] != mime_type
    ):
        return None

    return result


def get_audio_status(client_record_id: str):
    with connection() as db:
        row = db.execute(
            """
            SELECT id, client_record_id, status, created_at
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    return dict(row) if row else None
