
import asyncio
import json

from websockets.asyncio.client import connect


URL = "ws://127.0.0.1:8000/ws/voice"


async def receive_until(ws, expected_type):
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=35)
        event = json.loads(raw)

        print(
            "SERVER:",
            json.dumps(event, ensure_ascii=False),
        )

        if event["type"] == "session_error":
            raise RuntimeError(event["message"])

        if event["type"] == expected_type:
            return event


async def send_turn(ws, text):
    print(f"\nASHA: {text}")

    await ws.send(json.dumps({
        "type": "transcript_final",
        "text": text,
    }))

    events = []

    # The backend always emits agent_reply last for
    # successful transcript_final turns.
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=35)
        event = json.loads(raw)

        print(
            "SERVER:",
            json.dumps(event, ensure_ascii=False),
        )

        events.append(event)

        if event["type"] == "session_error":
            raise RuntimeError(event["message"])

        if event["type"] == "agent_reply":
            break

    return events


def find_event(events, event_type):
    return next(
        (event for event in events if event["type"] == event_type),
        None,
    )


async def test_visit_flow():
    async with connect(URL) as ws:
        print("CONNECTED:", await ws.recv())

        events = await send_turn(
            ws,
            "Lakshmi newborn visit weight 2.8 kg",
        )
        assert find_event(events, "beneficiary_clarification")

        events = await send_turn(ws, "Rampura")
        draft = find_event(events, "visit_draft")

        assert draft
        assert draft["saved"] is False
        assert draft["beneficiary"]["beneficiary_id"] == "ASHA102"

        events = await send_turn(
            ws,
            "Actually weight is 3.2 kg",
        )
        draft = find_event(events, "visit_draft")

        assert draft
        assert draft["visit"]["weight_kg"] == 3.2
        assert draft["saved"] is False

        events = await send_turn(ws, "yes")
        saved = find_event(events, "visit_saved")

        assert saved

        print("\nSUCCESS: Multi-turn visit test passed!")
        print("Saved visit ID:", saved["visit_id"])


async def test_danger_alert():
    async with connect(URL) as ws:
        print("CONNECTED:", await ws.recv())

        events = await send_turn(
            ws,
            "ASHA101 Anitha is pregnant and bleeding",
        )

        alert = find_event(events, "danger_sign_detected")
        assert alert, "Expected pregnancy bleeding alert"

        print("\nSUCCESS: Danger alert detected!")
        print("Alert ID:", alert["alert_id"])

        events = await send_turn(ws, "yes")

        assert not find_event(events, "visit_saved")
        assert any(
            "acknowledgement" in event.get("text", "").lower()
            for event in events
        ), "Expected save to be blocked"

        print("SUCCESS: Save blocked pending acknowledgement!")

        await ws.send(json.dumps({
            "type": "acknowledge_alert",
            "alert_id": alert["alert_id"],
        }))

        acknowledged = await receive_until(
            ws,
            "danger_alert_acknowledged",
        )

        assert acknowledged["acknowledged"] is True

        print("SUCCESS: Alert acknowledged!")

        events = await send_turn(ws, "yes")
        saved = find_event(events, "visit_saved")

        assert saved, "Expected save after acknowledgement"

        print("SUCCESS: Visit saved after acknowledgement!")


async def main():
    await test_visit_flow()
    await test_danger_alert()

    print("\nALL SESSION TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
