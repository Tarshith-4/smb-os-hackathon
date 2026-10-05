"""Central, context-aware policy for classifying tool actions and their approval gates.

Base risk comes from the action type; context can only RAISE it (never lower it).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

RISK_BY_ACTION = {
    "READ_EMAIL": "LOW", "READ_CUSTOMER": "LOW", "READ_BUSINESS_DATA": "LOW",
    "ANALYZE_DATA": "LOW", "DRAFT_EMAIL": "LOW", "PREPARE_FOLLOWUP": "LOW",
    "PREPARE_INVOICE": "LOW", "PREPARE_MEETING": "LOW",
    "SEND_EMAIL": "MEDIUM", "SCHEDULE_MEETING": "MEDIUM",
    "CREATE_INVOICE": "HIGH", "MODIFY_CUSTOMER": "HIGH",
    "REFUND": "CRITICAL", "DELETE_DATA": "CRITICAL", "FINANCIAL_TRANSACTION": "CRITICAL",
}
LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
REASONS = {
    "LOW": "Read, analysis, or preparation has no external effect.",
    "MEDIUM": "This action communicates or schedules something outside the workspace.",
    "HIGH": "This action creates or changes an official business record.",
    "CRITICAL": "This action has a high-impact financial or destructive effect.",
}
LARGE_INVOICE_INR = 100_000
KEY_ACCOUNT_REVENUE = 500_000


def _bump(level: str, to: str) -> str:
    return to if LEVELS.index(to) > LEVELS.index(level) else level


def evaluate_action(action_type: str, payload: dict | None = None, db: Session | None = None) -> dict:
    risk = RISK_BY_ACTION.get(action_type.upper(), "HIGH")
    factors: list[str] = []
    payload = payload or {}
    if db is not None and payload:
        from .models import Customer, Invoice  # local import avoids a cycle
        if action_type == "SEND_EMAIL":
            known = db.scalar(select(Customer).where(Customer.email == payload.get("to")))
            if known is None:
                risk = _bump(risk, "HIGH"); factors.append("recipient is not a known customer")
            elif known.revenue >= KEY_ACCOUNT_REVENUE:
                risk = _bump(risk, "HIGH"); factors.append(f"key account ({known.company})")
        elif action_type == "CREATE_INVOICE":
            amount = int(payload.get("amount", 0) or 0)
            if amount >= LARGE_INVOICE_INR:
                risk = _bump(risk, "CRITICAL"); factors.append(f"large amount (₹{amount:,})")
            prior = db.scalars(select(Invoice.amount).where(Invoice.customer_id == payload.get("customer_id"))).all()
            if prior and amount > 2 * max(prior):
                risk = _bump(risk, "CRITICAL"); factors.append("amount is more than 2× this customer's largest prior invoice")
    reason = REASONS[risk] + (" Escalated because: " + "; ".join(factors) + "." if factors else "")
    return {"risk_level": risk, "approval_required": risk != "LOW", "reason": reason, "factors": factors}
