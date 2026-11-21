"""Run from backend/: python test_offline_sync.py"""

import os
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import sync_db
from app.sync_api import router


def main():
    with tempfile.TemporaryDirectory() as temp:
        original = sync_db.DB_PATH
        old_key = os.environ.get("SAHAYAK_SYNC_API_KEY")

        sync_db.DB_PATH = Path(temp) / "test_sync.db"
        os.environ["SAHAYAK_SYNC_API_KEY"] = "test-only-secret"

        try:
            sync_db.init_sync_db()

            app = FastAPI()
            app.include_router(router)

            headers = {
                "X-Sync-API-Key": "test-only-secret"
            }

            uid = str(uuid4())

            payload = {
                "client_record_id": uid,
                "beneficiary_id": "ASHA102",
                "transcript": "Newborn visit, weight 3.2 kg",
                "visit_draft": {
                    "weight_kg": 3.2
                },
            }

            url = "/api/offline-sync/records"

            with TestClient(app) as client:

                # Test 1: Unauthorized request
                response = client.post(url, json=payload)
                assert response.status_code == 401

                # Test 2: First upload
                first = client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

                assert first.status_code == 201, first.text

                saved = first.json()

                assert saved["status"] == "uploaded"
                assert saved["confirmed_visit_id"] is None

                # Test 3: Same upload again
                second = client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

                assert second.status_code == 201

                assert (
                    second.json()["server_sync_id"]
                    == saved["server_sync_id"]
                )

                # Test 4: Same UUID, different content
                changed = {
                    **payload,
                    "transcript": "Different content",
                }

                response = client.post(
                    url,
                    json=changed,
                    headers=headers,
                )

                assert response.status_code == 409

                # Test 5: Fetch synchronization status
                lookup = client.get(
                    f"{url}/{uid}",
                    headers=headers,
                )

                assert lookup.status_code == 200

                assert (
                    lookup.json()["server_sync_id"]
                    == saved["server_sync_id"]
                )

                # Test 6: Unknown record
                missing = client.get(
                    f"{url}/{uuid4()}",
                    headers=headers,
                )

                assert missing.status_code == 404

            # Test 7: Confirm only one database row exists
            with sync_db.database_connection() as db:
                count = db.execute(
                    "SELECT COUNT(*) FROM offline_sync_jobs"
                ).fetchone()[0]

                assert count == 1

            print(
                "PASS: authentication, upload, idempotent retry, "
                "conflict, status, missing ID, single DB row"
            )

        finally:
            sync_db.DB_PATH = original

            if old_key is None:
                os.environ.pop("SAHAYAK_SYNC_API_KEY", None)
            else:
                os.environ["SAHAYAK_SYNC_API_KEY"] = old_key


if __name__ == "__main__":
    main()