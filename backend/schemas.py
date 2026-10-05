"""Validated API request and response shapes."""

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    edited_payload: dict | None = None


class ApprovalEdit(BaseModel):
    payload: dict


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    customer_id: int | None = None


class TaskUpdate(BaseModel):
    status: str = Field(pattern="^(open|completed)$")
