
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "sahayak.db"
LOCAL_TZ = timezone(timedelta(hours=5, minutes=30))


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


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

        visit_columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(visits)"
            ).fetchall()
        }
        if "idempotency_key" not in visit_columns:
            connection.execute(
                "ALTER TABLE visits ADD COLUMN idempotency_key TEXT"
            )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "idx_visits_idempotency_key "
            "ON visits(idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        )

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

        # Backward-compatible migration: preserve existing alerts and visits.
        existing = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(danger_alerts)"
            ).fetchall()
        }
        additions = {
            "severity": "TEXT NOT NULL DEFAULT 'urgent'",
            "matched_sign": "TEXT",
            "guideline_document": "TEXT",
            "guideline_page": "INTEGER",
            "recommended_action": "TEXT",
            "referral_status": "TEXT NOT NULL DEFAULT 'not_started'",
            "acknowledged_at": "TEXT",
            "referral_updated_at": "TEXT",
        }
        for column, declaration in additions.items():
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE danger_alerts ADD COLUMN {column} {declaration}"
                )

        alert_columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(danger_alerts)"
            ).fetchall()
        }
        if "visit_id" not in alert_columns:
            connection.execute(
                "ALTER TABLE danger_alerts ADD COLUMN visit_id "
                "INTEGER REFERENCES visits(id)"
            )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                beneficiary_id TEXT NOT NULL,
                visit_id INTEGER NOT NULL UNIQUE,
                scheduled_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'completed')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (beneficiary_id)
                    REFERENCES beneficiaries(beneficiary_id),
                FOREIGN KEY (visit_id) REFERENCES visits(id)
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_follow_ups_date_status "
            "ON follow_ups(scheduled_date, status)"
        )
        connection.execute("""
            INSERT OR IGNORE INTO follow_ups (
                beneficiary_id, visit_id, scheduled_date, reason
            )
            SELECT beneficiary_id, id, next_visit_date,
                   COALESCE(visit_type, 'Household visit')
            FROM visits
            WHERE next_visit_date IS NOT NULL
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
            SELECT beneficiaries.beneficiary_id,
                   beneficiaries.name,
                   beneficiaries.category,
                   beneficiaries.village,
                   (SELECT visits.created_at FROM visits
                    WHERE visits.beneficiary_id =
                          beneficiaries.beneficiary_id
                    ORDER BY visits.id DESC LIMIT 1) AS last_visit,
                   (SELECT follow_ups.scheduled_date FROM follow_ups
                    WHERE follow_ups.beneficiary_id =
                          beneficiaries.beneficiary_id
                      AND follow_ups.status = 'pending'
                    ORDER BY follow_ups.scheduled_date LIMIT 1)
                    AS next_visit
            FROM beneficiaries
            ORDER BY beneficiary_id
        """).fetchall()
        return [dict(row) for row in rows]


def normalize_beneficiary_id(value):
    if value is None:
        return None

    raw = str(value).strip().casefold()
    if not raw:
        return None

    word_numbers = {
        "zero": 0, "one": 1, "two": 2, "three": 3,
        "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
        "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20,
        "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90,
    }

    digits = "".join(
        character for character in raw
        if character.isdigit()
    )
    if digits:
        return digits

    words = "".join(
        character if character.isalnum() else " "
        for character in raw
    ).split()
    words = [
        word for word in words
        if word not in {
            "as", "ash", "asha", "beneficiary", "id",
            "beneficiaryid",
        }
    ]
    parsed = 0
    current = 0
    recognized = False
    direct_digit_words = {
        "zero", "one", "two", "three", "four",
        "five", "six", "seven", "eight", "nine",
    }
    if all(word in direct_digit_words for word in words):
        recognized = True
        return "".join(str(word_numbers[word]) for word in words)

    for word in words:
        if word in word_numbers:
            recognized = True
            current += word_numbers[word]
        elif word == "hundred":
            recognized = True
            current = max(current, 1) * 100
        elif word == "thousand":
            recognized = True
            parsed += max(current, 1) * 1000
            current = 0
    if recognized:
        return str(parsed + current)

    return raw.strip()


def match_beneficiary(
    beneficiary_id=None,
    beneficiary_name=None,
):
    beneficiary_id = normalize_beneficiary_id(beneficiary_id)

    with get_connection() as connection:
        if beneficiary_id:
            row = connection.execute("""
                SELECT * FROM beneficiaries
                WHERE UPPER(beneficiary_id) = UPPER(?)
            """, (beneficiary_id.strip(),)).fetchone()

            if not row:
                normalized = normalize_beneficiary_id(beneficiary_id)
                all_rows = connection.execute(
                    "SELECT * FROM beneficiaries"
                ).fetchall()
                candidates = [
                    dict(candidate)
                    for candidate in all_rows
                    if normalize_beneficiary_id(
                        candidate["beneficiary_id"]
                    ) == normalized
                ]

                if len(candidates) == 1:
                    row = connection.execute(
                        "SELECT * FROM beneficiaries "
                        "WHERE beneficiary_id = ?",
                        (candidates[0]["beneficiary_id"],),
                    ).fetchone()
                elif len(candidates) > 1:
                    return {
                        "status": "ambiguous",
                        "matches": candidates,
                        "message": (
                            "Multiple beneficiaries match that "
                            "short ID. Please provide the full "
                            "beneficiary ID or village."
                        ),
                    }

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


