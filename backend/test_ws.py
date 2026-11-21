
import asyncio
import json

from websockets.asyncio.client import connect


async def main():
    uri = "ws://127.0.0.1:8000/ws/voice"

    async with connect(uri) as websocket:
        print("Connected to SAHAYAK AI WebSocket")

        welcome = await websocket.recv()
        print("SERVER:", welcome)

        await websocket.send(json.dumps({
            "type": "extract_visit",
            "text": (
                "Beneficiary ASHA102 Lakshmi, "
                "newborn visit, weight 2.8 kg."
            ),
        }))

        response = await websocket.recv()
        print("SERVER:", response)

        data = json.loads(response)

        if data.get("type") == "visit_draft":
            print("\nStructured extraction successful!")
            print(json.dumps(data["visit"], indent=2))
            print("Saved:", data["saved"])
        else:
            print("\nExtraction failed; check backend logs.")


if __name__ == "__main__":
    asyncio.run(main())
