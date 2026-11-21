
"""Database operations for Gnani audio transcription and ASHA review."""

from .audio_sync_db import connection
from .database import _save_visit, get_connection, match_beneficiary


def init_audio_processing_db():
    """Add transcription and review columns without deleting existing audio."""
    with connection() as db:
        existing = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(offline_audio_jobs)"
            ).fetchall()
        }

        new_columns = {
            "transcript": "TEXT",
            "transcript_language": "TEXT",
            "stt_model": "TEXT",
            "gnani_request_id": "TEXT",
            "transcript_truncated": "INTEGER DEFAULT 0",
            "processing_error": "TEXT",
            "processed_at": "TEXT",
            "reviewed_transcript": "TEXT",
            "reviewed_at": "TEXT",
            "confirmed_visit_id": "INTEGER",
        }

        for column, column_type in new_columns.items():
            if column not in existing:
                db.execute(
                    f"ALTER TABLE offline_audio_jobs "
                    f"ADD COLUMN {column} {column_type}"
                )


def get_job(client_record_id: str):
    """Return transcription status without exposing audio bytes."""
    with connection() as db:
        row = db.execute(
            """
            SELECT
                id,
                client_record_id,
                beneficiary_id,
                status,
                transcript,
                transcript_language,
                stt_model,
                gnani_request_id,
                transcript_truncated,
                processing_error,
                processed_at,
                reviewed_transcript,
                reviewed_at,
                confirmed_visit_id
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    return dict(row) if row else None


def claim_job(client_record_id: str):
    """Prevent two requests from processing the same job."""
    with connection() as db:
        updated = db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'processing',
                processing_error = NULL
            WHERE client_record_id = ?
              AND status IN ('uploaded', 'failed')
            """,
            (client_record_id,),
        )

        if updated.rowcount == 1:
            return "claimed"

        row = db.execute(
            """
            SELECT status
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    return row["status"] if row else "missing"


def get_stored_audio(client_record_id: str):
    """Retrieve audio bytes for transcription."""
    with connection() as db:
        row = db.execute(
            """
            SELECT audio_data, mime_type
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    return dict(row) if row else None


def finish_job(client_record_id: str, result: dict):
    """Save a successful Gnani transcription for ASHA review."""
    with connection() as db:
        db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'awaiting_review',
                transcript = ?,
                transcript_language = ?,
                stt_model = ?,
                gnani_request_id = ?,
                transcript_truncated = ?,
                processing_error = NULL,
                processed_at = CURRENT_TIMESTAMP
            WHERE client_record_id = ?
              AND status = 'processing'
            """,
            (
                result["transcript"],
                result["detected_language"],
                result["model"],
                result["request_id"],
                int(result["truncated"]),
                client_record_id,
            ),
        )


def fail_job(client_record_id: str, message: str):
    """Store a processing failure so it can be retried."""
    with connection() as db:
        db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'failed',
                processing_error = ?
            WHERE client_record_id = ?
              AND status = 'processing'
            """,
            (message[:300], client_record_id),
        )


def confirm_transcript(client_record_id: str, reviewed_transcript: str):
    """
    Confirm an ASHA-reviewed transcript exactly once.

    Only jobs with status 'awaiting_review' can be confirmed.
    The original Gnani transcript remains unchanged.

    Returns:
        'confirmed'         - New confirmation succeeded.
        'already_confirmed' - Previously confirmed; no changes made.
        'already_<status>'   - Job exists but is not awaiting review.
        'missing'           - Job does not exist.
    """
    reviewed_transcript = reviewed_transcript.strip()

    if not reviewed_transcript:
        raise ValueError("Reviewed transcript cannot be empty")

    with connection() as db:
        updated = db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'confirmed',
                reviewed_transcript = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE client_record_id = ?
              AND status = 'awaiting_review'
            """,
            (reviewed_transcript, client_record_id),
        )

        if updated.rowcount == 1:
            return "confirmed"

        row = db.execute(
            """
            SELECT status
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()

    # IMPORTANT:
    # Prefix existing status with "already_" so the API does not
    # mistake an existing confirmed job for a new confirmation.
    return f"already_{row['status']}" if row else "missing"


def save_confirmed_offline_visit(
    client_record_id: str,
    visit,
):
    """Persist a reviewed offline visit once, with its job status atomically."""
    with get_connection() as db:
        job = db.execute(
            """
            SELECT beneficiary_id, status, confirmed_visit_id
            FROM offline_audio_jobs
            WHERE client_record_id = ?
            """,
            (client_record_id,),
        ).fetchone()
        if job is None:
            return {"status": "missing"}

        if job["status"] == "visit_saved" and job["confirmed_visit_id"]:
            return {
                "status": "already_saved",
                "visit_id": job["confirmed_visit_id"],
                "beneficiary_id": job["beneficiary_id"],
            }

        if job["status"] != "confirmed":
            return {"status": f"not_reviewed:{job['status']}"}

        match = match_beneficiary(beneficiary_id=job["beneficiary_id"])
        if match["status"] != "matched":
            return {"status": "beneficiary_not_found"}
        beneficiary_id = match["matches"][0]["beneficiary_id"]

        claimed = db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'saving'
            WHERE client_record_id = ?
              AND status = 'confirmed'
            """,
            (client_record_id,),
        )
        if claimed.rowcount != 1:
            current = db.execute(
                """
                SELECT status, confirmed_visit_id, beneficiary_id
                FROM offline_audio_jobs
                WHERE client_record_id = ?
                """,
                (client_record_id,),
            ).fetchone()
            if current and current["confirmed_visit_id"]:
                return {
                    "status": "already_saved",
                    "visit_id": current["confirmed_visit_id"],
                    "beneficiary_id": current["beneficiary_id"],
                }
            return {
                "status": f"not_reviewed:{current['status'] if current else 'missing'}"
            }

        visit_id = _save_visit(
            db,
            beneficiary_id,
            visit,
            f"offline:{client_record_id}",
        )
        db.execute(
            """
            UPDATE offline_audio_jobs
            SET status = 'visit_saved',
                confirmed_visit_id = ?
            WHERE client_record_id = ?
              AND status = 'saving'
            """,
            (visit_id, client_record_id),
        )

    return {
        "status": "visit_saved",
        "visit_id": visit_id,
        "beneficiary_id": beneficiary_id,
    }
