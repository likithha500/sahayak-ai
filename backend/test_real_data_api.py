"""Verify real-data APIs and idempotent visit/follow-up persistence."""

import tempfile
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app import audio_processing_db, audio_sync_db, database, sync_db
from app.main import app
from app.schemas import VisitExtraction


def main():
    with tempfile.TemporaryDirectory() as temp:
        original_database_path = database.DB_PATH
        original_sync_path = sync_db.DB_PATH
        test_database = Path(temp) / "sahayak-test.db"
        database.DB_PATH = test_database
        sync_db.DB_PATH = test_database

        try:
            database.initialize_database()
            sync_db.init_sync_db()
            audio_sync_db.init_audio_sync_db()
            audio_processing_db.init_audio_processing_db()
            due_date = date.today() + timedelta(days=7)
            visit = VisitExtraction(
                beneficiary_id="ASHA103",
                visit_type="child",
                weight_kg=18.5,
                vaccinations_due=["Measles"],
                next_visit_date=due_date,
            )
            visit_id = database.save_visit(
                "ASHA103",
                visit,
                idempotency_key="real-data-api-test",
            )
            duplicate_id = database.save_visit(
                "ASHA103",
                visit,
                idempotency_key="real-data-api-test",
            )
            assert duplicate_id == visit_id
            assert len(database.list_visits()) == 1

            offline_id = str(uuid4())
            audio_sync_db.save_audio(
                offline_id,
                "ASHA103",
                "2026-01-01T10:00:00Z",
                "audio/webm",
                b"synthetic-test-audio",
            )
            assert audio_processing_db.claim_job(offline_id) == "claimed"
            audio_processing_db.finish_job(
                offline_id,
                {
                    "transcript": "Child visit, weight 18.5 kilograms",
                    "detected_language": "en-IN",
                    "model": "synthetic-test",
                    "request_id": "synthetic-test",
                    "truncated": False,
                },
            )
            assert audio_processing_db.confirm_transcript(
                offline_id,
                "Child visit, weight 18.5 kilograms",
            ) == "confirmed"
            offline_visit = VisitExtraction(
                visit_type="child",
                weight_kg=18.5,
                vaccinations_due=None,
                next_visit_date=None,
            )
            saved_offline = audio_processing_db.save_confirmed_offline_visit(
                offline_id,
                offline_visit,
            )
            repeated_offline = audio_processing_db.save_confirmed_offline_visit(
                offline_id,
                offline_visit,
            )
            assert saved_offline["status"] == "visit_saved"
            assert repeated_offline["status"] == "already_saved"
            assert repeated_offline["visit_id"] == saved_offline["visit_id"]
            assert len(database.list_visits()) == 2

            follow_ups = database.list_follow_ups()
            assert len(follow_ups) == 1
            assert follow_ups[0]["visit_id"] == visit_id
            assert follow_ups[0]["scheduled_date"] == due_date.isoformat()
            alert_id = database.save_danger_alert(
                "synthetic test alert",
                "Synthetic urgent referral test",
                beneficiary_id="ASHA103",
                recommended_action="Contact the referral facility.",
            )

            with TestClient(app) as client:
                beneficiary = client.get("/api/beneficiaries/103")
                assert beneficiary.status_code == 200
                assert beneficiary.json()["beneficiary_id"] == "ASHA103"
                beneficiary_visits = client.get(
                    "/api/beneficiaries/ASHA103/visits"
                )
                assert beneficiary_visits.status_code == 200
                assert any(
                    item["id"] == visit_id
                    for item in beneficiary_visits.json()
                )

                visits = client.get("/api/visits")
                assert visits.status_code == 200
                api_visit = next(
                    item for item in visits.json()
                    if item["id"] == visit_id
                )
                assert api_visit["beneficiary_name"] == "Meena"
                visit_detail = client.get(f"/api/visits/{visit_id}")
                assert visit_detail.status_code == 200
                assert visit_detail.json()["id"] == visit_id

                dashboard = client.get("/api/dashboard")
                assert dashboard.status_code == 200
                assert dashboard.json()["stats"]["beneficiaries"] == 5
                assert dashboard.json()["stats"]["urgent_referrals"] == 1

                follow_up_id = follow_ups[0]["id"]
                complete = client.patch(
                    f"/api/follow-ups/{follow_up_id}",
                    json={"status": "completed"},
                )
                assert complete.status_code == 200
                assert complete.json()["status"] == "completed"

                acknowledged = client.post(
                    f"/api/alerts/{alert_id}/acknowledge"
                )
                assert acknowledged.status_code == 200
                assert acknowledged.json()["acknowledged"] == 1
                referral = client.patch(
                    f"/api/alerts/{alert_id}/referral-status",
                    json={"status": "completed"},
                )
                assert referral.status_code == 200
                assert referral.json()["referral_status"] == "completed"

        finally:
            database.DB_PATH = original_database_path
            sync_db.DB_PATH = original_sync_path

    print("PASS: real beneficiary/visit APIs, dashboard, follow-up, and idempotency")


if __name__ == "__main__":
    main()