def _save_visit(connection, beneficiary_id, visit, idempotency_key,
                alert_ids=()):
    if idempotency_key:
        existing = connection.execute(
            "SELECT id FROM visits WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            visit_id = existing["id"]
        else:
            visit_id = None
    else:
        visit_id = None

    next_visit_date = (
        visit.next_visit_date.isoformat()
        if visit.next_visit_date else None
    )
    if visit_id is None:
        cursor = connection.execute("""
            INSERT INTO visits (
                beneficiary_id,
                visit_type,
                weight_kg,
                vaccinations_due,
                next_visit_date,
                idempotency_key
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            beneficiary_id,
            visit.visit_type,
            visit.weight_kg,
            json.dumps(visit.vaccinations_due)
            if visit.vaccinations_due is not None else None,
            next_visit_date,
            idempotency_key,
        ))
        visit_id = cursor.lastrowid

    if next_visit_date:
        connection.execute("""
            INSERT INTO follow_ups (
                beneficiary_id, visit_id, scheduled_date, reason
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(visit_id) DO UPDATE SET
                beneficiary_id = excluded.beneficiary_id,
                scheduled_date = excluded.scheduled_date,
                reason = excluded.reason,
                updated_at = CURRENT_TIMESTAMP
            WHERE follow_ups.status = 'pending'
        """, (
            beneficiary_id,
            visit_id,
            next_visit_date,
            visit.visit_type,
        ))

    if alert_ids:
        placeholders = ",".join("?" for _ in alert_ids)
        connection.execute(
            f"""
            UPDATE danger_alerts
            SET beneficiary_id = COALESCE(beneficiary_id, ?),
                visit_id = ?
            WHERE id IN ({placeholders})
              AND (beneficiary_id IS NULL OR beneficiary_id = ?)
              AND (visit_id IS NULL OR visit_id = ?)
            """,
            (beneficiary_id, visit_id, *alert_ids,
             beneficiary_id, visit_id),
        )

    return visit_id


def save_visit(beneficiary_id, visit, idempotency_key=None, alert_ids=()):
    with get_connection() as connection:
        return _save_visit(
            connection,
            beneficiary_id,
            visit,
            idempotency_key,
            alert_ids,
        )


def list_visits():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT visits.*,
                   beneficiaries.name AS beneficiary_name,
                   beneficiaries.category AS beneficiary_category,
                   beneficiaries.village AS beneficiary_village,
                   follow_ups.id AS follow_up_id,
                   follow_ups.scheduled_date AS follow_up_date,
                   follow_ups.status AS follow_up_status
            FROM visits
            JOIN beneficiaries
              ON beneficiaries.beneficiary_id = visits.beneficiary_id
            LEFT JOIN follow_ups ON follow_ups.visit_id = visits.id
            ORDER BY visits.id DESC
        """).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            if item["vaccinations_due"] is not None:
                item["vaccinations_due"] = json.loads(
                    item["vaccinations_due"]
                )
            item["alerts"] = [
                dict(alert) for alert in connection.execute(
                    "SELECT * FROM danger_alerts WHERE visit_id = ? "
                    "ORDER BY id",
                    (item["id"],),
                ).fetchall()
            ]
            result.append(item)

        return result


def get_visit(visit_id):
    return next(
        (visit for visit in list_visits() if visit["id"] == visit_id),
        None,
    )


def get_beneficiary(beneficiary_id):
    match = match_beneficiary(beneficiary_id=beneficiary_id)
    if match["status"] != "matched":
        return None

    beneficiary = match["matches"][0]
    with get_connection() as connection:
        row = connection.execute("""
            SELECT
                (SELECT created_at FROM visits
                 WHERE beneficiary_id = ?
                 ORDER BY id DESC LIMIT 1) AS last_visit,
                (SELECT scheduled_date FROM follow_ups
                 WHERE beneficiary_id = ? AND status = 'pending'
                 ORDER BY scheduled_date LIMIT 1) AS next_visit
        """, (
            beneficiary["beneficiary_id"],
            beneficiary["beneficiary_id"],
        )).fetchone()

    result = dict(beneficiary)
    result.update(dict(row))
    return result


def get_beneficiary_visits(beneficiary_id):
    beneficiary = get_beneficiary(beneficiary_id)
    if beneficiary is None:
        return None
    return [
        visit for visit in list_visits()
        if visit["beneficiary_id"] == beneficiary["beneficiary_id"]
    ]


def list_follow_ups():
    today = datetime.now(LOCAL_TZ).date().isoformat()
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT follow_ups.*,
                   beneficiaries.name AS beneficiary_name,
                   beneficiaries.category AS beneficiary_category,
                   visits.visit_type
            FROM follow_ups
            JOIN beneficiaries
              ON beneficiaries.beneficiary_id =
                 follow_ups.beneficiary_id
            JOIN visits ON visits.id = follow_ups.visit_id
            ORDER BY
                CASE WHEN follow_ups.status = 'completed' THEN 1 ELSE 0 END,
                follow_ups.scheduled_date,
                follow_ups.id
        """).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        if item["status"] == "pending" and item["scheduled_date"] < today:
            item["status"] = "overdue"
        result.append(item)
    return result


def update_follow_up(follow_up_id, *, scheduled_date=None, status=None):
    if status not in (None, "pending", "completed"):
        raise ValueError("Unsupported follow-up status")
    if scheduled_date is not None:
        date.fromisoformat(scheduled_date)

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM follow_ups WHERE id = ?",
            (follow_up_id,),
        ).fetchone()
        if existing is None:
            return False

        if scheduled_date is not None and status is not None:
            connection.execute("""
                UPDATE follow_ups
                SET scheduled_date = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (scheduled_date, status, follow_up_id))
        elif scheduled_date is not None:
            connection.execute("""
                UPDATE follow_ups
                SET scheduled_date = ?, status = 'pending',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (scheduled_date, follow_up_id))
        elif status is not None:
            connection.execute("""
                UPDATE follow_ups
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, follow_up_id))
    return True


