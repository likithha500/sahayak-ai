
import asyncio
import json
import websockets


async def main():
    url = "ws://127.0.0.1:8000/ws/voice"

    print("Connecting to SAHAYAK AI backend...")

    async with websockets.connect(url) as ws:
        initial = json.loads(await ws.recv())
        print("Backend:", initial)

        print("Testing Gnani Prisma connection...")

        await ws.send(json.dumps({
            "type": "test_prisma"
        }))

        response = await asyncio.wait_for(
            ws.recv(),
            timeout=25
        )

        data = json.loads(response)
        print("Prisma response:", data)

        if data.get("type") == "prisma_connected":
            print("SUCCESS: FastAPI -> Gnani Prisma working!")
        else:
            print("FAILED: Check backend terminal for errors.")


asyncio.run(main())
