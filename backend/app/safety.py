
import re


def detect_danger_signs(text, visit_type=None):
    text = text.casefold()

    pregnancy_context = (
        visit_type == "pregnancy"
        or any(term in text for term in [
            "pregnant", "pregnancy", "garbhavati",
            "गर्भवती", "गर्भावस्था",
            "ಗರ್ಭಿಣಿ", "ಗರ್ಭಾವಸ್ಥೆ",
        ])
    )

    newborn_context = (
        visit_type == "newborn"
        or any(term in text for term in [
            "newborn", "new born", "new born baby",
            "नवजात", "नवजात शिशु",
            "ನವಜಾತ", "ಹಸುಗೂಸು",
        ])
    )

    bleeding = any(term in text for term in [
        "bleeding", "blood loss", "bleed",
        "रक्तस्राव", "खून बह",
        "ರಕ್ತಸ್ರಾವ", "ರಕ್ತ ಬರುತ್ತ",
    ])

    fever = any(term in text for term in [
        "high fever", "very high fever",
        "तेज बुखार", "बहुत बुखार",
        "ತೀವ್ರ ಜ್ವರ", "ಹೆಚ್ಚು ಜ್ವರ",
    ])

    temperature = re.search(
        r"(\d{2,3}(?:\.\d+)?)\s*°?\s*([cf])\b",
        text,
    )

    if temperature:
        value = float(temperature.group(1))
        unit = temperature.group(2)

        if unit == "c" and value >= 38:
            fever = True
        if unit == "f" and value >= 100.4:
            fever = True

    # Avoid treating common explicit negations as positive alerts.
    # This is limited and does not cover all languages.
    if re.search(r"\b(no|not|without)\s+bleeding\b", text):
        bleeding = False

    if re.search(r"\b(no|not|without)\s+(high\s+)?fever\b", text):
        fever = False

    alerts = []

    if pregnancy_context and bleeding:
        alerts.append({
            "danger_type": "pregnancy_bleeding",
            "severity": "urgent",
            "message": (
                "Danger sign: bleeding during pregnancy. "
                "Arrange immediate assessment at the nearest "
                "appropriate health facility. Contact the local "
                "emergency referral service."
            ),
        })

    if newborn_context and fever:
        alerts.append({
            "danger_type": "newborn_high_fever",
            "severity": "urgent",
            "message": (
                "Danger sign: fever in a newborn. "
                "Arrange immediate medical assessment at the "
                "nearest appropriate health facility."
            ),
        })

    return alerts