def dashboard_data():
    now = datetime.now(LOCAL_TZ)
    today = now.date().isoformat()
    start_local = datetime.combine(now.date(), time.min, tzinfo=LOCAL_TZ)
    end_local = datetime.combine(now.date(), time.max, tzinfo=LOCAL_TZ)
    start_utc = start_local.astimezone(timezone.utc).replace(
        tzinfo=None
    ).isoformat(sep=" ")
    end_utc = end_local.astimezone(timezone.utc).replace(
        tzinfo=None
    ).isoformat(sep=" ")

    with get_connection() as connection:
        counts = connection.execute("""
            SELECT
                (SELECT COUNT(*) FROM beneficiaries) AS beneficiaries,
                (SELECT COUNT(*) FROM visits
                 WHERE created_at >= ? AND created_at <= ?) AS visits_today,
                (SELECT COUNT(*) FROM follow_ups
                 WHERE status = 'pending'
                   AND scheduled_date = ?) AS scheduled_today,
                (SELECT COUNT(*) FROM follow_ups
                 WHERE status = 'pending'
                   AND scheduled_date >= ?) AS upcoming_follow_ups,
                (SELECT COUNT(*) FROM follow_ups
                 WHERE status = 'pending'
                   AND scheduled_date < ?) AS overdue_follow_ups,
                (SELECT COUNT(*) FROM danger_alerts
                 WHERE severity = 'urgent'
                   AND COALESCE(referral_status, 'not_started')
                       != 'completed') AS urgent_referrals
        """, (
            start_utc, end_utc, today, today, today,
        )).fetchone()

    visits = list_visits()
    alerts = list_danger_alerts()
    today_visits = [
        visit for visit in visits
        if visit.get("created_at")
        and start_utc <= visit["created_at"] <= end_utc
    ]
    follow_ups = list_follow_ups()
    return {
        "stats": {
            "beneficiaries": counts["beneficiaries"],
            "visits_today": counts["visits_today"],
            "scheduled_today": counts["scheduled_today"],
            "upcoming_follow_ups": counts["upcoming_follow_ups"],
            "overdue_follow_ups": counts["overdue_follow_ups"],
            "urgent_referrals": counts["urgent_referrals"],
        },
        "today_visits": today_visits,
        "recent_visits": visits[:5],
        "upcoming_follow_ups": [
            item for item in follow_ups
            if item["status"] in ("pending", "overdue")
        ][:5],
        "urgent_alerts": [
            alert for alert in alerts
            if alert.get("severity") == "urgent"
            and alert.get("referral_status", "not_started") != "completed"
        ][:5],
    }


def save_danger_alert(danger_type, transcript, beneficiary_id=None, *,
                      severity="urgent", matched_sign=None,
                      guideline_document=None, guideline_page=None,
                      recommended_action=None):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO danger_alerts (
                beneficiary_id, danger_type, transcript, severity,
                matched_sign, guideline_document, guideline_page,
                recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (beneficiary_id, danger_type, transcript, severity,
              matched_sign, guideline_document, guideline_page,
              recommended_action))
        return cursor.lastrowid


def acknowledge_danger_alert(alert_id):
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE danger_alerts
            SET acknowledged = 1,
                acknowledged_at = COALESCE(acknowledged_at, CURRENT_TIMESTAMP)
            WHERE id = ?
        """, (alert_id,))
        return cursor.rowcount > 0


REFERRAL_STATUSES = {"not_started", "referred", "follow_up_pending", "completed"}


def update_referral_status(alert_id, status):
    if status not in REFERRAL_STATUSES:
        raise ValueError("Unsupported referral status")
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE danger_alerts
            SET referral_status = ?, referral_updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, alert_id))
        return cursor.rowcount > 0


def list_danger_alerts():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM danger_alerts ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]
