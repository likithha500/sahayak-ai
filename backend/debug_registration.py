import asyncio
import json
from app.session import VisitSession
from app.config import DB_PATH

async def main():
    session = VisitSession()

    print("Database:", DB_PATH)

    while True:
        text = input("\nYOU: ").strip()

        if text.lower() == "exit":
            break

        try:
            result = await session.process_turn(text)

            print("\nBACKEND RESPONSE:")
            print(json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str
            ))

            print("\nSESSION STATE:")
            for field in [
                "workflow",
                "current_question",
                "awaiting_registration_offer",
                "awaiting_registration_confirmation",
                "awaiting_confirmation",
                "registration_draft",
                "beneficiary",
            ]:
                print(field, "=", getattr(session, field, None))

        except Exception:
            import traceback
            traceback.print_exc()

asyncio.run(main())
