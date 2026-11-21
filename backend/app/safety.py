"""Conservative, rule-based referral flags for a synthetic-data ASHA prototype.

Sources:
- MoHFW, Reference Manual for Integrated RMNCAH+N Counseling (2021),
  printed p.59 Table 9 (pregnancy), p.66 (postpartum).
- MoHFW, Training Manual on Newborn and Child Health Services for CHOs
  (2021), printed p.13 (0-2 month referral conditions).

This is NOT diagnosis, clinical triage, or a comprehensive safety screen.
"""
import re


# References are to PRINTED manual pages, not PDF viewer page indices.
# Prototype rule-to-source mapping; requires clinical review before deployment.
GUIDELINE_REFERENCES = {
    "pregnancy_bleeding": {"sign": "Bleeding during pregnancy", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 59},
    "pregnancy_convulsions": {"sign": "Convulsions during pregnancy", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 59},
    "pregnancy_headache_vision": {"sign": "Severe headache with blurred vision", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 59},
    "pregnancy_reduced_fetal_movement": {"sign": "Reduced or absent fetal movement", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 59},
    "pregnancy_fluid_leak": {"sign": "Fluid leaking during pregnancy", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 59},
    "postpartum_excessive_bleeding": {"sign": "Excessive postpartum bleeding", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 66},
    "postpartum_convulsions": {"sign": "Postpartum convulsions", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 66},
    "postpartum_breathing_difficulty": {"sign": "Postpartum breathing difficulty", "document": "Reference Manual for Integrated RMNCAH+N Counseling (2021)", "page": 66},
    "newborn_high_fever": {"sign": "Young infant elevated temperature", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
    "newborn_low_temperature": {"sign": "Young infant low temperature", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
    "newborn_feeding_difficulty": {"sign": "Young infant feeding difficulty", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
    "newborn_breathing_difficulty": {"sign": "Young infant fast or difficult breathing", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
    "newborn_chest_indrawing": {"sign": "Young infant chest indrawing", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
    "newborn_convulsions": {"sign": "Young infant convulsions", "document": "Training Manual on Newborn and Child Health Services for CHOs (2021)", "page": 22},
}

def _contains(text, phrases):
    return any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", text) for p in phrases)


def _positive(text, phrases):
    """Reject simple nearby English negation; uncertain statements remain flags."""
    for phrase in phrases:
        for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
            prefix = text[max(0, match.start() - 35):match.start()]
            # Avoid ignoring a symptom when 'no' refers to an earlier clause.
            prefix = re.split(r"[.,;!?]|\bbut\b|\bhowever\b", prefix)[-1]
            if re.search(r"\b(?:no|not|without|denies|denied)\s+(?:(?:any|signs? of|history of)\s+)?$", prefix):
                continue
            return True
    return False


def _temperature_c(text):
    match = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*°?\s*(c|f|celsius|fahrenheit)\b", text)
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2).startswith("f"):
        value = (value - 32) * 5 / 9
    # Reject implausible readings rather than producing false clinical alerts.
    return value if 25 <= value <= 45 else None


def _breaths_per_minute(text):
    patterns = [
        r"\b(?:respiratory rate|breathing rate|respirations|rr)\s*(?:is|of|:|=)?\s*(\d{2,3})\s*(?:/\s*min|per minute|bpm)?\b",
        r"\b(\d{2,3})\s*(?:breaths|respirations)\s*(?:per minute|/\s*min)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def detect_danger_signs(text, visit_type=None):
    """Return zero or more alert dictionaries for the existing WebSocket flow.

    `visit_type` is an optional previously established visit context.
    Absence of alerts does NOT establish that the patient is safe.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    text = text.casefold()
    context = (visit_type or "").casefold()

    pregnancy = context == "pregnancy" or _contains(text, [
        "pregnant", "pregnancy", "antenatal", "garbhavati", "गर्भवती",
        "गर्भावस्था", "ಗರ್ಭಿಣಿ", "ಗರ್ಭಾವಸ್ಥೆ",
    ])
    newborn = context == "newborn" or _contains(text, [
        "newborn", "new born", "neonate", "neonatal", "young infant",
        "नवजात", "नवजात शिशु", "ನವಜಾತ", "ಹಸುಗೂಸು",
    ])
    postpartum = context in {"postpartum", "postnatal", "maternal_postpartum"} or _contains(text, [
        "postpartum", "postnatal mother", "after delivery", "after childbirth", "delivered baby",
    ])

    # If a mother and baby are mentioned together, assess both contexts.
    alerts = []
    def add(code, message):
        source = GUIDELINE_REFERENCES[code]
        alerts.append({
            "danger_type": code,
            "severity": "urgent",
            "message": message,
            "matched_sign": source["sign"],
            "guideline_document": source["document"],
            "guideline_page": source["page"],
            "recommended_action": message,
        })

    bleeding = _positive(text, [
        "bleeding", "bleed", "blood loss", "vaginal bleeding", "रक्तस्राव",
        "खून बह", "ರಕ್ತಸ್ರಾವ", "ರಕ್ತ ಬರುತ್ತ",
    ])
    convulsions = _positive(text, ["convulsions", "convulsion", "fits", "seizure", "seizures"])
    difficulty_breathing = _positive(text, [
        "difficulty breathing", "difficult breathing", "breathing difficulty",
        "trouble breathing", "fast breathing", "rapid breathing", "shortness of breath",
    ])

    if pregnancy:
        if bleeding:
            add("pregnancy_bleeding", "Danger sign: bleeding during pregnancy. Arrange urgent assessment at an appropriate health facility and contact the local referral service.")
        if convulsions:
            add("pregnancy_convulsions", "Danger sign: convulsions during pregnancy. Arrange immediate emergency referral.")
        if _positive(text, ["severe headache", "bad headache"]) and _positive(text, [
            "blurred vision", "blurry vision", "visual disturbance",
        ]):
            add("pregnancy_headache_vision", "Danger sign: headache with blurred vision during pregnancy. Arrange urgent facility assessment.")
        if (_positive(text, ["reduced fetal movement", "decreased fetal movement", "baby not moving", "baby stopped moving"])
                or _contains(text, ["no fetal movement", "no baby movement"])):
            add("pregnancy_reduced_fetal_movement", "Danger sign: reduced or absent fetal movement. Arrange urgent facility assessment.")
        if _positive(text, ["leaking fluid", "leaking water", "water leaking", "waters broke", "fluid leaking"]):
            add("pregnancy_fluid_leak", "Possible leaking of fluid during pregnancy. Arrange prompt assessment at an appropriate health facility.")

    if postpartum:
        if bleeding and _positive(text, ["heavy", "excessive", "severe", "soaking", "a lot", "bleeding heavily", "heavy bleeding", "excessive bleeding"]):
            add("postpartum_excessive_bleeding", "Danger sign: excessive bleeding after childbirth. Seek immediate medical assessment.")
        if convulsions:
            add("postpartum_convulsions", "Danger sign: convulsions after childbirth. Seek immediate medical assessment.")
        if difficulty_breathing:
            add("postpartum_breathing_difficulty", "Danger sign: breathing difficulty after childbirth. Seek immediate medical assessment.")

    if newborn:
        temp = _temperature_c(text)
        fever_words = _positive(text, [
            "fever", "high fever", "very high fever", "hot to touch", "तेज बुखार",
            "बहुत बुखार", "बुखार", "ತೀವ್ರ ಜ್ವರ", "ಹೆಚ್ಚು ಜ್ವರ", "ಜ್ವರ",
        ])
        # MoHFW CHO manual p.13: axillary >=37.5C or <35.5C for age 0-2 months.
        if fever_words or (temp is not None and temp >= 37.5):
            add("newborn_high_fever", "Danger sign: fever or elevated temperature in a newborn/young infant. Arrange urgent medical assessment at an appropriate health facility.")
        if (temp is not None and temp < 35.5) or _positive(text, [
            "cold to touch", "baby is cold", "very cold baby", "hypothermia",
        ]):
            add("newborn_low_temperature", "Danger sign: low body temperature in a newborn/young infant. Arrange urgent medical assessment.")
        if _positive(text, [
            "not feeding", "unable to feed", "cannot feed", "can't feed",
            "unable to breastfeed", "cannot breastfeed", "not breastfeeding",
            "difficulty feeding", "poor feeding", "refusing feeds", "refuses feeds",
        ]):
            add("newborn_feeding_difficulty", "Danger sign: feeding difficulty in a newborn/young infant. Arrange urgent medical assessment.")
        rate = _breaths_per_minute(text)
        if difficulty_breathing or (rate is not None and rate >= 60):
            add("newborn_breathing_difficulty", "Danger sign: difficult or fast breathing in a newborn/young infant. Arrange urgent medical assessment.")
        if _positive(text, ["severe chest indrawing", "chest indrawing", "chest retractions"]):
            add("newborn_chest_indrawing", "Danger sign: chest indrawing in a newborn/young infant. Arrange urgent medical assessment.")
        if convulsions:
            add("newborn_convulsions", "Danger sign: convulsions in a newborn/young infant. Arrange immediate emergency referral.")

    return alerts
