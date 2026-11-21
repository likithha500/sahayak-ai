
import json
import os

from datetime import date

from dotenv import load_dotenv
from groq import AsyncGroq

from .schemas import VisitExtraction


load_dotenv()

client = AsyncGroq(
    api_key=os.environ.get("GROQ_API_KEY"),
    timeout=15.0,
    max_retries=1,
)

SYSTEM_PROMPT = """
You are SAHAYAK AI, a multilingual assistant for ASHA workers.

Understand Kannada, Hindi, English, and code-mixed visit notes.

Respond briefly and naturally in the worker's language.

Never claim a visit is recorded, registered, or saved.
The backend has not saved anything unless it explicitly confirms so.

Do not invent beneficiary information.
Ask for clarification when information is ambiguous.

Do not diagnose, prescribe treatment, or dismiss danger signs.
The backend handles urgent safety referrals.
"""

EXTRACTION_PROMPT = """
Extract structured information from an ASHA home-visit transcript.

Return ONLY a valid JSON object with these exact keys:
{
  "beneficiary_id": null,
  "beneficiary_name": null,
  "visit_type": null,
  "weight_kg": null,
  "vaccinations_due": null,
  "next_visit_date": null
}

Rules:
- Extract only information explicitly present in the transcript.
- Never invent an ID, name, weight, vaccine, or date.
- Missing or uncertain fields must be null.
- visit_type must be one of:
  pregnancy, newborn, child, postnatal, general, or null.
- weight_kg must be a number in kilograms, or null.
- vaccinations_due must be a list of vaccine names if explicitly
  mentioned as due, otherwise null.
- next_visit_date must be YYYY-MM-DD or null.
- Do not assume today's date for an unspecified date.
- Preserve beneficiary IDs exactly as spoken.
- Output JSON only, without markdown or commentary.
"""


def get_model() -> str:
    model = os.environ.get("GROQ_MODEL")
    if not model:
        raise RuntimeError("GROQ_MODEL is not configured")
    return model


async def generate_reply(
    user_text: str,
    history: list[dict] | None = None,
) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(history or []),
        {"role": "user", "content": user_text},
    ]

    response = await client.chat.completions.create(
        model=get_model(),
        messages=messages,
        temperature=0.2,
        max_completion_tokens=180,
    )

    return response.choices[0].message.content or ""


async def extract_visit(user_text: str) -> VisitExtraction:
    response = await client.chat.completions.create(
        model=get_model(),
        messages=[
            {
                "role": "system",
                "content": EXTRACTION_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Current date: {date.today().isoformat()}\n"
                    f"Transcript:\n{user_text}"
                ),
            },
        ],
        temperature=0,
        max_completion_tokens=500,
        response_format={"type": "json_object"},
    )

    raw_content = response.choices[0].message.content

    if not raw_content:
        raise ValueError("Qwen returned an empty extraction")

    extracted_data = json.loads(raw_content)

    if not isinstance(extracted_data, dict):
        raise ValueError("Qwen returned an invalid JSON structure")

    return VisitExtraction.model_validate(extracted_data)
