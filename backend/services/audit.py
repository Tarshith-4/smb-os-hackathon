from sqlalchemy.orm import Session

from ..models import AuditLog


def record(db: Session, event_type: str, message: str, *, entity_type: str = "business", entity_id: int | None = None, details: dict | None = None) -> AuditLog:
    entry = AuditLog(event_type=event_type, message=message, entity_type=entity_type, entity_id=entity_id, details=details or {})
    db.add(entry)
    db.flush()
    return entry
