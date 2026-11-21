
"""API endpoints for real Gnani audio transcription."""

import logging
import shutil
import subprocess
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool

from .audio_processing_db import (
    claim_job,
    confirm_transcript,
    fail_job,
    finish_job,
    get_job,
    get_stored_audio,
    save_confirmed_offline_visit,
)
from .database import match_beneficiary
from .gnani_client import GnaniError, transcribe_audio
from .groq_llm import extract_visit
from .schemas import VisitExtraction
from .sync_api import require_sync_key


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/offline-sync/audio",
    tags=["Gnani audio processing"],
    dependencies=[Depends(require_sync_key)],
)


def public_result(job: dict) -> dict:
    """
    Return transcription and review metadata.

    Never expose raw audio or API credentials.
    """
    return {
        "client_record_id": job["client_record_id"],
        "beneficiary_id": job.get("beneficiary_id"),
        "server_sync_id": job["id"],
        "status": job["status"],
        "transcript": job.get("transcript"),
        "transcript_language": job.get("transcript_language"),
        "stt_model": job.get("stt_model"),
        "transcript_truncated": bool(
            job.get("transcript_truncated")
        ),
        "reviewed_transcript": job.get("reviewed_transcript"),
        "reviewed_at": job.get("reviewed_at"),
        "confirmed_visit_id": job.get("confirmed_visit_id"),
        "visit_saved": job["status"] == "visit_saved",
    }


def check_duration(audio_data: bytes) -> None:
    """
    Validate actual decoded audio duration.

    Browser-generated WebM/Opus files may not contain
    duration metadata.

    Decode to raw PCM and count samples instead.

    Reject recordings longer than 30 seconds before
    calling Gnani.
    """
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg is None:
        raise GnaniError("FFmpeg is not installed")

    if not audio_data:
        raise GnaniError("Recording is empty")

    # Mono, 16-bit PCM, 16,000 samples per second.
    sample_rate = 16000
    bytes_per_second = sample_rate * 2
    max_audio_bytes = 30 * bytes_per_second

    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                "pipe:0",
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-f",
                "s16le",
                "pipe:1",
            ],
            input=audio_data,
            capture_output=True,
            timeout=20,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise GnaniError(
            "Audio duration check timed out"
        ) from exc

    except OSError as exc:
        raise GnaniError(
            "Could not run FFmpeg"
        ) from exc

    if result.returncode != 0:
        raise GnaniError(
            "Could not decode recording"
        )

    decoded_bytes = len(result.stdout)

    if decoded_bytes == 0:
        raise GnaniError(
            "Recording contains no decodable audio"
        )

    if decoded_bytes > max_audio_bytes:
        raise GnaniError(
            "Recording must be between 0 and 30 seconds"
        )

    duration = decoded_bytes / bytes_per_second

    logger.info(
        "Validated audio duration: %.2f seconds",
        duration,
    )


@router.post("/{client_record_id}/process")
async def process_audio(
    client_record_id: UUID,
    language_codes: str = "kn-IN,en-IN,hi-IN",
):
    """Process uploaded audio using real Gnani Prisma v3.0."""
    record_id = str(client_record_id)

    existing = await run_in_threadpool(
        get_job,
        record_id,
    )

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )

    # Do not call Gnani again for an existing transcript.
    if existing["status"] == "awaiting_review":
        return public_result(existing)

    if existing["status"] == "processing":
        raise HTTPException(
            status_code=409,
            detail="Audio is already processing",
        )

    if existing["status"] not in ("uploaded", "failed"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Audio cannot be processed "
                "in its current state"
            ),
        )

    state = await run_in_threadpool(
        claim_job,
        record_id,
    )

    if state != "claimed":
        raise HTTPException(
            status_code=409,
            detail=f"Audio processing unavailable: {state}",
        )

    try:
        stored = await run_in_threadpool(
            get_stored_audio,
            record_id,
        )

        if stored is None:
            raise GnaniError(
                "Stored audio is missing"
            )

        await run_in_threadpool(
            check_duration,
            stored["audio_data"],
        )

        result = await run_in_threadpool(
            transcribe_audio,
            stored["audio_data"],
            language_codes,
        )

        if not result["transcript"].strip():
            raise GnaniError(
                "No speech detected; recording needs review"
            )

        if result["truncated"]:
            raise GnaniError(
                "Gnani truncated the recording; "
                "use a shorter clip"
            )

        await run_in_threadpool(
            finish_job,
            record_id,
            result,
        )

    except GnaniError as exc:
        await run_in_threadpool(
            fail_job,
            record_id,
            str(exc),
        )

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected transcription failure for %s",
            record_id,
        )

        await run_in_threadpool(
            fail_job,
            record_id,
            "Unexpected transcription failure",
        )

        raise HTTPException(
            status_code=502,
            detail="Transcription service failed",
        ) from exc

    job = await run_in_threadpool(
        get_job,
        record_id,
    )

    return public_result(job)


