"""Cross-system, concise business context for agent planning."""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import CalendarEvent, Customer, Email, Invoice, Task
from .guard import WITHHELD, scan


def load_business_context(db: Session) -> dict:
    customers = db.scalars(select(Customer).options(joinedload(Customer.emails), joinedload(Customer.invoices))).unique().all()
    tasks = db.scalars(select(Task).where(Task.status == "open").order_by(Task.due_date)).all()
    events = db.scalars(select(CalendarEvent).options(joinedload(CalendarEvent.customer)).order_by(CalendarEvent.starts_at)).all()
    now = datetime.now(timezone.utc)
    events = [event for event in events if (event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at) >= now]
    invoices = db.scalars(select(Invoice).options(joinedload(Invoice.customer)).order_by(Invoice.due_date)).all()
    inbox = db.scalars(select(Email).options(joinedload(Email.customer)).order_by(Email.received_at.desc())).all()
    return {
        "today": date.today().isoformat(),
        "customers": [{"id": c.id, "company": c.company, "contact": c.name, "email": c.email,
                       "revenue": c.revenue, "sentiment": c.sentiment, "risk_score": c.risk_score,
                       "risk_reason": c.risk_reason,
                       "open_issues": [{"subject": e.subject, "priority": e.priority, "sentiment": e.sentiment, "message": WITHHELD if scan(e.subject, e.message) else e.message} for e in c.emails if e.status == "open"],
                       "invoices": [{"number": i.number, "amount": i.amount, "due_date": i.due_date, "status": i.status} for i in c.invoices if i.status in ("overdue", "outstanding")]}
                      for c in customers],
        "open_tasks": [{"title": t.title, "due_date": t.due_date, "priority": t.priority, "customer_id": t.customer_id} for t in tasks],
        "invoices": [{"id": i.id, "number": i.number, "customer_id": i.customer_id, "customer": i.customer.company,
                      "customer_email": i.customer.email, "amount": i.amount, "due_date": i.due_date, "status": i.status} for i in invoices],
        "upcoming_meetings": [{"customer_id": e.customer_id, "customer": e.customer.company if e.customer else "Internal",
                               "title": e.title, "starts_at": e.starts_at.isoformat(), "notes": e.notes} for e in events[:12]],
        "recent_conversations": [{"id": e.id, "customer_id": e.customer_id, "customer": e.customer.company,
                                  "contact": e.customer.name, "email": e.customer.email, "subject": e.subject,
                                  "message": WITHHELD if scan(e.subject, e.message) else e.message,
                                  "security_flags": scan(e.subject, e.message), "category": e.category, "priority": e.priority,
                                  "sentiment": e.sentiment, "status": e.status, "ai_draft": e.ai_draft}
                                 for e in inbox[:25]],
    }


def security_alerts(db: Session) -> list[dict]:
    """Open inbound messages that contain prompt-injection / social-engineering signals."""
    rows = db.scalars(select(Email).options(joinedload(Email.customer)).where(Email.status == "open").order_by(Email.received_at.desc())).all()
    return [{"email_id": e.id, "customer": e.customer.company, "subject": e.subject, "flags": scan(e.subject, e.message)}
            for e in rows if scan(e.subject, e.message)]
