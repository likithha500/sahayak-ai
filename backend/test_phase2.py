"""Run: python test_phase2.py. Uses an isolated temporary SQLite database."""
import tempfile
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from unittest.mock import patch

from app import database
from app.safety import detect_danger_signs


@contextmanager
def closed_connection():
    """Commit/rollback and close SQLite handles on Windows."""
    with closing(_original_get_connection()) as connection:
        with connection:
            yield connection


_original_get_connection = database.get_connection


def main():
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        stack.enter_context(patch.object(database, "get_connection", closed_connection))
        test_db = Path(directory) / "phase2.db"
        with patch.object(database, "DB_PATH", test_db):
            database.initialize_database()
            alert = detect_danger_signs("ASHA101 Anitha is pregnant and bleeding")[0]
            assert alert["danger_type"] == "pregnancy_bleeding"
            alert_id = database.save_danger_alert(
                alert["danger_type"], "ASHA101 Anitha is pregnant and bleeding",
                "ASHA101", severity=alert["severity"],
                matched_sign=alert["matched_sign"],
                guideline_document=alert["guideline_document"],
                guideline_page=alert["guideline_page"],
                recommended_action=alert["recommended_action"],
            )
            saved = database.list_danger_alerts()[0]
            assert saved["id"] == alert_id
            assert saved["guideline_page"] == 59
            assert saved["referral_status"] == "not_started"
            assert saved["acknowledged"] == 0
            assert database.acknowledge_danger_alert(alert_id)
            assert database.update_referral_status(alert_id, "referred")
            saved = database.list_danger_alerts()[0]
            assert saved["acknowledged"] == 1
            assert saved["acknowledged_at"]
            assert saved["referral_status"] == "referred"
            assert saved["referral_updated_at"]
            try:
                database.update_referral_status(alert_id, "unknown")
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid referral status accepted")
            # Re-initialization is idempotent.
            database.initialize_database()
            assert database.list_danger_alerts()[0]["id"] == alert_id
            print("PASS: new database, alert metadata, acknowledgement, referral status")

        # Simulate an older database without the new columns.
        with patch.object(database, "DB_PATH", test_db):
            with database.get_connection() as conn:
                conn.execute("DROP TABLE danger_alerts")
                conn.execute("""CREATE TABLE danger_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    beneficiary_id TEXT, danger_type TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )""")
                conn.execute("INSERT INTO danger_alerts (danger_type, transcript) VALUES (?, ?)",
                             ("newborn_high_fever", "old alert"))
            database.initialize_database()
            rows = database.list_danger_alerts()
            assert len(rows) == 1 and rows[0]["transcript"] == "old alert"
            assert rows[0]["referral_status"] == "not_started"
            print("PASS: migration preserves existing alerts")
    print("ALL PHASE 2 DATABASE TESTS PASSED")


if __name__ == "__main__":
    main()
