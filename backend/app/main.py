
import json
import logging
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import (
    initialize_database,
    list_beneficiaries,
    list_visits,
    list_danger_alerts,
    save_danger_alert,
    acknowledge_danger_alert,
    update_referral_status,
    REFERRAL_STATUSES,
)
from .groq_llm import generate_reply, extract_visit
from .schemas import ExtractRequest, ExtractResponse
from .session import VisitSession
from .safety import detect_danger_signs


logger = logging.getLogger(__name__)


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    logger.info("SAHAYAK AI database initialized")
    yield


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="SAHAYAK AI API",
    description="Voice-first ASHA healthcare field assistant",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST SCHEMAS
# --------------------------------------------------

class ChatRequest(BaseModel):
    text: str = Field(min_length=1)


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "sahayak-ai",
        "version": "0.5.0",
    }


# --------------------------------------------------
# GROQ / QWEN CHAT
# --------------------------------------------------

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        reply = await generate_reply(request.text)

        return {
            "reply": reply,
            "source": "groq-qwen",
        }

    except Exception:
        logger.exception("Groq/Qwen chat failed")

        raise HTTPException(
            status_code=502,
            detail="Unable to generate reply",
        )


# --------------------------------------------------
# STRUCTURED VISIT EXTRACTION
# --------------------------------------------------

@app.post(
    "/api/extract",
    response_model=ExtractResponse,
)
async def extract(request: ExtractRequest):
    try:
        visit = await extract_visit(request.text)

        return ExtractResponse(
            visit=visit,
            status="draft",
            saved=False,
        )

    except Exception:
        logger.exception("Visit extraction failed")

        raise HTTPException(
            status_code=502,
            detail="Unable to extract visit",
        )


# --------------------------------------------------
# DATABASE ENDPOINTS
# Development only: authentication required
# before using real beneficiary information.
# --------------------------------------------------

@app.get("/api/beneficiaries")
async def beneficiaries():
    return list_beneficiaries()


@app.get("/api/visits")
async def visits():
    return list_visits()


@app.get("/api/alerts")
async def alerts():
    return list_danger_alerts()


# --------------------------------------------------
# VOICE WEBSOCKET
# --------------------------------------------------

