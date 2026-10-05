"""Persistent business and agent records for the SMB OS MVP."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    company: Mapped[str] = mapped_column(String(140), index=True)
    email: Mapped[str] = mapped_column(String(180), unique=True)
    phone: Mapped[str] = mapped_column(String(32), default="")
    customer_since: Mapped[str] = mapped_column(String(10))
    revenue: Mapped[int] = mapped_column(Integer, default=0)
    sentiment: Mapped[str] = mapped_column(String(24), default="neutral")
    risk_score: Mapped[int] = mapped_column(Integer, default=10)
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    last_interaction: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emails: Mapped[list["Email"]] = relationship(back_populates="customer")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True)
    role: Mapped[str] = mapped_column(String(32), default="owner")


class Email(Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    subject: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    category: Mapped[str] = mapped_column(String(32), default="general")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    sentiment: Mapped[str] = mapped_column(String(24), default="neutral")
    status: Mapped[str] = mapped_column(String(24), default="open")
    ai_draft: Mapped[str] = mapped_column(Text, default="")
    customer: Mapped[Customer] = relationship(back_populates="emails")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[str] = mapped_column(String(10), index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(24), default="open")
    automated: Mapped[bool] = mapped_column(Boolean, default=False)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    description: Mapped[str] = mapped_column(String(220))
    amount: Mapped[int] = mapped_column(Integer)
    issued_date: Mapped[str] = mapped_column(String(10))
    due_date: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(24), default="outstanding")
    customer: Mapped[Customer] = relationship(back_populates="invoices")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    location: Mapped[str] = mapped_column(String(180), default="Video call")
    notes: Mapped[str] = mapped_column(Text, default="")
    customer: Mapped[Customer | None] = relationship()


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    request: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(80), default="business_assistance")
    status: Mapped[str] = mapped_column(String(24), default="completed")
    plan: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AgentAction(Base):
    __tablename__ = "agent_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(220))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW")
    status: Mapped[str] = mapped_column(String(24), default="prepared")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approval: Mapped["ApprovalRequest | None"] = relationship(back_populates="action", uselist=False)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("agent_actions.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action: Mapped[AgentAction] = relationship(back_populates="approval")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String(48), default="business")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
