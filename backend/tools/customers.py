from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Customer


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.scalar(select(Customer).options(joinedload(Customer.emails), joinedload(Customer.invoices)).where(Customer.id == customer_id))


def get_customers(db: Session) -> list[Customer]:
    return list(db.scalars(select(Customer).order_by(Customer.company)).all())


def analyze_customer(db: Session, customer_id: int) -> dict:
    customer = get_customer(db, customer_id)
    if customer is None:
        raise LookupError("Customer not found")
    open_issues = [email for email in customer.emails if email.status == "open"]
    overdue = [invoice for invoice in customer.invoices if invoice.status == "overdue"]
    signals = ([f"{len(open_issues)} open support issues"] if open_issues else [])
    if customer.sentiment == "negative":
        signals.append("recent negative sentiment")
    if overdue:
        signals.append(f"{sum(invoice.amount for invoice in overdue):,} INR overdue")
    return {"customer_id": customer.id, "company": customer.company, "risk_score": customer.risk_score,
            "risk_reason": customer.risk_reason, "signals": signals}
