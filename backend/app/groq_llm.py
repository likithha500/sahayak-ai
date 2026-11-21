
import json
import os

from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from groq import AsyncGroq

from .schemas import VisitExtraction


load_dotenv(
    Path(__file__).resolve().parents[1] / ".env"
)

client = AsyncGroq(
    api_key=os.environ.get("GROQ_API_KEY"),
    timeout=15.0,
    max_retries=1,
)


SYSTEM_PROMPT = """
You are SAHAYAK AI, an intelligent multilingual
conversational field-visit assistant for ASHA workers.

You understand Kannada, Hindi, English, and
code-mixed speech.

You are connected to a real backend that can:
- Match beneficiaries against a database.
- Extract structured visit information.
- Maintain visit drafts.
- Accept corrections.
- Save explicitly confirmed visits.

CONVERSATION RULES:

Respond naturally in the worker's spoken language.

Keep spoken responses short and conversational.
Usually use one or two sentences.

Ask only one relevant question at a time.

Remember information that has already been provided.

Do not unnecessarily repeat questions.

Do not invent beneficiary names, measurements,
vaccinations, symptoms, or dates.

Follow the current backend visit state.

When the backend provides the next question,
ask that question naturally in the worker's language.

Do not introduce additional required fields that
the backend cannot record.

Accept corrections patiently.

If a measurement is unavailable, allow the worker
to skip it instead of inventing a value.

SAVING RULES:

SAHAYAK can save visits after review and confirmation.

Never claim that SAHAYAK lacks saving functionality.

Never redirect the worker to a different ASHA app.

Never claim that an unsaved draft has been saved.

The backend is the authority for validation,
confirmation, and database persistence.

Only report successful saving if the backend
explicitly confirms that saving succeeded.

Do not invent a visit ID or database result.

SAFETY RULES:

Do not diagnose medical conditions.

Do not prescribe medication or treatment.

Do not dismiss or minimize danger signs.

Follow backend safety and referral instructions.

Never invent clinical measurements or guidelines.

Never treat acknowledgement of a safety alert
as proof that a referral was completed.

Be supportive, clear, and professional.
"""


EXTRACTION_PROMPT = """
Extract structured information from an ASHA
home-visit conversation.

Return ONLY a valid JSON object with these exact keys:

{
  "beneficiary_id": null,
  "beneficiary_name": null,
  "visit_type": null,
  "weight_kg": null,
  "vaccinations_due": null,
  "next_visit_date": null
}

EXTRACTION RULES:

- Extract only information explicitly supplied
  by the worker.

- Never invent an ID, name, weight, vaccine, or date.

- Missing or uncertain fields must be null.

- beneficiary_id must preserve the identifier
  supplied by the worker.

- beneficiary_name must refer to the beneficiary,
  not the ASHA worker.

- visit_type must be one of:
  pregnancy, newborn, child, postnatal,
  general, or null.

- weight_kg must be a number in kilograms,
  or null.

- Convert explicitly stated grams to kilograms.

- Never confuse age, pregnancy months,
  blood pressure, or temperature with weight.

- Recognize numbers spoken in words in
  Kannada, Hindi, and English.

- vaccinations_due must be a list of vaccine
  names explicitly stated as due, otherwise null.

- If the worker explicitly says no vaccinations
  are due, return an empty list.

- Do not assume that vaccinations are due
  based on age or pregnancy stage.

- next_visit_date must be YYYY-MM-DD or null.

- Resolve clear relative dates using the
  supplied current date.

- Do not assume a date when the date is
  missing or uncertain.

- Recognize explicitly stated corrections.

- Extract the corrected value instead of
  the previous incorrect value.

- Never extract measurements or patient
  information from a question alone.

- Never interpret agreement or confirmation
  as new beneficiary information.

- Use the expected field only to interpret
  short and unambiguous answers.

- If the expected field is weight_kg and
  the worker clearly answers with a number,
  interpret it in kilograms.

- If the expected field is beneficiary,
  recognize a clearly supplied name or ID.

- Do not force unrelated answers into
  the expected field.

- If information is unavailable, skipped,
  or unknown, return null for that field.

- Output JSON only, without markdown
  or commentary.
"""


def get_model() -> str:
    model = os.environ.get("GROQ_MODEL")

    if not model:
        raise RuntimeError(
            "GROQ_MODEL is not configured"
        )

    return model


async def generate_reply(
    user_text: str,
    history: list[dict] | None = None,
) -> str:

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        *(history or []),
        {
            "role": "user",
            "content": user_text,
        },
    ]

    response = await client.chat.completions.create(
        model=get_model(),
        messages=messages,
        temperature=0.2,
        max_completion_tokens=220,
    )

    return (
        response.choices[0].message.content or ""
    ).strip()


async def extract_visit(
    user_text: str,
    expected_field: str | None = None,
) -> VisitExtraction:

    context = (
        f"Current date: {date.today().isoformat()}\n"
        f"Expected field: "
        f"{expected_field or 'unspecified'}\n"
        f"Worker's transcript:\n{user_text}"
    )

    response = await client.chat.completions.create(
        model=get_model(),
        messages=[
            {
                "role": "system",
                "content": EXTRACTION_PROMPT,
            },
            {
                "role": "user",
                "content": context,
            },
        ],
        temperature=0,
        max_completion_tokens=500,
        response_format={
            "type": "json_object"
        },
    )

    raw_content = (
        response.choices[0].message.content
    )

    if not raw_content:
        raise ValueError(
            "Groq returned an empty extraction"
        )

    extracted_data = json.loads(raw_content)

    if not isinstance(extracted_data, dict):
        raise ValueError(
            "Groq returned an invalid JSON structure"
        )

    return VisitExtraction.model_validate(
        extracted_data
    )
