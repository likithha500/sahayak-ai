
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class VisitExtraction(BaseModel):
    beneficiary_id: str | None = None
    beneficiary_name: str | None = None
    visit_type: Literal[
        "pregnancy",
        "newborn",
        "child",
        "postnatal",
        "general",
    ] | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=300)
    vaccinations_due: list[str] | None = None
    next_visit_date: date | None = None

    @field_validator("beneficiary_id", "beneficiary_name")
    @classmethod
    def clean_text(cls, value: str | None):
        if value is None:
            return None
        return value.strip() or None


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    visit: VisitExtraction
    status: Literal["draft"] = "draft"
    saved: Literal[False] = False
