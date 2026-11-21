
import asyncio
import json
import logging
import sqlite3
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
    get_beneficiary, register_beneficiary, save_visit,
    list_beneficiaries,
    list_visits,
    list_danger_alerts,
    save_danger_alert,
    acknowledge_danger_alert,
)
from .groq_llm import generate_reply, extract_visit
from .schemas import ExtractRequest, ExtractResponse, VisitExtraction
from .session import VisitSession
from .safety import detect_danger_signs
from .gnani_stt import connect_to_prisma


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
    version="0.4.2",
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
        "version": "0.4.2",
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


# REST workflow independent of the voice WebSocket session.
class BeneficiaryRegistration(BaseModel):
    beneficiary_id: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    village: str = Field(min_length=1, max_length=120)


class SaveVisitRequest(BaseModel):
    beneficiary_id: str = Field(min_length=2)
    visit: VisitExtraction
    transcript: str = Field(min_length=1)
    acknowledge_danger: bool = False


@app.get("/api/beneficiaries/{beneficiary_id}")
async def beneficiary_by_id(beneficiary_id: str):
    match = get_beneficiary(beneficiary_id)
    if not match:
        raise HTTPException(status_code=404, detail="Beneficiary not found. Register this ID first.")
    return match


@app.post("/api/beneficiaries/register", status_code=201)
async def create_beneficiary(request: BeneficiaryRegistration):
    beneficiary_id = request.beneficiary_id.strip().upper()
    if get_beneficiary(beneficiary_id):
        raise HTTPException(status_code=409, detail="Beneficiary ID already exists")
    try:
        return register_beneficiary(beneficiary_id, request.name.strip(), request.category.strip(), request.village.strip())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Beneficiary ID already exists")


@app.post("/api/visits/confirm", status_code=201)
async def confirm_visit(request: SaveVisitRequest):
    beneficiary = get_beneficiary(request.beneficiary_id)
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary ID not found")
    if not request.visit.visit_type:
        raise HTTPException(status_code=422, detail="Visit type is required")
    alerts = detect_danger_signs(request.transcript, request.visit.visit_type)
    if alerts and not request.acknowledge_danger:
        raise HTTPException(status_code=409, detail="Urgent referral alert must be acknowledged before saving")
    try:
        visit_id = save_visit(beneficiary["beneficiary_id"], request.visit)
        for alert in alerts:
            alert_id = save_danger_alert(alert["danger_type"], request.transcript, beneficiary["beneficiary_id"])
            if request.acknowledge_danger:
                acknowledge_danger_alert(alert_id)
    except Exception:
        logger.exception("Saving visit failed")
        raise HTTPException(status_code=500, detail="Unable to save visit")
    return {"saved": True, "visit_id": visit_id, "beneficiary_id": beneficiary["beneficiary_id"], "alerts": alerts}


# --------------------------------------------------
# VOICE WEBSOCKET
# --------------------------------------------------

