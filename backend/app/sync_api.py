"""Offline draft upload API. Requires an explicit prototype API key."""

import hmac
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .sync_db import get_status, submit

router = APIRouter(
    prefix="/api/offline-sync",
    tags=["Offline synchronization"],
)


def require_sync_key(
    x_sync_api_key: str | None = Header(default=None),
):
    expected = os.environ.get("SAHAYAK_SYNC_API_KEY", "")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Offline sync API key is not configured",
        )

    if not x_sync_api_key or not hmac.compare_digest(
        x_sync_api_key, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid sync API key",
        )


class OfflineDraft(BaseModel):
    client_record_id: UUID
    beneficiary_id: str | None = Field(
        default=None,
        max_length=80,
    )
    transcript: str | None = Field(
        default=None,
        max_length=20000,
    )
    visit_draft: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str | None = Field(
        default=None,
        max_length=64,
    )


@router.post(
    "/records",
    status_code=201,
    dependencies=[Depends(require_sync_key)],
)
def upload_offline_draft(record: OfflineDraft):
    # Uploading a draft does NOT create a confirmed health visit.
    # AI processing, safety review, and ASHA confirmation come later.

    payload = record.model_dump(
        mode="json",
        exclude={"client_record_id"},
    )

    if len(str(payload).encode("utf-8")) > 100_000:
        raise HTTPException(
            status_code=413,
            detail="Draft too large",
        )

    result = submit(record.client_record_id, payload)

    if result is None:
        raise HTTPException(
            status_code=409,
            detail="Client record ID already exists with different data",
        )

    return {
        "client_record_id": result["client_record_id"],
        "server_sync_id": result["id"],
        "status": result["status"],
        "confirmed_visit_id": None,
        "message": "Draft uploaded; not yet processed or confirmed",
    }


@router.get(
    "/records/{client_record_id}",
    dependencies=[Depends(require_sync_key)],
)
def offline_draft_status(client_record_id: UUID):
    result = get_status(client_record_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Offline draft not found",
        )

    return {
        "client_record_id": result["client_record_id"],
        "server_sync_id": result["id"],
        "status": result["status"],
        "confirmed_visit_id": None,
    }