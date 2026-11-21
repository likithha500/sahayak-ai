
from .database import match_beneficiary, save_visit
from .groq_llm import extract_visit
from .schemas import VisitExtraction


def normalize(text):
    return " ".join(text.casefold().strip().split()).rstrip(".!?")


YES_WORDS = {
    "yes", "yes save", "yes save it",
    "save it", "confirm", "confirmed",
    "ಹೌದು", "ಹೌದು ಸೇವ್ ಮಾಡಿ",
    "हाँ", "हां", "हाँ सेव करो",
}

NO_WORDS = {
    "no", "don't save", "do not save",
    "cancel", "discard", "ಇಲ್ಲ", "ಬೇಡ",
    "नहीं", "मत सेव करो",
}


class VisitSession:
    def __init__(self):
        self.pending_alert_ids = set()
        self.reset_draft()

    def reset_draft(self):
        self.draft = VisitExtraction()
        self.beneficiary = None
        self.candidates = []
        self.awaiting_confirmation = False

    def draft_data(self):
        return self.draft.model_dump(mode="json")

    def readback(self):
        beneficiary = self.beneficiary

        parts = [
            f"{beneficiary['name']}, "
            f"ID {beneficiary['beneficiary_id']}, "
            f"village {beneficiary['village']}"
        ]

        if self.draft.visit_type:
            parts.append(f"visit type {self.draft.visit_type}")

        if self.draft.weight_kg is not None:
            parts.append(
                f"weight {self.draft.weight_kg} kilograms"
            )

        if self.draft.vaccinations_due is not None:
            vaccines = self.draft.vaccinations_due
            parts.append(
                "vaccinations due "
                + (", ".join(vaccines) if vaccines else "none")
            )

        if self.draft.next_visit_date:
            parts.append(
                "next visit "
                + self.draft.next_visit_date.isoformat()
            )

        return (
            "Draft not saved. "
            + ", ".join(parts)
            + ". Is this correct? Say yes to save, "
            "or tell me what to correct."
        )

    def resolve_candidate(self, text):
        spoken = normalize(text)

        matches = [
            candidate for candidate in self.candidates
            if (
                candidate["village"].casefold() in spoken
                or candidate["beneficiary_id"].casefold() in spoken
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
            "message": message,
        }

    async def process_turn(self, text):
        spoken = normalize(text)

        # Confirmation is accepted only after a readback.
        if self.awaiting_confirmation and spoken in YES_WORDS:
            if self.pending_alert_ids:
                return {
                    "type": "agent_reply",
                    "text": (
                        "An urgent alert needs acknowledgement "
                        "before this visit can be saved."
                    ),
                }

            if not self.beneficiary or not self.draft.visit_type:
                return {
                    "type": "agent_reply",
                    "text": "The visit is incomplete. Nothing was saved.",
                }

            visit_id = save_visit(
                self.beneficiary["beneficiary_id"],
                self.draft,
            )

            result = {
                "type": "visit_saved",
                "visit_id": visit_id,
                "beneficiary_id": self.beneficiary["beneficiary_id"],
                "message": "Visit saved successfully.",
            }

            self.reset_draft()
            return result

        if spoken in {"cancel", "discard"}:
            self.reset_draft()
            return {
                "type": "agent_reply",
                "text": "Draft discarded. Nothing was saved.",
            }

        if self.awaiting_confirmation and spoken in NO_WORDS:
            self.awaiting_confirmation = False
            return {
                "type": "agent_reply",
                "text": (
                    "Nothing was saved. "
                    "Tell me what needs correcting."
                ),
            }

        # A short village or ID response can resolve ambiguity.
        if self.candidates and self.resolve_candidate(text):
            if not self.draft.visit_type:
                return self.make_draft_result(
                    "Which type of visit was this?"
                )

            self.awaiting_confirmation = True
            return self.make_draft_result(self.readback())

        # Extract fields from the new utterance.
        extracted = await extract_visit(text)
        updates = extracted.model_dump(exclude_none=True)

        beneficiary_id = updates.get("beneficiary_id")
        beneficiary_name = updates.get("beneficiary_name")

        if beneficiary_id or beneficiary_name:
            match = match_beneficiary(
                beneficiary_id,
                beneficiary_name,
            )

            if match["status"] == "matched":
                self.beneficiary = match["matches"][0]
                self.candidates = []

            elif match["status"] == "ambiguous":
                self.beneficiary = None
                self.candidates = match["matches"]

            else:
                self.beneficiary = None
                self.candidates = []
                self.awaiting_confirmation = False
                return {
                    "type": "agent_reply",
                    "text": match["message"],
                }

        # Apply only fields explicitly present in this turn.
        # Example: "Actually weight is 3.2 kg"
        for field in (
            "visit_type",
            "weight_kg",
            "vaccinations_due",
            "next_visit_date",
        ):
            if field in updates:
                setattr(self.draft, field, updates[field])

        self.awaiting_confirmation = False

        if self.candidates:
            choices = "; ".join(
                f"{item['name']} from {item['village']}, "
                f"ID {item['beneficiary_id']}"
                for item in self.candidates
            )

            return {
                "type": "beneficiary_clarification",
                "candidates": self.candidates,
                "visit": self.draft_data(),
                "saved": False,
                "message": (
                    f"Multiple beneficiaries found: {choices}. "
                    "Please say the village or ID."
                ),
            }

        if not self.beneficiary:
            return self.make_draft_result(
                "Please say the beneficiary name or ID. "
                "Nothing has been saved."
            )

        if not self.draft.visit_type:
            return self.make_draft_result(
                "Which type of visit was this? "
                "Nothing has been saved."
            )

        self.awaiting_confirmation = True
        return self.make_draft_result(self.readback())
