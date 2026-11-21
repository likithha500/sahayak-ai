
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from .audio_sync_db import get_audio_status, save_audio
from .database import match_beneficiary
from .sync_api import require_sync_key

router = APIRouter(
    prefix="/api/offline-sync",
    tags=["Offline audio synchronization"],
    dependencies=[Depends(require_sync_key)],
)

MAX_AUDIO_BYTES = 10 * 1024 * 1024

ALLOWED_TYPES = {
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/mp4",
    "audio/ogg",
    "audio/ogg;codecs=opus",
}


@router.post("/audio", status_code=201)
async def upload_audio(
    client_record_id: UUID = Form(...),
    beneficiary_id: str = Form(...),
    recorded_at: str = Form(...),
    audio: UploadFile = File(...),
):
    beneficiary_id = beneficiary_id.strip()

    if not beneficiary_id or len(beneficiary_id) > 80:
        raise HTTPException(
            status_code=422,
            detail="Invalid beneficiary ID",
        )

    match = match_beneficiary(beneficiary_id=beneficiary_id)
    if match["status"] != "matched":
        raise HTTPException(
            status_code=422,
            detail=(
                "Beneficiary ID must uniquely match a registered record"
            ),
        )
    beneficiary_id = match["matches"][0]["beneficiary_id"]

    if not recorded_at or len(recorded_at) > 64:
        raise HTTPException(
            status_code=422,
            detail="Invalid recording timestamp",
        )

    mime_type = (
        audio.content_type or ""
    ).lower().strip()

    if mime_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format",
        )

    # Read at most one byte beyond the limit.
    content = await audio.read(MAX_AUDIO_BYTES + 1)

    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio exceeds 10 MB",
        )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="Audio is empty",
        )

    result = save_audio(
        client_record_id=str(client_record_id),
        beneficiary_id=beneficiary_id,
        recorded_at=recorded_at,
        mime_type=mime_type,
        audio_data=content,
    )

    if result is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Record ID already exists with "
                "different audio or metadata"
            ),
        )

    return {
        "client_record_id": result["client_record_id"],
        "server_sync_id": result["id"],
        "status": result["status"],
        "confirmed_visit_id": None,
        "message": (
            "Audio uploaded successfully; "
            "awaiting transcription and review"
        ),
    }


@router.get("/audio/{client_record_id}")
def audio_status(client_record_id: UUID):
    result = get_audio_status(str(client_record_id))

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Audio record not found",
        )

    return {
        "client_record_id": result["client_record_id"],
        "server_sync_id": result["id"],
        "status": result["status"],
        "confirmed_visit_id": None,
    }
