
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .groq_llm import generate_reply


# --------------------------------------------------
# Application setup
# --------------------------------------------------

app = FastAPI(
    title="SAHAYAK AI API",
    description="Voice-first ASHA healthcare field assistant",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class ChatRequest(BaseModel):
    text: str = Field(min_length=1)


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "sahayak-ai",
        "version": "0.2.0",
    }


# --------------------------------------------------
# REST endpoint (for development testing)
# --------------------------------------------------

@app.post("/api/chat")
async def chat(request: ChatRequest):
    reply = await generate_reply(request.text)

    return {
        "reply": reply,
        "source": "groq-qwen",
    }


# --------------------------------------------------
# WebSocket endpoint (frontend <-> backend)
# --------------------------------------------------

@app.websocket("/ws/voice")
async def voice_session(websocket: WebSocket):
    await websocket.accept()

    logger.info("Voice WebSocket client connected")

    await websocket.send_json({
        "type": "session_connected",
        "message": "SAHAYAK AI backend connected",
    })

    try:
        while True:
            message = await websocket.receive()

            # Handle disconnected client
            if message["type"] == "websocket.disconnect":
                break

            # Audio frames will be processed by Gnani later.
            if message.get("bytes") is not None:
                continue

            raw_text = message.get("text")

            if raw_text is None:
                continue

            # Parse frontend JSON messages
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "session_error",
                    "message": "Invalid JSON message",
                })
                continue

            if not isinstance(data, dict):
                await websocket.send_json({
                    "type": "session_error",
                    "message": "Expected a JSON object",
                })
                continue

            event_type = data.get("type")

            # --------------------------------------
            # Final speech transcript -> Groq/Qwen
            # --------------------------------------

            if event_type == "transcript_final":
                transcript = data.get("text")

                if not isinstance(transcript, str) or not transcript.strip():
                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Transcript cannot be empty",
                    })
                    continue

                transcript = transcript.strip()

                await websocket.send_json({
                    "type": "transcript_final",
                    "text": transcript,
                })

                try:
                    reply = await generate_reply(transcript)

                    await websocket.send_json({
                        "type": "agent_reply",
                        "text": reply,
                    })

                except Exception:
                    logger.exception("Groq/Qwen request failed")

                    await websocket.send_json({
                        "type": "session_error",
                        "message": "Unable to generate a reply",
                    })

            # --------------------------------------
            # Interrupt acknowledgement (temporary)
            # --------------------------------------

            elif event_type == "interrupt":
                await websocket.send_json({
                    "type": "agent_interrupted",
                })

            # --------------------------------------
            # Ping/pong for connection testing
            # --------------------------------------

            elif event_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                })

            # --------------------------------------
            # Unknown event
            # --------------------------------------

            else:
                await websocket.send_json({
                    "type": "session_error",
                    "message": f"Unsupported event: {event_type}",
                })

    except WebSocketDisconnect:
        logger.info("Voice WebSocket client disconnected")

    except Exception:
        logger.exception("Unexpected voice WebSocket error")

    finally:
        logger.info("Voice WebSocket session ended")
