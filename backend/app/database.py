
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sahayak.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS beneficiaries (
                beneficiary_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                village TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                beneficiary_id TEXT NOT NULL,
                visit_type TEXT,
                weight_kg REAL,
                vaccinations_due TEXT,
                next_visit_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (beneficiary_id)
                    REFERENCES beneficiaries(beneficiary_id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS danger_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                beneficiary_id TEXT,
                danger_type TEXT NOT NULL,
                transcript TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        samples = [
            ("ASHA101", "Anitha", "pregnancy", "Rampura"),
            ("ASHA102", "Lakshmi", "newborn", "Rampura"),
            ("ASHA103", "Meena", "child", "Rampura"),
            ("ASHA104", "Lakshmi", "pregnancy", "Hoskote"),
            ("ASHA105", "Suma", "postnatal", "Hoskote"),
        ]

        connection.executemany("""
            INSERT OR IGNORE INTO beneficiaries
            (beneficiary_id, name, category, village)
            VALUES (?, ?, ?, ?)
        """, samples)


def list_beneficiaries():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT beneficiary_id, name, category, village
            FROM beneficiaries ORDER BY beneficiary_id
        """).fetchall()
        return [dict(row) for row in rows]


def match_beneficiary(
    beneficiary_id=None,
    beneficiary_name=None,
):
    with get_connection() as connection:
        if beneficiary_id:
            row = connection.execute("""
                SELECT * FROM beneficiaries
                WHERE UPPER(beneficiary_id) = UPPER(?)
            """, (beneficiary_id.strip(),)).fetchone()

            if not row:
                return {
                    "status": "not_found",
                    "matches": [],
                    "message": "Beneficiary ID not found.",
                }

            match = dict(row)

            if (
                beneficiary_name
                and match["name"].casefold()
                != beneficiary_name.strip().casefold()
            ):
                return {
                    "status": "conflict",
                    "matches": [match],
                    "message": (
                        "The beneficiary ID and name do not match. "
                        "Please clarify."
                    ),
                }

            return {
                "status": "matched",
                "matches": [match],
                "message": "Beneficiary matched.",
            }

        if not beneficiary_name:
            return {
                "status": "missing",
                "matches": [],
                "message": "Please say the beneficiary name or ID.",
            }

        rows = connection.execute("""
            SELECT * FROM beneficiaries
            WHERE LOWER(name) = LOWER(?)
            ORDER BY beneficiary_id
        """, (beneficiary_name.strip(),)).fetchall()

        matches = [dict(row) for row in rows]

        if len(matches) == 1:
            status = "matched"
        elif len(matches) > 1:
            status = "ambiguous"
        else:
            status = "not_found"

        return {
            "status": status,
            "matches": matches,
            "message": (
                "Beneficiary matched."
                if status == "matched"
                else "Please clarify the beneficiary."
            ),
        }


def save_visit(beneficiary_id, visit):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO visits (
                beneficiary_id,
                visit_type,
                weight_kg,
                vaccinations_due,
                next_visit_date
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            beneficiary_id,
            visit.visit_type,
            visit.weight_kg,
            json.dumps(visit.vaccinations_due)
            if visit.vaccinations_due is not None else None,
            visit.next_visit_date.isoformat()
            if visit.next_visit_date else None,
        ))
        return cursor.lastrowid


def list_visits():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM visits ORDER BY id DESC
        """).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            if item["vaccinations_due"] is not None:
                item["vaccinations_due"] = json.loads(
                    item["vaccinations_due"]
                )
            result.append(item)

        return result


def save_danger_alert(danger_type, transcript, beneficiary_id=None):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO danger_alerts (
                beneficiary_id, danger_type, transcript
            )
            VALUES (?, ?, ?)
        """, (beneficiary_id, danger_type, transcript))
        return cursor.lastrowid


def acknowledge_danger_alert(alert_id):
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE danger_alerts
            SET acknowledged = 1
            WHERE id = ?
        """, (alert_id,))
        return cursor.rowcount > 0


def list_danger_alerts():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM danger_alerts
            ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]
