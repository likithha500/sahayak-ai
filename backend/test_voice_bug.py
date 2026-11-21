import asyncio
import json
import sqlite3
from pathlib import Path

from websockets.asyncio.client import connect


URL = "ws://127.0.0.1:8001/ws/voice"
DB_PATH = Path(__file__).resolve().parent / "sahayak.db"


async def send_turn(ws, text):
    await ws.send(json.dumps({
        "type": "transcript_final",
        "text": text,
        "turn_id": f"test-{text}",
    }))

    events = []
    while True:
        event = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
        events.append(event)
        event_type = event["type"]
        if event_type == "agent_speaking_finished":
            return events
        if event_type in {"danger_sign_detected", "session_error"}:
            if event_type == "session_error":
                return events


async def main():
    async with connect(URL, max_size=10 * 1024 * 1024) as ws:
        connected = json.loads(await ws.recv())
        assert connected["type"] == "session_connected"

        await ws.send(json.dumps({
            "type": "start_session",
            "language": "en",
        }))
        greeting_events = []
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=40))
            greeting_events.append(event)
            if event["type"] == "agent_speaking_finished":
                break

        premature = await send_turn(
            ws,
            "Save this visit",
        )
        premature_draft = next(
            event for event in premature
            if event["type"] == "visit_draft"
        )
        assert "Nothing has been saved" in premature_draft["message"]

        identified = await send_turn(
            ws,
            "I want to record a pregnancy visit for beneficiary 103",
        )
        draft = next(
            event for event in identified
            if event["type"] == "visit_draft"
        )
        assert draft["beneficiary"]["beneficiary_id"] == "ASHA103"

        weight = await send_turn(ws, "Fifty-four kilograms")
        assert any(
            event["type"] == "visit_draft"
            for event in weight
        )

        vaccines = await send_turn(ws, "No vaccinations are due")
        assert any(
            event["type"] == "visit_draft"
            for event in vaccines
        )

        date = await send_turn(ws, "December fifth 2026")
        review = next(
            event for event in date
            if event["type"] == "visit_draft"
        )
        assert review["awaiting_confirmation"] is True

        before = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM visits"
        ).fetchone()[0]

        saved_events = await send_turn(ws, "Yes, save it")
        saved = next(
            event for event in saved_events
            if event["type"] == "visit_saved"
        )
        assert isinstance(saved["visit_id"], int)

        after = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM visits"
        ).fetchone()[0]
        assert after == before + 1

        repeat_events = await send_turn(ws, "Yes, save it")
        repeat = next(
            event for event in repeat_events
            if event["type"] == "agent_reply"
        )
        assert "already saved successfully" in repeat["text"]
        assert "No duplicate" in repeat["text"]

        final_count = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM visits"
        ).fetchone()[0]
        assert final_count == after

        print(
            json.dumps({
                "beneficiary": "ASHA103",
                "visit_id": saved["visit_id"],
                "before": before,
                "after": after,
                "final_count": final_count,
            }, ensure_ascii=False)
        )


asyncio.run(main())
