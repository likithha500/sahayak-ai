
import os

import websockets
from dotenv import load_dotenv

load_dotenv()

GNANI_STT_URL = "wss://api.vachana.ai/stt/v3/stream"


async def connect_to_prisma():
    """Connect to Gnani Prisma v3.0 for real-time STT."""

    api_key = os.getenv("GNANI_API_KEY")

    if not api_key:
        raise RuntimeError("GNANI_API_KEY is missing")

    headers = {
        "x-api-key-id": api_key,
        "model": "prisma-v3.0",
        "language_code": "indic-auto",
        "format": "codemix",
        "x-sample-rate": "16000",
        "x-idle-timeout-sec": "120",
    }

    return await websockets.connect(
        GNANI_STT_URL,
        additional_headers=headers,
        open_timeout=30,
        ping_interval=None,  # Gnani streaming endpoint may not answer client WebSocket pings
    )
