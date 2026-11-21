
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SAHAYAK AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sahayak-ai"}

@app.websocket("/ws/voice")
async def voice_session(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "type": "session_connected",
        "message": "SAHAYAK AI backend connected"
    })

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if message.get("text") is not None:
                await websocket.send_json({
                    "type": "debug_echo",
                    "message": message["text"]
                })

    except WebSocketDisconnect:
        pass
