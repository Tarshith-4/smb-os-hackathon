"""Strict payload schemas for every write action. Applied on prepare, edit and approve."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, ValidationError, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_INVOICE_INR = 10_000_000


class EmailPayload(BaseModel):
    to: str
    subject: str = Field(min_length=1, max_length=220)
    body: str = Field(min_length=5, max_length=5000)
    email_id: int | None = None

    @field_validator("to")
    @classmethod
    def _valid_to(cls, v: str) -> str:
        if not _EMAIL.match(v.strip()):
            raise ValueError("recipient is not a valid email address")
        return v.strip()


class InvoicePayload(BaseModel):
    customer_id: int
    amount: int = Field(gt=0, le=MAX_INVOICE_INR)
    description: str = Field(min_length=2, max_length=220)


class MeetingPayload(BaseModel):
    customer_id: int
    customer: str | None = None
    title: str = Field(min_length=2, max_length=220)
    starts_at: str
    duration_minutes: int = Field(default=30, ge=10, le=240)
    location: str = Field(default="Video call", max_length=180)
    notes: str = Field(default="", max_length=2000)

    @field_validator("starts_at")
    @classmethod
    def _valid_start(cls, v: str) -> str:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


_MODELS = {"SEND_EMAIL": EmailPayload, "CREATE_INVOICE": InvoicePayload, "SCHEDULE_MEETING": MeetingPayload}


def validate_payload(action_type: str, payload: dict) -> dict:
    """Return the normalized payload or raise ValueError with a readable message."""
    model = _MODELS.get(action_type)
    if model is None:
        raise ValueError(f"Unsupported action type: {action_type}")
    try:
        return model(**payload).model_dump(exclude_none=True)
    except (ValidationError, TypeError, ValueError) as exc:
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()) if isinstance(exc, ValidationError) else str(exc)
        raise ValueError(f"Invalid {action_type} payload: {detail}") from exc
