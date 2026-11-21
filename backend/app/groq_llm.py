
import os

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

SYSTEM_PROMPT = """
You are SAHAYAK AI, a multilingual assistant for ASHA workers.

Your task is to understand home-visit notes in Kannada,
Hindi, English, and code-mixed speech.

Respond naturally and briefly in the worker's language.

You may help identify:
- Beneficiary ID and name
- Visit type
- Weight in kilograms
- Vaccinations due
- Next visit date
- Spoken corrections

Do not invent missing information.
Ask a clarification question when needed.

Never claim that a record was saved unless the backend
explicitly confirms the database transaction.

Do not diagnose, prescribe treatment, or dismiss danger signs.
The backend independently handles urgent safety referrals.
"""

client = AsyncGroq(
    api_key=os.environ.get("GROQ_API_KEY"),
    timeout=15.0,
    max_retries=1,
)


async def generate_reply(
    user_text: str,
    history: list[dict] | None = None,
) -> str:
    model = os.environ.get("GROQ_MODEL")

    if not model:
        raise RuntimeError("GROQ_MODEL is not configured")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(history or []),
        {"role": "user", "content": user_text},
    ]

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_completion_tokens=180,
    )

    return response.choices[0].message.content or ""
