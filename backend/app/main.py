from .audio_processing_db import init_audio_processing_db
from .audio_processing_api import router as audio_processing_router
import json
import logging
from contextlib import asynccontextmanager
import asyncio
import base64

from .gnani_client import transcribe_audio, GnaniError
from .gnani_tts import synthesize_speech

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import (
    initialize_database,
    list_beneficiaries,
    list_visits,
    list_danger_alerts,
    get_beneficiary,
    get_beneficiary_visits,
    get_visit,
    list_follow_ups,
    update_follow_up,
    dashboard_data,
    save_danger_alert,
    acknowledge_danger_alert,
    update_referral_status,
    REFERRAL_STATUSES,
)
from .groq_llm import generate_reply, extract_visit
from .schemas import (
    ExtractRequest,
    ExtractResponse,
    FollowUpUpdate,
    ReferralStatusUpdate,
)
from .session import VisitSession
from .safety import detect_danger_signs

# Phase 3: JSON draft synchronization
from .sync_api import router as offline_sync_router
from .sync_db import init_sync_db

# Phase 3: Audio synchronization
from .audio_sync_api import router as audio_sync_router
from .audio_sync_db import init_audio_sync_db


logger = logging.getLogger(__name__)


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    init_sync_db()
    init_audio_sync_db()
    init_audio_processing_db()

    logger.info("SAHAYAK AI database initialized")
    yield


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="SAHAYAK AI API",
    description="Voice-first ASHA healthcare field assistant",
    version="0.7.0",
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

# Register offline synchronization endpoints
app.include_router(offline_sync_router)
app.include_router(audio_sync_router)
app.include_router(audio_processing_router)


# ==================================================
# REQUEST SCHEMAS
# ==================================================

class ChatRequest(BaseModel):
    text: str = Field(min_length=1)


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "sahayak-ai",
        "version": "0.7.0",
    }


# ==================================================
# GROQ / QWEN CHAT
# ==================================================

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


# ==================================================
# STRUCTURED VISIT EXTRACTION
# ==================================================

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


# ==================================================
# DATABASE ENDPOINTS
# Development only: authentication is required
# before processing real beneficiary information.
# ==================================================

@app.get("/api/beneficiaries")
async def beneficiaries():
    return list_beneficiaries()


@app.get("/api/beneficiaries/{beneficiary_id}")
async def beneficiary_detail(beneficiary_id: str):
    beneficiary = get_beneficiary(beneficiary_id)
    if beneficiary is None:
        raise HTTPException(
            status_code=404,
            detail="Beneficiary not found",
        )
    return beneficiary


@app.get("/api/beneficiaries/{beneficiary_id}/visits")
async def beneficiary_visits(beneficiary_id: str):
    result = get_beneficiary_visits(beneficiary_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Beneficiary not found",
        )
    return result


@app.get("/api/visits")
async def visits():
    return list_visits()


@app.get("/api/visits/{visit_id}")
async def visit_detail(visit_id: int):
    visit = get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@app.get("/api/follow-ups")
async def follow_ups():
    return list_follow_ups()


@app.patch("/api/follow-ups/{follow_up_id}")
async def follow_up_update(
    follow_up_id: int,
    update: FollowUpUpdate,
):
    try:
        updated = update_follow_up(
            follow_up_id,
            scheduled_date=(
                update.scheduled_date.isoformat()
                if update.scheduled_date else None
            ),
            status=update.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Follow-up not found",
        )
    return next(
        row for row in list_follow_ups()
        if row["id"] == follow_up_id
    )


@app.get("/api/dashboard")
async def dashboard():
    return dashboard_data()


@app.get("/api/statistics")
async def statistics():
    return dashboard_data()["stats"]


@app.get("/api/alerts")
async def alerts():
    return list_danger_alerts()


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    if not acknowledge_danger_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return next(
        alert for alert in list_danger_alerts()
        if alert["id"] == alert_id
    )


@app.patch("/api/alerts/{alert_id}/referral-status")
async def set_alert_referral_status(
    alert_id: int,
    update: ReferralStatusUpdate,
):
    if not update_referral_status(alert_id, update.status):
        raise HTTPException(status_code=404, detail="Alert not found")
    return next(
        alert for alert in list_danger_alerts()
        if alert["id"] == alert_id
    )


# ==================================================
# VOICE WEBSOCKET
# ==================================================

