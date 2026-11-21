
import logging
import re
import unicodedata
import uuid

from .database import (
    create_beneficiary,
    find_possible_duplicates,
    match_beneficiary,
    save_visit,
)
from .groq_llm import (
    extract_beneficiary_registration,
    extract_visit,
)
from .schemas import (
    BeneficiaryCreate,
    BeneficiaryRegistrationExtraction,
    VisitExtraction,
)


logger = logging.getLogger(__name__)


def normalize(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(
        re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
        .strip()
        .split()
    )


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


AFFIRMATION_TOKENS = {
    "yes", "confirm", "confirmed", "save", "it", "please",
    "the", "visit", "record", "everything", "is", "all",
    "correct", "right", "go", "ahead", "okay", "ok", "and",
    "ಹೌದು", "ಉಳಿಸಿ", "ಮಾಡಿ", "ದಯವಿಟ್ಟು", "ಖಚಿತ", "ಸರಿ",
    "हाँ", "हां", "ठीक", "है", "कर", "दो", "सेव",
    "बचाओ", "सहेजें", "आगे", "बढ़ो",
}

NEGATION_TOKENS = {
    "no", "not", "never", "dont", "don", "t", "नहीं",
    "मत", "ಇಲ್ಲ", "ಬೇಡ", "ಬೇಡವೇ",
}

CORRECTION_TOKENS = {
    "but", "change", "correct", "correction", "actually",
    "instead", "update", "ಅಲ್ಲ", "ಬದಲಿಸಿ", "ತಿದ್ದು",
    "लेकिन", "बदलो", "सुधार",
}


def is_negative(text):
    tokens = normalize(text).split()
    return any(token in NEGATION_TOKENS for token in tokens)


def is_confirmation(text):
    tokens = normalize(text).split()
    if not tokens or is_negative(text):
        return False
    if any(token in CORRECTION_TOKENS for token in tokens):
        return False
    return (
        any(
            token in {
                "yes", "confirm", "confirmed", "save",
                "everything", "all", "go", "ಹೌದು", "हाँ",
                "हां", "ಸರಿ", "ठीक",
            }
            for token in tokens
        )
        and all(token in AFFIRMATION_TOKENS for token in tokens)
    )


def is_registration_intent(text):
    spoken = normalize(text)
    phrases = (
        "register new beneficiary",
        "register a new beneficiary",
        "i want to register",
        "add a new beneficiary",
        "add new beneficiary",
        "create a new beneficiary",
        "create new beneficiary",
        "add new patient",
        "register a new patient",
        "add a new mother",
        "register a newborn",
        "create new record",
        "create a new record",
        "add new record",
        "add a new record",
        "ಹೊಸ ಫಲಾನುಭವಿಯನ್ನು ನೋಂದಾಯಿಸಿ",
        "ಹೊಸ ಫಲಾನುಭವಿ ನೋಂದಣಿ",
        "ಹೊಸ ತಾಯಿಯನ್ನು ಸೇರಿಸಿ",
        "नया लाभार्थी पंजीकृत",
        "नया लाभार्थी जोड़ें",
        "नई मां जोड़ें",
        "नवजात पंजीकृत",
    )
    if any(phrase in spoken for phrase in phrases):
        return True

    words = set(spoken.split())
    return (
        "new" in words
        and "beneficiary" in words
        and bool(
            words.intersection(
                {"register", "registering", "add", "create"}
            )
        )
    )


def is_cancel_intent(text):
    return normalize(text) in {
        "cancel",
        "cancel registration",
        "cancel the registration",
        "discard",
        "ರದ್ದುಮಾಡಿ",
        "ರದ್ದು ಮಾಡಿ",
        "ರದ್ದುಗೊಳಿಸಿ",
        "रद्द करें",
        "रद्द करो",
        "रद्द",
    }


def is_review_intent(text):
    return normalize(text) in {
        "review",
        "review again",
        "review details",
        "show the details",
        "show the summary",
        "read the summary",
        "ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ",
        "ಮತ್ತೆ ಪರಿಶೀಲಿಸಿ",
        "विवरण की समीक्षा करें",
        "फिर से दिखाएं",
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
        self.workflow = "visit"
        self.registration_draft = (
            BeneficiaryRegistrationExtraction()
        )
        self.registration_skipped_fields = set()
        self.registration_candidates = []
        self.awaiting_registration_offer = False
        self.awaiting_registration_confirmation = False
        self.awaiting_first_visit_offer = False
        self.saved_visit_id = None
        self.draft_version = 0
        self.reset_draft()

    def reset_draft(self):
        self.draft = VisitExtraction()
        self.beneficiary = None
        self.candidates = []
        self.workflow = "visit"
        self.awaiting_registration_offer = False
        self.awaiting_registration_confirmation = False
        self.awaiting_first_visit_offer = False
        self.registration_candidates = []
        self.registration_draft = (
            BeneficiaryRegistrationExtraction()
        )
        self.registration_skipped_fields = set()
        self.awaiting_confirmation = False
        self.current_question = None
        self.skipped_fields = set()
        self.saved_visit_id = None
        self.pending_alert_ids.clear()
        self.alert_ids.clear()
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

    def registration_result(self, message, event_type=None):
        return {
            "type": (
                event_type or "beneficiary_registration_draft"
            ),
            "registration": self.registration_draft.model_dump(
                mode="json"
            ),
            "beneficiary": self.beneficiary,
            "candidates": self.registration_candidates,
            "saved": False,
            "awaiting_confirmation": (
                self.awaiting_registration_confirmation
            ),
            "current_question": self.current_question,
            "skipped_fields": sorted(
                self.registration_skipped_fields
            ),
            "message": message,
        }

    def start_registration(self, initial_name=None):
        self.workflow = "registration"
        self.saved_visit_id = None
        self.registration_draft = (
            BeneficiaryRegistrationExtraction(
                name=initial_name
            )
        )
        self.registration_skipped_fields = set()
        self.registration_candidates = []
        self.awaiting_registration_offer = False
        self.awaiting_registration_confirmation = False
        self.current_question = "registration_name"

    def next_registration_question(self):
        self.awaiting_registration_confirmation = False
        registration = self.registration_draft
        if not registration.name:
            self.current_question = "registration_name"
            return self.registration_result(
                "Certainly. What is the beneficiary's name?"
            )
        if not registration.village:
            self.current_question = "registration_village"
            return self.registration_result(
                f"Which village does {registration.name} live in?"
            )
        if (
            registration.age is None
            and "age" not in self.registration_skipped_fields
        ):
            self.current_question = "registration_age"
            return self.registration_result(
                f"How old is {registration.name}? "
                "You can say skip if unknown."
            )
        if not registration.category:
            self.current_question = "registration_category"
            return self.registration_result(
                "Which healthcare category applies: pregnancy, "
                "newborn, child, postnatal, or general?"
            )

        duplicates = find_possible_duplicates(
            registration.name,
            registration.village,
        )
        if duplicates:
            self.registration_candidates = duplicates
            self.current_question = "registration_duplicate"
            choices = "; ".join(
                f"{item['name']} from {item['village']}, "
                f"ID {item['beneficiary_id']}"
                for item in duplicates
            )
            return self.registration_result(
                "I found a similar registered beneficiary: "
                f"{choices}. Please verify the ID, or correct "
                "the name or village. I will not create a duplicate.",
                "beneficiary_registration_clarification",
            )

        self.registration_candidates = []
        self.current_question = "registration_confirmation"
        self.awaiting_registration_confirmation = True
        age_text = (
            f"age {registration.age}"
            if registration.age is not None
            else "age not provided"
        )
        return self.registration_result(
            f"I have {registration.name}, {age_text}, from "
            f"{registration.village}, registered under "
            f"{registration.category} care. Shall I save this "
            "new beneficiary?"
        )

    async def process_registration_turn(self, text):
        spoken = normalize(text)
        if is_cancel_intent(text):
            self.workflow = "visit"
            self.registration_draft = (
                BeneficiaryRegistrationExtraction()
            )
            self.awaiting_registration_offer = False
            self.awaiting_registration_confirmation = False
            self.current_question = "beneficiary"
            return {
                "type": "agent_reply",
                "text": (
                    "Registration cancelled. Nothing was saved. "
                    "Please provide a registered beneficiary name or ID."
                ),
            }

        if is_review_intent(text):
            return self.next_registration_question()

        if self.registration_candidates and not is_negative(text):
            compact_spoken = spoken.replace(" ", "")
            matches = [
                candidate
                for candidate in self.registration_candidates
                if candidate["beneficiary_id"]
                .casefold()
                .replace("-", "")
                in compact_spoken
            ]
            if len(matches) == 1:
                self.workflow = "visit"
                self.beneficiary = matches[0]
                self.registration_candidates = []
                self.registration_draft = (
                    BeneficiaryRegistrationExtraction()
                )
                self.current_question = None
                return self.next_question()

        if (
            self.awaiting_registration_confirmation
            and is_confirmation(text)
        ):
            try:
                payload = BeneficiaryCreate.model_validate(
                    self.registration_draft.model_dump(
                        exclude_none=True
                    )
                )
                result = create_beneficiary(
                    payload.name,
                    payload.village,
                    payload.category,
                    payload.age,
                )
            except Exception as exc:
                logger.exception(
                    "Beneficiary registration persistence failed "
                    "(error_type=%s)",
                    type(exc).__name__,
                )
                self.awaiting_registration_confirmation = True
                return self.registration_result(
                    "The beneficiary could not be saved because of a "
                    "database error. The reviewed details are preserved. "
                    "Please try confirming again."
                )

            if result["status"] == "duplicate":
                self.registration_candidates = result["matches"]
                self.awaiting_registration_confirmation = False
                return self.registration_result(
                    "A similar beneficiary was registered before this "
                    "record could be saved. Please verify the existing "
                    "ID or correct the name or village.",
                    "beneficiary_registration_clarification",
                )

            self.beneficiary = result["beneficiary"]
            self.workflow = "first_visit_offer"
            self.awaiting_registration_confirmation = False
            self.awaiting_first_visit_offer = True
            self.current_question = "first_visit_offer"
            return {
                "type": "beneficiary_created",
                "beneficiary": self.beneficiary,
                "saved": True,
                "message": (
                    f"{self.beneficiary['name']} has been registered "
                    "successfully. Their beneficiary ID is "
                    f"{self.beneficiary['beneficiary_id']}. "
                    "Would you like to record the first visit?"
                ),
            }

        if (
            self.awaiting_registration_confirmation
            and is_negative(text)
        ):
            self.awaiting_registration_confirmation = False
            self.current_question = "registration_correction"
            return self.registration_result(
                "Nothing has been saved. Tell me what to correct, "
                "or say review again."
            )

        if (
            self.awaiting_registration_confirmation
            and spoken == "review again"
        ):
            return self.next_registration_question()

        if (
            spoken in SKIP_WORDS
            and self.current_question == "registration_age"
        ):
            self.registration_skipped_fields.add("age")
            return self.next_registration_question()

        was_awaiting_confirmation = (
            self.awaiting_registration_confirmation
        )
        try:
            extracted = await extract_beneficiary_registration(
                text,
                expected_field=self.current_question,
            )
        except Exception as exc:
            logger.warning(
                "Beneficiary extraction failed (error_type=%s)",
                type(exc).__name__,
            )
            self.awaiting_registration_confirmation = (
                was_awaiting_confirmation
            )
            return self.registration_result(
                "I couldn't understand that registration detail. "
                "Please try again; nothing has been saved."
            )

        updates = extracted.model_dump(exclude_none=True)
        if updates:
            self.registration_draft = (
                self.registration_draft.model_copy(update=updates)
            )
            self.registration_skipped_fields.difference_update(
                updates
            )
            self.registration_candidates = []
            self.awaiting_registration_confirmation = False
        elif was_awaiting_confirmation:
            self.awaiting_registration_confirmation = True
            self.current_question = "registration_confirmation"
            return self.registration_result(
                "I didn't hear a clear correction. The details are still "
                "awaiting confirmation. Say yes to save or tell me what "
                "to change."
            )

        return self.next_registration_question()

    async def process_turn(self, text):
        spoken = normalize(text)

        if self.workflow == "registration":
            return await self.process_registration_turn(text)

        if self.workflow == "first_visit_offer":
            if is_confirmation(text):
                self.workflow = "visit"
                self.awaiting_first_visit_offer = False
                self.current_question = None
                return self.next_question()
            if is_negative(text) or is_cancel_intent(text):
                self.workflow = "visit"
                self.awaiting_first_visit_offer = False
                self.draft = VisitExtraction()
                self.current_question = None
                return {
                    "type": "agent_reply",
                    "text": (
                        "The beneficiary is registered. No visit was "
                        "started; you can begin one whenever you are ready."
                    ),
                }
            return {
                "type": "agent_reply",
                "text": (
                    "Would you like to record the first visit now? "
                    "Please say yes or no."
                ),
            }

        if self.awaiting_registration_offer:
            if is_confirmation(text):
                initial_name = self.registration_draft.name
                self.start_registration(initial_name)
                return await self.process_registration_turn(text)
            if is_negative(text):
                self.awaiting_registration_offer = False
                self.registration_draft = (
                    BeneficiaryRegistrationExtraction()
                )
                self.current_question = "beneficiary"
                return self.make_draft_result(
                    "Okay. I will not register anyone. Please provide "
                    "the registered beneficiary's full name or ID."
                )
            return {
                "type": "agent_reply",
                "text": (
                    "Would you like me to start a new beneficiary "
                    "registration? Please say yes or no."
                ),
            }

        if is_review_intent(text):
            return self.next_question()

        if is_registration_intent(text):
            self.start_registration()
            return await self.process_registration_turn(text)

        # Repeated confirmation must not create or resubmit a visit.
        if (
            self.saved_visit_id is not None
            and is_confirmation(text)
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
            and is_confirmation(text)
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
            is_confirmation(text)
            and not self.awaiting_confirmation
            and self.current_question is None
        ):
            return self.make_draft_result(
                "Let's collect and review the visit "
                "details before saving. "
                "Please tell me the beneficiary name or ID."
            )

        # Discard an unsaved draft.
        if is_cancel_intent(text):
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
            and is_negative(text)
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

                if (
                    match["status"] == "not_found"
                    and beneficiary_name
                    and not beneficiary_id
                ):
                    self.registration_draft = (
                        BeneficiaryRegistrationExtraction(
                            name=beneficiary_name
                        )
                    )
                    self.awaiting_registration_offer = True
                    return {
                        "type": "agent_reply",
                        "text": (
                            f"I couldn't find {beneficiary_name} in the "
                            "beneficiary register. Would you like to "
                            "register this person as a new beneficiary?"
                        ),
                    }

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
            if was_awaiting_confirmation:
                self.awaiting_confirmation = True
                self.current_question = "confirmation"
                return self.make_draft_result(
                    "I did not identify a clear correction. "
                    "The reviewed draft is still awaiting confirmation. "
                    "Say yes to save, or tell me what to correct."
                )
            self.current_question = "correction"
            return (
                self.next_question()
                if spoken == "review again"
                else self.make_draft_result(
                    "I did not identify a clear correction. "
                    "Please tell me the field and its correct value, "
                    "or say review again."
                )
            )

        # Continue collecting missing fields.
        return self.next_question()