@router.get("/{client_record_id}/processing")
async def processing_status(client_record_id: UUID):
    """
    Return transcription and review status.

    Includes:
    - Original Gnani transcript
    - ASHA-reviewed transcript
    - Review timestamp
    - Confirmed visit ID, if linked
    """
    job = await run_in_threadpool(
        get_job,
        str(client_record_id),
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )

    return public_result(job)


class TranscriptConfirmation(BaseModel):
    reviewed_transcript: str = Field(
        min_length=1,
        max_length=10000,
    )


@router.post("/{client_record_id}/confirm")
async def confirm_audio_transcript(
    client_record_id: UUID,
    payload: TranscriptConfirmation,
):
    """
    Confirm an ASHA-reviewed transcript exactly once.

    Duplicate confirmations return HTTP 409.
    Original Gnani transcript remains unchanged.
    """
    record_id = str(client_record_id)

    reviewed_text = payload.reviewed_transcript.strip()

    if not reviewed_text:
        raise HTTPException(
            status_code=422,
            detail="Reviewed transcript cannot be empty",
        )

    result = await run_in_threadpool(
        confirm_transcript,
        record_id,
        reviewed_text,
    )

    if result == "missing":
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )

    if result != "confirmed":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot confirm transcript "
                f"with status: {result}"
            ),
        )

    job = await run_in_threadpool(
        get_job,
        record_id,
    )

    return public_result(job)


@router.post("/{client_record_id}/extract")
async def extract_offline_visit(client_record_id: UUID):
    """Extract a structured draft from the reviewed Gnani transcript."""
    job = await run_in_threadpool(get_job, str(client_record_id))
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )
    if job["status"] != "confirmed" or not job.get("reviewed_transcript"):
        raise HTTPException(
            status_code=409,
            detail="Review and confirm the transcript before extracting a visit",
        )

    match = await run_in_threadpool(
        match_beneficiary,
        beneficiary_id=job["beneficiary_id"],
    )
    if match["status"] != "matched":
        raise HTTPException(
            status_code=422,
            detail="The registered beneficiary could not be verified",
        )

    try:
        visit = await extract_visit(job["reviewed_transcript"])
    except Exception as exc:
        logger.exception(
            "Offline visit extraction failed (record_id=%s)",
            str(client_record_id),
        )
        raise HTTPException(
            status_code=502,
            detail="Could not extract a visit draft",
        ) from exc

    visit = visit.model_copy(update={
        "beneficiary_id": match["matches"][0]["beneficiary_id"],
        "beneficiary_name": match["matches"][0]["name"],
    })
    return {
        "visit": visit.model_dump(mode="json"),
        "beneficiary": match["matches"][0],
        "saved": False,
    }


class OfflineVisitConfirmation(BaseModel):
    confirmed: Literal[True]
    visit: VisitExtraction

    @model_validator(mode="after")
    def require_visit_type(self):
        if self.visit.visit_type is None:
            raise ValueError("A visit type is required before saving")
        return self


@router.post("/{client_record_id}/confirm-visit")
async def confirm_offline_visit(
    client_record_id: UUID,
    payload: OfflineVisitConfirmation,
):
    """Save only a reviewed, explicitly confirmed offline visit draft."""
    job = await run_in_threadpool(get_job, str(client_record_id))
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )
    if job["status"] != "confirmed" or not job.get("reviewed_transcript"):
        if job.get("confirmed_visit_id"):
            return {
                **public_result(job),
                "visit_id": job["confirmed_visit_id"],
                "saved": True,
            }
        raise HTTPException(
            status_code=409,
            detail="Review and confirm the transcript before saving",
        )

    try:
        result = await run_in_threadpool(
            save_confirmed_offline_visit,
            str(client_record_id),
            payload.visit,
        )
    except Exception as exc:
        logger.exception(
            "Offline visit save failed (record_id=%s)",
            str(client_record_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Visit was not saved; the reviewed draft is preserved",
        ) from exc

    if result["status"] == "missing":
        raise HTTPException(status_code=404, detail="Audio record not found")
    if result["status"] == "beneficiary_not_found":
        raise HTTPException(
            status_code=422,
            detail="The registered beneficiary could not be verified",
        )
    if result["status"].startswith("not_reviewed:"):
        raise HTTPException(
            status_code=409,
            detail="Review and confirm the transcript before saving",
        )

    saved_job = await run_in_threadpool(get_job, str(client_record_id))
    return {
        **public_result(saved_job),
        "visit_id": result["visit_id"],
        "saved": True,
    }