async def send_spoken_reply(
    websocket: WebSocket,
    text: str,
    language: str = "auto",
):
    if not text.strip():
        return

    await websocket.send_json({
        "type": "spoken_reply",
        "text": text,
    })

    await websocket.send_json({
        "type": "agent_speaking_started",
        "text": text,
    })

    try:
        audio = await asyncio.to_thread(
            synthesize_speech,
            text,
            language,
        )

        await websocket.send_json({
            "type": "agent_audio",
            "audio": base64.b64encode(audio).decode("ascii"),
            "mime_type": "audio/wav",
        })

        await websocket.send_json({
            "type": "agent_speaking_finished",
        })

    except WebSocketDisconnect:
        raise

    except Exception as exc:
        logger.warning(
            "Gnani TTS failed; keeping voice session open (error_type=%s)",
            type(exc).__name__,
        )
        await websocket.send_json({
            "type": "session_error",
            "message": (
                "Voice playback is temporarily unavailable. "
                "You can continue by speaking."
            ),
            "recoverable": True,
        })



@app.websocket("/ws/voice")
async def voice_session(websocket: WebSocket):
    await websocket.accept()

    # Each WebSocket connection gets its own visit session.
    session = VisitSession()
    logger.info("Voice WebSocket client connected")

    await websocket.send_json({
        "type": "session_connected",
        "message": "SAHAYAK AI backend connected",
        "session_id": session.session_id,
    })

    try:
        while True:
            message = await websocket.receive()

            # --------------------------------------
            # DISCONNECTION
            # --------------------------------------

            if message["type"] == "websocket.disconnect":
                break

            # --------------------------------------
            # BINARY AUDIO
            # --------------------------------------
            # Gnani audio streaming will be
            # connected separately.

            if message.get("bytes") is not None:
                audio_data = message["bytes"]

                if not audio_data or len(audio_data) > 10 * 1024 * 1024:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Invalid audio size",
                    })
                    continue

                try:
                    stt_result = await asyncio.to_thread(
                        transcribe_audio,
                        audio_data,
                        (
                            session.language
                            if session.language in {"kn-IN", "hi-IN", "en-IN"}
                            else "kn-IN,en-IN,hi-IN"
                        ),
                    )

                    transcript = stt_result["transcript"].strip()

                    if not transcript:
                        await websocket.send_json({
                            "type": "session_error",
                            "message": "No speech detected. Please try again.",
                            "recoverable": True,
                        })
                        continue

                    raw = json.dumps({
                        "type": "transcript_final",
                        "text": transcript,
                        "language": stt_result.get("detected_language"),
                    })

                except GnaniError as exc:
                    logger.warning(
                        "Gnani STT failed; keeping voice session open "
                        "(reason=%s)",
                        str(exc),
                    )
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Speech recognition is temporarily "
                            "unavailable. Please try again."
                        ),
                        "recoverable": True,
                    })
                    continue

            else:
                raw = message.get("text")


            if raw is None:
                continue

            # --------------------------------------
            # PARSE JSON
            # --------------------------------------

            try:
                data = json.loads(raw)

                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")

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

            # SESSION CONTEXT
            if event_type == "start_session":
                session.language = {
                    "kn": "kn-IN",
                    "hi": "hi-IN",
                    "en": "en-IN",
                }.get(data.get("language"), session.language)

                beneficiary_id = data.get("beneficiary_id")
                if beneficiary_id:
                    session.set_initial_beneficiary(str(beneficiary_id))

                greeting = {
                    "kn-IN": "ನಮಸ್ಕಾರ! ನಾನು SAHAYAK, ನಿಮ್ಮ ಕ್ಷೇತ್ರ-ಭೇಟಿ ಸಹಾಯಕ. ಇಂದು ಯಾರನ್ನು ಭೇಟಿಮಾಡುತ್ತಿದ್ದೀರಿ?",
                    "hi-IN": "नमस्ते! मैं SAHAYAK हूँ, आपका फील्ड-विज़िट सहायक। आज आप किस लाभार्थी से मिल रहे हैं?",
                    "en-IN": "Hello! I'm SAHAYAK, your field-visit assistant. Whom are you visiting today?",
                }[session.language]

                if session.beneficiary:
                    draft_event = session.next_question()
                    greeting = draft_event["message"]
                    await websocket.send_json(draft_event)

                await websocket.send_json({
                    "type": "session_started",
                    "session_id": session.session_id,
                    "language": session.language,
                    "beneficiary": session.beneficiary,
                })
                await send_spoken_reply(
                    websocket,
                    greeting,
                    session.language,
                )
                continue

            # --------------------------------------
            # INTERRUPT
            # --------------------------------------
            # Acknowledges the interrupt request.
            # Actual TTS/model cancellation is not
            # yet implemented.

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

                if type(alert_id) is not int or alert_id <= 0:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "A valid alert_id is required",
                    })
                    continue

                if alert_id not in session.pending_alert_ids:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Alert does not belong "
                            "to this active session"
                        ),
                    })
                    continue

                try:
                    acknowledged = acknowledge_danger_alert(
                        alert_id
                    )

                    if acknowledged:
                        session.pending_alert_ids.discard(
                            alert_id
                        )

                    await websocket.send_json({
                        "type": "danger_alert_acknowledged",
                        "alert_id": alert_id,
                        "acknowledged": acknowledged,
                    })

                except Exception:
                    logger.exception(
                        "Alert acknowledgement failed"
                    )

                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Unable to acknowledge alert",
                    })

                continue

            # --------------------------------------
            # UPDATE REFERRAL STATUS
            # --------------------------------------
            # Referral status and alert
            # acknowledgement are separate actions.

            if event_type == "update_referral_status":
                alert_id = data.get("alert_id")
                status = data.get("status")

                if (
                    type(alert_id) is not int
                    or alert_id <= 0
                    or status not in REFERRAL_STATUSES
                ):
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Valid alert_id and referral "
                            "status required"
                        ),
                    })
                    continue

                if alert_id not in session.alert_ids:
                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Alert does not belong "
                            "to this active session"
                        ),
                    })
                    continue

                try:
                    updated = update_referral_status(
                        alert_id,
                        status,
                    )

                    await websocket.send_json({
                        "type": "referral_status_updated",
                        "alert_id": alert_id,
                        "status": status,
                        "updated": updated,
                    })

                except Exception:
                    logger.exception(
                        "Referral status update failed"
                    )

                    await websocket.send_json({
                        "type": "session_error",
                        "message": (
                            "Unable to update referral status"
                        ),
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
                        f"Unsupported event: {event_type}"
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
                    "message": "Transcript cannot be empty",
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
                    "turn_id": data.get("turn_id"),
                    "session_id": session.session_id,
                })

            # --------------------------------------
            # INDEPENDENT SAFETY DETECTION
            # --------------------------------------
            # Safety rules run BEFORE Qwen.

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
                        guideline_document=danger[
                            "guideline_document"
                        ],
                        guideline_page=danger[
                            "guideline_page"
                        ],
                        recommended_action=danger[
                            "recommended_action"
                        ],
                    )

                except Exception:
                    logger.exception(
                        "Danger alert persistence failed"
                    )
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

            # Stop processing if an urgent alert
            # could not be saved to the database.

            if alert_persistence_failed:
                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        "Urgent safety alert could not "
                        "be recorded. Visit processing "
                        "was stopped; please retry."
                    ),
                })
                continue

            # --------------------------------------
            # PROCESS MULTI-TURN CONVERSATION
            # --------------------------------------

            try:
                result = await session.process_turn(
                    transcript
                )

                await websocket.send_json(result)

                backend_reply = (
                    result.get("message")
                    or result.get("text")
                    or ""
                )

                reply = (
                    danger_signs[0]["recommended_action"]
                    if danger_signs
                    else backend_reply
                )

                await send_spoken_reply(
                    websocket,
                    reply,
                    session.language,
                )

            except WebSocketDisconnect:
                raise

            except Exception as exc:
                logger.warning(
                    "Voice turn failed; preserving session "
                    "(error_type=%s)",
                    type(exc).__name__,
                )

                await websocket.send_json({
                    "type": "session_error",
                    "message": (
                        "I couldn't process that response. "
                        "Your current draft is preserved; "
                        "please try again."
                    ),
                    "recoverable": True,
                })

    except WebSocketDisconnect:
        logger.info(
            "Voice WebSocket client disconnected"
        )

    except Exception as exc:
        logger.error(
            "Unexpected WebSocket failure (error_type=%s)",
            type(exc).__name__,
        )

    finally:
        logger.info(
            "Voice WebSocket session ended"
        )