@app.websocket("/ws/voice")
async def voice_session(websocket: WebSocket):
    await websocket.accept()

    # Each WebSocket connection has its own visit draft.
    session = VisitSession()

    logger.info("Voice WebSocket client connected")

    await websocket.send_json({
        "type": "session_connected",
        "message": "SAHAYAK AI backend connected",
    })

    try:
        while True:
            message = await websocket.receive()

            # --------------------------------------
            # HANDLE DISCONNECTION
            # --------------------------------------

            if message["type"] == "websocket.disconnect":
                break

            # --------------------------------------
            # BINARY AUDIO
            # --------------------------------------
            # Gnani audio streaming integration
            # will be connected separately.

            if message.get("bytes") is not None:
                continue

            raw = message.get("text")

            if raw is None:
                continue

            # --------------------------------------
            # PARSE WEBSOCKET JSON
            # --------------------------------------

            try:
                data = json.loads(raw)

                if not isinstance(data, dict):
                    raise ValueError(
                        "Expected a JSON object"
                    )

            except (json.JSONDecodeError, ValueError):
                await websocket.send_json({
                    "type": "session_error",
                    "message": "Invalid JSON message",
                })
                continue

            event_type = data.get("type")

            # --------------------------------------
            # PING / PONG
            # --------------------------------------

            if event_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                })
                continue

            # --------------------------------------
            # INTERRUPT
            # --------------------------------------
            # This acknowledges an interrupt request.
            # Actual cancellation of ongoing TTS
            # or model generation is not yet wired.

            if event_type == "interrupt":
                await websocket.send_json({
                    "type": "agent_interrupted",
                })
                continue

            # --------------------------------------
            # ACKNOWLEDGE URGENT ALERT
            # --------------------------------------

            if event_type == "acknowledge_alert":
                alert_id = data.get("alert_id")

                if (
                    type(alert_id) is not int
                    or alert_id <= 0
                ):
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "A valid alert_id is required"
                        ),
                    })
                    continue

                if (
                    alert_id
                    not in session.pending_alert_ids
                ):
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Alert does not belong "
                            "to this active session"
                        ),
                    })
                    continue

                try:
                    acknowledged = (
                        acknowledge_danger_alert(
                            alert_id
                        )
                    )

                    if acknowledged:
                        session.pending_alert_ids.discard(
                            alert_id
                        )

                    await websocket.send_json({
                        "type": (
                            "danger_alert_acknowledged"
                        ),
                        "alert_id": alert_id,
                        "acknowledged": acknowledged,
                    })

                except Exception:
                    logger.exception(
                        "Alert acknowledgement failed"
                    )

                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Unable to acknowledge alert"
                        ),
                    })

                continue

            # --------------------------------------
            # REFERRAL STATUS (not an acknowledgement)
            # --------------------------------------
            if event_type == "update_referral_status":
                alert_id = data.get("alert_id")
                status = data.get("status")
                if type(alert_id) is not int or alert_id <= 0 or status not in REFERRAL_STATUSES:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Valid alert_id and referral status required",
                    })
                    continue
                # Restrict changes to alerts raised in this active session.
                if alert_id not in session.alert_ids:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Alert does not belong to this active session",
                    })
                    continue
                try:
                    updated = update_referral_status(alert_id, status)
                    await websocket.send_json({
                        "type": "referral_status_updated",
                        "alert_id": alert_id,
                        "status": status,
                        "updated": updated,
                    })
                except Exception:
                    logger.exception("Referral status update failed")
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Unable to update referral status",
                    })
                continue

            # --------------------------------------
            # VALIDATE TRANSCRIPT EVENT
            # --------------------------------------

            if event_type not in {
                "transcript_final",
                "extract_visit",
            }:
                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        f"Unsupported event: "
                        f"{event_type}"
                    ),
                })
                continue

            transcript = data.get("text")

            if (
                not isinstance(transcript, str)
                or not transcript.strip()
            ):
                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        "Transcript cannot be empty"
                    ),
                })
                continue

            transcript = transcript.strip()

            # --------------------------------------
            # ECHO FINAL TRANSCRIPT
            # --------------------------------------

            if event_type == "transcript_final":
                await websocket.send_json({
                    "type": "transcript_final",
                    "text": transcript,
                })

            # --------------------------------------
            # INDEPENDENT DANGER-SIGN CHECK
            # --------------------------------------
            # Safety detection runs BEFORE Qwen.

            context = (
                session.draft.visit_type
                or (
                    session.beneficiary["category"]
                    if session.beneficiary
                    else None
                )
            )

            danger_signs = detect_danger_signs(
                transcript,
                context,
            )

            alert_persistence_failed = False

            for danger in danger_signs:
                try:
                    alert_id = save_danger_alert(
                        danger["danger_type"],
                        transcript,
                        (
                            session.beneficiary["beneficiary_id"]
                            if session.beneficiary
                            else None
                        ),
                        severity=danger["severity"],
                        matched_sign=danger["matched_sign"],
                        guideline_document=danger["guideline_document"],
                        guideline_page=danger["guideline_page"],
                        recommended_action=danger["recommended_action"],
                    )
                except Exception:
                    logger.exception("Danger alert persistence failed")
                    alert_persistence_failed = True
                    break

                session.pending_alert_ids.add(alert_id)
                session.alert_ids.add(alert_id)
                await websocket.send_json({
                    "type": "danger_sign_detected",
                    "alert_id": alert_id,
                    **danger,
                    "requires_acknowledgement": True,
                })

            if alert_persistence_failed:
                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        "Urgent safety alert could not be recorded. "
                        "Visit processing was stopped; please retry."
                    ),
                })
                # Continue the OUTER WebSocket receive loop, not
                # the inner danger-sign loop. No process_turn call.
                continue

            # --------------------------------------
            # PROCESS MULTI-TURN CONVERSATION
            # --------------------------------------

            try:
                result = await session.process_turn(
                    transcript
                )

                # Send the actual structured result.
                await websocket.send_json(result)

                # ----------------------------------
                # FIX: NO DUPLICATE AGENT REPLIES
                # ----------------------------------
                # If the session already returned
                # agent_reply, do not send it again.

                if result["type"] != "agent_reply":
                    reply_text = (
                        result.get("message")
                        or result.get("text")
                    )

                    if reply_text:
                        await websocket.send_json({
                            "type": "agent_reply",
                            "text": reply_text,
                        })

            except Exception:
                logger.exception(
                    "Voice session processing failed"
                )

                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        "Unable to process visit"
                    ),
                })

    except WebSocketDisconnect:
        logger.info(
            "Voice WebSocket client disconnected"
        )

    except Exception:
        logger.exception(
            "Unexpected WebSocket failure"
        )

    finally:
        logger.info(
            "Voice WebSocket session ended"
        )
