
import asyncio
import json

from websockets.asyncio.client import connect


async def main():
    uri = "ws://127.0.0.1:8000/ws/voice"

    async with connect(uri) as websocket:
        print("Connected to SAHAYAK AI WebSocket")

        # Receive connection confirmation
        welcome = await websocket.recv()
        print("SERVER:", welcome)

        # Send sample ASHA visit transcript
        await websocket.send(json.dumps({
            "type": "transcript_final",
            "text": (
                "Beneficiary ASHA102 Lakshmi, "
                "newborn visit, weight 2.8 kg."
            ),
        }))

        # Receive transcript and Qwen response
        for _ in range(2):
            response = await websocket.recv()
            print("SERVER:", response)


if __name__ == "__main__":
    asyncio.run(main())
