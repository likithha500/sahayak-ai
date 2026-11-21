
import asyncio
import json
import sys
import urllib.request
from websockets.asyncio.client import connect

sys.stdout.reconfigure(encoding='utf-8')

URL = "ws://127.0.0.1:8000/ws/voice"
API_VISITS = "http://127.0.0.1:8000/api/visits"


def get_stored_visits():
    with urllib.request.urlopen(API_VISITS) as resp:
        return json.loads(resp.read().decode())


async def send_turn(ws, text):
    print(f"\n[CLIENT] transcript_final: {text}")
    await ws.send(json.dumps({"type": "transcript_final", "text": text}))
    events = []
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=35)
        event = json.loads(raw)
        print("  [SERVER]:", event.get("type"), event.get("message") or event.get("text") or "")
        events.append(event)
        if event["type"] in ("agent_reply", "visit_saved"):
            # Check if more messages immediately available
            try:
                raw2 = await asyncio.wait_for(ws.recv(), timeout=0.5)
                e2 = json.loads(raw2)
                print("  [SERVER]:", e2.get("type"), e2.get("message") or e2.get("text") or "")
                events.append(e2)
            except asyncio.TimeoutError:
                pass
            break
        if event["type"] == "session_error":
            break
    return events


def find_event(events, event_type):
    return next((e for e in events if e.get("type") == event_type), None)


async def test_meena_asha103():
    print("\n" + "="*50)
    print("TEST 1: Meena / ASHA103 Voice Transcript -> Draft -> Confirm -> Save")
    print("="*50)
    async with connect(URL) as ws:
        await ws.recv()  # welcome
        events = await send_turn(ws, "Beneficiary ASHA 103 Meena child visit weight 12 kg")
        draft = find_event(events, "visit_draft")
        assert draft is not None, "Expected visit_draft"
        assert draft["saved"] is False, "Draft must not be pre-saved"
        assert draft["beneficiary"]["beneficiary_id"] == "ASHA103"
        assert draft["beneficiary"]["name"] == "Meena"
        assert draft["beneficiary"]["village"] == "Rampura"
        assert draft["visit"]["visit_type"] == "child"
        assert draft["visit"]["weight_kg"] == 12.0
        print("✓ Verified Meena / ASHA103 matched correctly in Rampura")

        events = await send_turn(ws, "yes")
        saved = find_event(events, "visit_saved")
        assert saved is not None, "Expected visit_saved"
        assert saved["beneficiary_id"] == "ASHA103"
        visit_id = saved["visit_id"]
        print(f"✓ Visit saved with ID: {visit_id}")

        visits = get_stored_visits()
        record = next((v for v in visits if v["id"] == visit_id), None)
        assert record is not None, f"Visit {visit_id} not found in /api/visits"
        assert record["beneficiary_id"] == "ASHA103"
        assert record["weight_kg"] == 12.0
        print(f"✓ Verified visit {visit_id} persisted in SQLite /api/visits")


async def test_both_lakshmi_records():
    print("\n" + "="*50)
    print("TEST 2: Both Lakshmi Records Disambiguation (Rampura vs Hoskote)")
    print("="*50)
    # Lakshmi 1: Rampura (ASHA102)
    async with connect(URL) as ws:
        await ws.recv()
        events = await send_turn(ws, "Lakshmi newborn visit weight 2.8 kg")
        clarification = find_event(events, "beneficiary_clarification")
        assert clarification is not None, "Expected clarification for duplicate name Lakshmi"
        assert len(clarification["candidates"]) >= 2
        print("✓ Ambiguity detected between multiple Lakshmi records")

        events = await send_turn(ws, "Rampura")
        draft = find_event(events, "visit_draft")
        assert draft is not None
        assert draft["beneficiary"]["beneficiary_id"] == "ASHA102"
        assert draft["beneficiary"]["village"] == "Rampura"
        print("✓ Resolved to ASHA102 Lakshmi (Rampura)")

        events = await send_turn(ws, "yes")
        saved = find_event(events, "visit_saved")
        assert saved is not None
        assert saved["beneficiary_id"] == "ASHA102"
        print(f"✓ ASHA102 visit saved with ID: {saved['visit_id']}")

    # Lakshmi 2: Hoskote (ASHA104)
    async with connect(URL) as ws:
        await ws.recv()
        events = await send_turn(ws, "Lakshmi pregnancy visit")
        clarification = find_event(events, "beneficiary_clarification")
        assert clarification is not None
        print("✓ Ambiguity detected for second Lakshmi")

        events = await send_turn(ws, "Hoskote")
        draft = find_event(events, "visit_draft")
        assert draft is not None
        assert draft["beneficiary"]["beneficiary_id"] == "ASHA104"
        assert draft["beneficiary"]["village"] == "Hoskote"
        print("✓ Resolved to ASHA104 Lakshmi (Hoskote)")

        events = await send_turn(ws, "yes")
        saved = find_event(events, "visit_saved")
        assert saved is not None
        assert saved["beneficiary_id"] == "ASHA104"
        print(f"✓ ASHA104 visit saved with ID: {saved['visit_id']}")


