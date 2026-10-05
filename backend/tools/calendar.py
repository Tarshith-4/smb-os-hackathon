from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session

from ..models import CalendarEvent, Customer
from ..services.audit import record


def get_calendar(db: Session) -> list[CalendarEvent]:
    return list(db.scalars(select(CalendarEvent).options(joinedload(CalendarEvent.customer)).order_by(CalendarEvent.starts_at)).all())


def schedule_meeting(db: Session, payload: dict) -> dict:
    customer = db.get(Customer, int(payload["customer_id"]))
    if customer is None:
        raise LookupError("Customer not found")
    starts_at = datetime.fromisoformat(payload["starts_at"].replace("Z", "+00:00"))
    event = CalendarEvent(customer_id=customer.id, title=str(payload.get("title", f"{customer.company} check-in")),
                          starts_at=starts_at, duration_minutes=int(payload.get("duration_minutes", 30)),
                          location=str(payload.get("location", "Video call")), notes=str(payload.get("notes", "")))
    db.add(event)
    db.flush()
    record(db, "meeting.scheduled", f"Meeting scheduled with {customer.company}", entity_type="calendar_event", entity_id=event.id)
    return {"event_id": event.id, "customer": customer.company, "starts_at": starts_at.isoformat()}
