
from .database import match_beneficiary, save_visit
from .groq_llm import extract_visit
from .schemas import VisitExtraction
import uuid


def normalize(text):
    cleaned = (
        text.casefold()
        .replace(",", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace(".", " ")
        .replace("।", " ")
        .replace("-", " ")
    )
    return " ".join(cleaned.strip().split())


def is_premature_save_request(text):
    spoken = normalize(text)
    return (
        "save this visit" in spoken
        or "save the visit" in spoken
        or "confirm and save" in spoken
        or "save now" in spoken
        or "record this visit" in spoken
        or spoken in {"save", "save it", "save please"}
    )


YES_WORDS = {
    "yes",
    "yes save",
    "yes save it",
    "yes please save it",
    "save it",
    "save the visit",
    "confirm",
    "confirmed",
    "ಹೌದು",
    "ಹೌದು ಸೇವ್ ಮಾಡಿ",
    "ಉಳಿಸಿ",
    "हाँ",
    "हां",
    "हाँ सेव करो",
    "सेव कर दो",
}

NO_WORDS = {
    "no",
    "don't save",
    "do not save",
    "cancel",
    "discard",
    "ಇಲ್ಲ",
    "ಬೇಡ",
    "नहीं",
    "मत सेव करो",
    "ಇಲ್ಲ ಉಳಿಸಬೇಡ",
    "मत बचाओ",
}

SKIP_WORDS = {
    "skip",
    "not available",
    "not measured",
    "not applicable",
    "i don't know",
    "unknown",
    "ಗೊತ್ತಿಲ್ಲ",
    "ಲಭ್ಯವಿಲ್ಲ",
    "पता नहीं",
    "उपलब्ध नहीं",
}


class VisitSession:

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.language = "kn-IN"
        self.pending_alert_ids = set()
        self.alert_ids = set()
        self.saved_visit_id = None
        self.draft_version = 0
        self.reset_draft()

    def reset_draft(self):
        self.draft = VisitExtraction()
        self.beneficiary = None
        self.candidates = []
        self.awaiting_confirmation = False
        self.current_question = None
        self.skipped_fields = set()
        self.saved_visit_id = None
        self.draft_version += 1

    def draft_data(self):
        data = self.draft.model_dump(mode="json")

        if self.beneficiary:
            data["beneficiary_id"] = (
                self.beneficiary["beneficiary_id"]
            )

            data["beneficiary_name"] = (
                self.beneficiary["name"]
            )

        return data

    def set_initial_beneficiary(self, beneficiary_id):
        match = match_beneficiary(beneficiary_id=beneficiary_id)
        if match["status"] == "matched":
            previous_id = (
                self.beneficiary["beneficiary_id"]
                if self.beneficiary else None
            )
            self.beneficiary = match["matches"][0]
            if previous_id and previous_id != beneficiary_id:
                self.draft = VisitExtraction()
                self.skipped_fields.clear()
                self.awaiting_confirmation = False
            self.draft_version += 1
            return True
        return False

    def readback(self):
        beneficiary = self.beneficiary

        parts = [
            f"{beneficiary['name']}, "
            f"ID {beneficiary['beneficiary_id']}, "
            f"village {beneficiary['village']}"
        ]

        if self.draft.visit_type:
            parts.append(
                f"visit type {self.draft.visit_type}"
            )

        if self.draft.weight_kg is not None:
            parts.append(
                f"weight {self.draft.weight_kg} kilograms"
            )
        else:
            parts.append("weight not recorded")

        if self.draft.vaccinations_due is not None:
            vaccines = self.draft.vaccinations_due

            parts.append(
                "vaccinations due "
                + (
                    ", ".join(vaccines)
                    if vaccines
                    else "none"
                )
            )
        else:
            parts.append(
                "vaccination information not recorded"
            )

        if self.draft.next_visit_date:
            parts.append(
                "next visit "
                + self.draft.next_visit_date.isoformat()
            )
        else:
            parts.append("next visit date not recorded")

        return (
            "Here is your visit summary. "
            + ", ".join(parts)
            + ". Nothing has been saved yet. "
            "Is everything correct? "
            "Say yes to save, or tell me what to correct."
        )

    def resolve_candidate(self, text):
        spoken = normalize(text)

        matches = [
            candidate
            for candidate in self.candidates
            if (
                candidate["village"].casefold() in spoken
                or candidate["beneficiary_id"].casefold()
                in spoken
            )
        ]

        if len(matches) != 1:
            return False

        self.beneficiary = matches[0]
        self.candidates = []

        return True

    def make_draft_result(self, message):
        return {
            "type": "visit_draft",
            "visit": self.draft_data(),
            "beneficiary": self.beneficiary,
            "saved": False,
            "awaiting_confirmation": (
                self.awaiting_confirmation
            ),
            "current_question": self.current_question,
            "skipped_fields": sorted(self.skipped_fields),
            "message": message,
        }

    def next_question(self):
        self.awaiting_confirmation = False

        if not self.beneficiary:
            self.current_question = "beneficiary"

            return self.make_draft_result(
                "Could you tell me the beneficiary's "
                "name or ID?"
            )

        if not self.draft.visit_type:
            self.current_question = "visit_type"

            return self.make_draft_result(
                "What type of visit are you conducting? "
                "Is it a pregnancy, newborn, child, "
                "postnatal, or general visit?"
            )

        if (
            self.draft.weight_kg is None
            and "weight_kg" not in self.skipped_fields
        ):
            self.current_question = "weight_kg"

            return self.make_draft_result(
                f"What is {self.beneficiary['name']}'s "
                "weight in kilograms? "
                "If the weight was not measured, "
                "you can say skip."
            )

        if (
            self.draft.vaccinations_due is None
            and "vaccinations_due"
            not in self.skipped_fields
        ):
            self.current_question = "vaccinations_due"

            return self.make_draft_result(
                "Are any vaccinations due? "
                "If none are due, say no vaccinations due. "
                "If unknown or not applicable, say skip."
            )

        if (
            self.draft.next_visit_date is None
            and "next_visit_date"
            not in self.skipped_fields
        ):
            self.current_question = "next_visit_date"

            return self.make_draft_result(
                "When is the next scheduled visit? "
                "If it has not been scheduled, say skip."
            )

        if self.pending_alert_ids:
            self.current_question = "safety_alert"

            return self.make_draft_result(
                "Please review and acknowledge the "
                "urgent safety alert before saving "
                "this visit."
            )

        self.current_question = "confirmation"
        self.awaiting_confirmation = True

        return self.make_draft_result(
            self.readback()
        )

    async def process_turn(self, text):
        spoken = normalize(text)

        # Repeated confirmation must not create or resubmit a visit.
        if (
            self.saved_visit_id is not None
            and spoken in YES_WORDS
        ):
            return {
                "type": "agent_reply",
                "text": (
                    "This visit is already saved successfully "
                    f"with visit ID {self.saved_visit_id}. "
                    "No duplicate record was created."
                ),
            }

        # A completed session can start a fresh draft naturally.
        if self.saved_visit_id is not None:
            if (
                "new visit" in spoken
                or "another visit" in spoken
                or "ಹೊಸ ಭೇಟಿ" in spoken
                or "नया विज़िट" in spoken
                or "नई विज़िट" in spoken
            ):
                self.reset_draft()
                return self.next_question()

        # A save request is not confirmation until the draft
        # has been reviewed and the session is awaiting confirmation.
        if (
            is_premature_save_request(text)
            and not self.awaiting_confirmation
        ):
            missing = self.next_question()
            missing_message = missing.get("message", "")
            return self.make_draft_result(
                "This visit has not been reviewed or confirmed yet. "
                "Nothing has been saved. " + missing_message
            )

        # Save only after explicit confirmation.
        if (
            self.awaiting_confirmation
            and spoken in YES_WORDS
        ):
            if self.pending_alert_ids:
                return {
                    "type": "agent_reply",
                    "text": (
                        "An urgent safety alert requires "
                        "acknowledgement before saving."
                    ),
                }

            if (
                not self.beneficiary
                or not self.draft.visit_type
            ):
                self.awaiting_confirmation = False

                return self.make_draft_result(
                    "The visit is incomplete. "
                    "Nothing has been saved."
                )

            try:
                visit_id = save_visit(
                    self.beneficiary["beneficiary_id"],
                    self.draft,
                    idempotency_key=(
                        f"{self.session_id}:{self.draft_version}"
                    ),
                    alert_ids=tuple(self.alert_ids),
                )
            except Exception:
                self.awaiting_confirmation = True
                return self.make_draft_result(
                    "The visit could not be saved because of a "
                    "database error. The reviewed draft is preserved. "
                    "Please retry confirmation."
                )

            self.saved_visit_id = visit_id

            result = {
                "type": "visit_saved",
                "visit_id": visit_id,
                "beneficiary_id": (
                    self.beneficiary["beneficiary_id"]
                ),
                "beneficiary": self.beneficiary,
                "visit": self.draft_data(),
                "saved": True,
                "message": (
                    "Visit saved successfully. "
                    "Thank you for completing "
                    "the household visit."
                ),
            }

            self.reset_draft()
            self.saved_visit_id = visit_id

            return result

        # A save request without readback is not confirmation.
        if (
            spoken in YES_WORDS
            and not self.awaiting_confirmation
            and self.current_question is None
        ):
            return self.make_draft_result(
                "Let's collect and review the visit "
                "details before saving. "
                "Please tell me the beneficiary name or ID."
            )

        # Discard an unsaved draft.
        if spoken in {"cancel", "discard"}:
            if self.pending_alert_ids:
                return self.make_draft_result(
                    "Please review the urgent safety "
                    "alert before discarding this draft."
                )

            self.reset_draft()

            return self.make_draft_result(
                "Draft discarded. Nothing was saved."
            )

        # Reject confirmation and request corrections.
        if (
            self.awaiting_confirmation
            and spoken in NO_WORDS
        ):
            self.awaiting_confirmation = False
            self.current_question = "correction"

            return self.make_draft_result(
                "Nothing has been saved. "
                "Tell me which information "
                "you would like to correct."
            )

        # Resolve ambiguous beneficiary identities.
        if self.candidates:
            if self.resolve_candidate(text):
                return self.next_question()

        # Allow unavailable optional information.
        optional_fields = {
            "weight_kg",
            "vaccinations_due",
            "next_visit_date",
        }

        if (
            spoken in SKIP_WORDS
            and self.current_question in optional_fields
        ):
            self.skipped_fields.add(
                self.current_question
            )

            return self.next_question()

        # Handle an explicit absence of due vaccinations.
        if (
            self.current_question == "vaccinations_due"
            and spoken in {
                "no",
                "none",
                "no vaccinations due",
                "no vaccines due",
                "ಇಲ್ಲ",
                "ಯಾವುದೂ ಇಲ್ಲ",
                "नहीं",
                "कोई नहीं",
            }
        ):
            self.draft.vaccinations_due = []

            self.skipped_fields.discard(
                "vaccinations_due"
            )

            return self.next_question()

        # Any new information invalidates old confirmation.
        was_awaiting_confirmation = (
            self.awaiting_confirmation
        )

        self.awaiting_confirmation = False

        # Extract information using the real Groq API.
        extracted = await extract_visit(
            text,
            expected_field=self.current_question,
        )

        updates = extracted.model_dump(
            exclude_none=True
        )

        beneficiary_id = updates.get(
            "beneficiary_id"
        )

        beneficiary_name = updates.get(
            "beneficiary_name"
        )

        # Apply explicitly provided visit information.
        for field in (
            "visit_type",
            "weight_kg",
            "vaccinations_due",
            "next_visit_date",
        ):
            if field in updates:
                setattr(
                    self.draft,
                    field,
                    updates[field],
                )

                self.skipped_fields.discard(field)
                self.draft_version += 1

        # Match the beneficiary against the real database.
        if beneficiary_id or beneficiary_name:
            match = match_beneficiary(
                beneficiary_id,
                beneficiary_name,
            )

            if match["status"] == "matched":
                next_beneficiary = match["matches"][0]
                previous_id = (
                    self.beneficiary["beneficiary_id"]
                    if self.beneficiary else None
                )
                if (
                    previous_id
                    and previous_id != next_beneficiary["beneficiary_id"]
                ):
                    self.draft = VisitExtraction()
                    self.skipped_fields.clear()
                self.beneficiary = next_beneficiary
                self.candidates = []
                self.draft_version += 1

            elif match["status"] == "ambiguous":
                self.beneficiary = None
                self.candidates = match["matches"]

            else:
                self.beneficiary = None
                self.candidates = []
                self.current_question = "beneficiary"

                return self.make_draft_result(
                    match["message"]
                )

        if self.candidates:
            choices = "; ".join(
                f"{item['name']} from "
                f"{item['village']}, "
                f"ID {item['beneficiary_id']}"
                for item in self.candidates
            )

            self.current_question = "beneficiary"

            return {
                "type": "beneficiary_clarification",
                "candidates": self.candidates,
                "visit": self.draft_data(),
                "saved": False,
                "message": (
                    f"Multiple beneficiaries found: "
                    f"{choices}. "
                    "Please say the village or ID."
                ),
            }

        # Do not silently interpret unclear corrections.
        if (
            not updates
            and (
                was_awaiting_confirmation
                or self.current_question == "correction"
            )
        ):
            self.current_question = "correction"

            return self.make_draft_result(
                "I did not identify a clear correction. "
                "Please tell me the field and its "
                "correct value, or say review again."
            ) if spoken != "review again" else (
                self.next_question()
            )

        # Continue collecting missing fields.
        return self.next_question()
