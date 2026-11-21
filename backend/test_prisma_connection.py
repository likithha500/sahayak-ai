
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()

from app.gnani_stt import connect_to_prisma


async def main():
    print("Connecting to Gnani Prisma v3.0...")

    try:
        async with await connect_to_prisma() as ws:
            response = await asyncio.wait_for(ws.recv(), timeout=15)
            data = json.loads(response)

            print("Server response type:", data.get("type"))
            print("Server message:", data.get("message"))
            print("Active configuration:", data.get("config"))

            if data.get("type") == "connected":
                print("SUCCESS: Prisma connection established!")
            else:
                print("Connection opened, but Prisma did not confirm readiness.")

    except Exception as error:
        print("FAILED:", type(error).__name__, str(error))


asyncio.run(main())