@app.websocket("/ws/voice")
async def voice_session(websocket: WebSocket):
    await websocket.accept()

    # Each WebSocket connection has its own visit draft.
    session = VisitSession()
    prisma_ws = None
    prisma_reader = None
    send_lock = asyncio.Lock()
    browser_disconnected = False

    async def send_event(payload):
        nonlocal browser_disconnected
        if browser_disconnected:
            raise WebSocketDisconnect(code=1006)
        async with send_lock:
            if browser_disconnected:
                raise WebSocketDisconnect(code=1006)
            try:
                await websocket.send_json(payload)
            except (WebSocketDisconnect, RuntimeError) as exc:
                browser_disconnected = True
                raise WebSocketDisconnect(code=1006) from exc

    async def read_prisma(connection):
        try:
            async for raw_event in connection:
                event = json.loads(raw_event)
                if event.get("type") == "transcript" and event.get("is_final", True):
                    text = event.get("text", "").strip()
                    if text:
                        await send_event({"type": "stt_transcript", "text": text, "language": event.get("detected_language_code")})
                elif event.get("type") == "error":
                    await send_event({"type": "session_error", "message": "Prisma transcription error"})
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            logger.info("Browser disconnected while reading Prisma")
        except Exception:
            logger.exception("Prisma reader stopped")
            try:
                await send_event({"type": "session_error", "message": "Gnani connection dropped. Stop and start voice again."})
            except Exception:
                pass


    logger.info("Voice WebSocket client connected")

    await send_event({
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
                audio = message["bytes"]
                if prisma_ws is not None and len(audio) == 1024:
                    if prisma_ws.state.name != "OPEN":
                        prisma_ws = None
                        await send_event({"type": "session_error", "message": "Gnani connection closed. Stop and start voice again."})
                        continue
                    try:
                        await prisma_ws.send(audio)
                    except Exception:
                        logger.exception("Prisma audio forwarding failed")
                        try:
                            await prisma_ws.close()
                        except Exception:
                            pass
                        prisma_ws = None
                        await send_event({"type": "session_error", "message": "Gnani audio connection dropped. Stop and start voice again."})
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
                await send_event({
                    "type": "session_error",
                    "message": "Invalid JSON message",
                })
                continue

            event_type = data.get("type")

            # --------------------------------------
            # PING / PONG
            # --------------------------------------

            if event_type == "ping":
                await send_event({
                    "type": "pong",
                })
                continue

            # --------------------------------------
            # INTERRUPT
            # --------------------------------------
            # This acknowledges an interrupt request.
            # Actual cancellation of ongoing TTS
            # or model generation is not yet wired.

            if event_type == "start_stt":
                if prisma_ws is not None:
                    if prisma_ws.state.name == "OPEN" and prisma_reader is not None and not prisma_reader.done():
                        await send_event({"type": "stt_connected"})
                        continue
                    try:
                        await prisma_ws.close()
                    except Exception:
                        pass
                    prisma_ws = None
                    if prisma_reader is not None:
                        prisma_reader.cancel()
                        await asyncio.gather(prisma_reader, return_exceptions=True)
                        prisma_reader = None
                connection = None
                try:
                    connection = await connect_to_prisma()
                    ready = json.loads(await asyncio.wait_for(connection.recv(), timeout=15))
                    if ready.get("type") != "connected":
                        raise RuntimeError("Prisma did not confirm readiness")
                    prisma_ws = connection
                    prisma_reader = asyncio.create_task(read_prisma(connection))
                    await send_event({"type": "stt_connected"})
                except Exception:
                    logger.exception("Failed to start Prisma")
                    if connection is not None:
                        await connection.close()
                    prisma_ws = None
                    await send_event({"type": "session_error", "message": "Unable to start live transcription"})
                continue

            if event_type == "stop_stt":
                if prisma_ws is not None:
                    try:
                        await prisma_ws.send(json.dumps({"type": "commit"}))
                        await asyncio.sleep(1.5)
                    except Exception:
                        logger.exception("Prisma commit failed")
                    if prisma_reader is not None:
                        prisma_reader.cancel()
                        await asyncio.gather(prisma_reader, return_exceptions=True)
                        prisma_reader = None
                    await prisma_ws.close()
                    prisma_ws = None
                await send_event({"type": "stt_stopped"})
                continue

            if event_type == "interrupt":
                await send_event({
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
                    await send_event({
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
                    await send_event({
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

                    await send_event({
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

                    await send_event({
                        "type": "session_error",
                        "message": (
                            "Unable to acknowledge alert"
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
                await send_event({
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
                await send_event({
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
                await send_event({
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
                    )
                except Exception:
                    logger.exception("Danger alert persistence failed")
                    alert_persistence_failed = True
                    break

                session.pending_alert_ids.add(alert_id)
                await send_event({
                    "type": "danger_sign_detected",
                    "alert_id": alert_id,
                    **danger,
                    "requires_acknowledgement": True,
                })

            if alert_persistence_failed:
                await send_event({
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
                await send_event(result)

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
                        await send_event({
                            "type": "agent_reply",
                            "text": reply_text,
                        })

            except WebSocketDisconnect:
                raise
            except Exception:
                logger.exception(
                    "Voice session processing failed"
                )

                await send_event({
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
        if prisma_reader is not None:
            prisma_reader.cancel()
            await asyncio.gather(prisma_reader, return_exceptions=True)
        if prisma_ws is not None:
            try:
                await prisma_ws.close()
            except Exception:
                logger.debug("Prisma connection already closed", exc_info=True)
        logger.info(
            "Voice WebSocket session ended"
        )