async def test_frontend_demo_scenarios():
    print("\n" + "="*50)
    print("TEST 3: Frontend Demo Beneficiary Scenario (AS-205)")
    print("="*50)
    async with connect(URL) as ws:
        await ws.recv()
        # Scenario 2 from mock.ts: "Beneficiary 205 newborn baby weight 2.8 kilo hai. Next visit tomorrow."
        events = await send_turn(ws, "Beneficiary 205 newborn baby weight 2.8 kilo hai. Next visit tomorrow.")
        draft = find_event(events, "visit_draft")
        assert draft is not None, "Expected visit_draft"
        assert draft["beneficiary"]["beneficiary_id"] == "AS-205"
        assert draft["beneficiary"]["name"] == "Baby of Kavya"
        assert draft["visit"]["visit_type"] == "newborn"
        assert draft["visit"]["weight_kg"] == 2.8
        print("✓ Demo beneficiary AS-205 (Baby of Kavya) matched successfully")

        # Test explicit confirm_save message
        print("\n[CLIENT] sending explicit confirm_save event...")
        await ws.send(json.dumps({"type": "confirm_save"}))
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        saved = json.loads(raw)
        assert saved["type"] == "visit_saved"
        assert saved["beneficiary_id"] == "AS-205"
        print(f"✓ Visit saved via explicit confirm_save: ID {saved['visit_id']}")


async def test_unknown_beneficiary():
    print("\n" + "="*50)
    print("TEST 4: Unknown Beneficiary (No Silent Save)")
    print("="*50)
    async with connect(URL) as ws:
        await ws.recv()
        events = await send_turn(ws, "Beneficiary 999 Priya newborn visit weight 3 kg")
        saved = find_event(events, "visit_saved")
        assert saved is None, "Must NOT save unknown beneficiary"
        reply = find_event(events, "agent_reply")
        assert reply is not None
        assert "not found" in reply["text"].lower() or "register" in reply["text"].lower()
        print(f"✓ Unknown beneficiary rejected with helpful message: '{reply['text']}'")


async def test_invalid_id_with_valid_name_clarification():
    print("\n" + "="*50)
    print("TEST 5: Invalid ID with Valid Name (Clarification, No Silent Match)")
    print("="*50)
    async with connect(URL) as ws:
        await ws.recv()
        events = await send_turn(ws, "Beneficiary 999 Meena child visit weight 10 kg")
        saved = find_event(events, "visit_saved")
        assert saved is None, "Must NOT silently match or save"
        clarification = find_event(events, "beneficiary_clarification")
        assert clarification is not None, "Expected clarification when ID is invalid but name matches"
        assert any(c["name"] == "Meena" for c in clarification["candidates"])
        print(f"✓ Clarification requested without silent match: {clarification['message']}")


async def main():
    await test_meena_asha103()
    await test_both_lakshmi_records()
    await test_frontend_demo_scenarios()
    await test_unknown_beneficiary()
    await test_invalid_id_with_valid_name_clarification()
    print("\n" + "="*50)
    print("ALL COMPREHENSIVE BENEFICIARY & VISIT TESTS PASSED SUCCESSFULLY!")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
