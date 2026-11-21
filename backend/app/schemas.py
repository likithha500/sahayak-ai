
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class BeneficiaryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    village: str = Field(min_length=2, max_length=120)
    category: Literal[
        "pregnancy",
        "newborn",
        "child",
        "postnatal",
        "general",
    ]
    age: int | None = Field(default=None, ge=1, le=120)

    @field_validator("name", "village")
    @classmethod
    def clean_required_text(cls, value: str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank")
        return cleaned


class BeneficiaryRegistrationExtraction(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    category: Literal[
        "pregnancy",
        "newborn",
        "child",
        "postnatal",
        "general",
    ] | None = None
    age: int | None = Field(default=None, ge=1, le=120)

    @field_validator("name", "village")
    @classmethod
    def clean_optional_text(cls, value: str | None):
        if value is None:
            return None
        return value.strip() or None


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    visit: VisitExtraction
    status: Literal["draft"] = "draft"
    saved: Literal[False] = False


class FollowUpUpdate(BaseModel):
    scheduled_date: date | None = None
    status: Literal["pending", "completed"] | None = None

    @model_validator(mode="after")
    def require_update(self):
        if self.scheduled_date is None and self.status is None:
            raise ValueError("Provide a new date or follow-up status")
        return self


class ReferralStatusUpdate(BaseModel):
    status: Literal[
        "not_started",
        "referred",
        "follow_up_pending",
        "completed",
    ]
