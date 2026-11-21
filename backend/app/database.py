
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sahayak.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
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

        sample_beneficiaries = [
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
        """, sample_beneficiaries)

        connection.commit()


def list_beneficiaries():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT beneficiary_id, name, category, village
            FROM beneficiaries
            ORDER BY beneficiary_id
        """).fetchall()

        return [dict(row) for row in rows]


def match_beneficiary(
    beneficiary_id: str | None = None,
    beneficiary_name: str | None = None,
):
    with get_connection() as connection:
        if beneficiary_id:
            row = connection.execute("""
                SELECT beneficiary_id, name, category, village
                FROM beneficiaries
                WHERE UPPER(beneficiary_id) = UPPER(?)
            """, (beneficiary_id.strip(),)).fetchone()

            if row:
                result = dict(row)

                if (
                    beneficiary_name
                    and result["name"].casefold()
                    != beneficiary_name.strip().casefold()
                ):
                    return {
                        "status": "conflict",
                        "matches": [result],
                        "message": (
                            "The spoken beneficiary ID and name "
                            "do not match. Please clarify."
                        ),
                    }

                return {
                    "status": "matched",
                    "matches": [result],
                    "message": "Beneficiary matched.",
                }

            return {
                "status": "not_found",
                "matches": [],
                "message": "Beneficiary ID not found.",
            }

        if not beneficiary_name:
            return {
                "status": "missing",
                "matches": [],
                "message": "Please say the beneficiary name or ID.",
            }

        rows = connection.execute("""
            SELECT beneficiary_id, name, category, village
            FROM beneficiaries
            WHERE LOWER(name) = LOWER(?)
            ORDER BY beneficiary_id
        """, (beneficiary_name.strip(),)).fetchall()

        matches = [dict(row) for row in rows]

        if len(matches) == 1:
            return {
                "status": "matched",
                "matches": matches,
                "message": "Beneficiary matched.",
            }

        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "matches": matches,
                "message": (
                    "Multiple beneficiaries have this name. "
                    "Please confirm the village or beneficiary ID."
                ),
            }

        return {
            "status": "not_found",
            "matches": [],
            "message": "Beneficiary not found. Please clarify.",
        }
