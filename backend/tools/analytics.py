from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Customer, Email, Invoice, Task


def get_business_metrics(db: Session) -> dict:
    open_messages = db.scalar(select(func.count()).select_from(Email).where(Email.status == "open")) or 0
    overdue_invoices = db.scalars(select(Invoice).where(Invoice.status == "overdue")).all()
    at_risk = db.scalar(select(func.count()).select_from(Customer).where(Customer.risk_score >= 65)) or 0
    open_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.status == "open")) or 0
    return {"open_conversations": open_messages, "overdue_invoice_count": len(overdue_invoices),
            "overdue_inr": sum(row.amount for row in overdue_invoices), "customers_at_risk": at_risk,
            "open_tasks": open_tasks}
