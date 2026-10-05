from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Customer, Invoice
from ..services.audit import record


def get_invoices(db: Session) -> list[Invoice]:
    return list(db.scalars(select(Invoice).order_by(Invoice.due_date)).all())


def create_invoice(db: Session, payload: dict) -> dict:
    customer = db.scalar(select(Customer).where(Customer.id == int(payload["customer_id"])))
    if customer is None:
        raise LookupError("Customer not found")
    amount = int(payload["amount"])
    if amount <= 0:
        raise ValueError("Invoice amount must be greater than zero")
    count = db.scalar(select(func.count()).select_from(Invoice)) or 0
    today = date.today()
    invoice = Invoice(number=f"INV-{today.year}-{1042 + count}", customer_id=customer.id,
                      description=str(payload.get("description", "Consulting services")), amount=amount,
                      issued_date=today.isoformat(), due_date=(today + timedelta(days=30)).isoformat(), status="outstanding")
    db.add(invoice)
    db.flush()
    record(db, "invoice.created", f"Invoice {invoice.number} created for {customer.company}", entity_type="invoice", entity_id=invoice.id)
    return {"invoice_id": invoice.id, "number": invoice.number, "customer": customer.company, "amount": amount}
