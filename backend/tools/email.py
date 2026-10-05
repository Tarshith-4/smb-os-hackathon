import os
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Email
from ..services.audit import record


def _deliver(to: str, subject: str, body: str) -> str:
    """Real SMTP delivery when SMTP_HOST is set; otherwise a mock. SMTP_REDIRECT_TO sends every message to
    your own inbox instead (safe way to demo real delivery with seeded .example customers)."""
    host = os.getenv("SMTP_HOST")
    if not host:
        return "mock"
    redirect = os.getenv("SMTP_REDIRECT_TO")
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "smb-os@localhost"))
    msg["To"] = redirect or to
    msg["Subject"] = f"[SMB OS demo -> {to}] {subject}" if redirect else subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as smtp:
        smtp.starttls()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return "smtp"


def send_email(db: Session, payload: dict) -> dict:
    """Send after approval. Failure raises, so the action is never recorded as sent."""
    email_id = payload.get("email_id")
    body = str(payload.get("body", "")).strip()
    if len(body) < 5:
        raise ValueError("The email draft is empty")
    provider = _deliver(payload["to"], str(payload.get("subject", "")), body)
    if email_id:
        source = db.scalar(select(Email).where(Email.id == int(email_id)))
        if source is None:
            raise LookupError("Conversation not found")
        source.status = "resolved"
        source.ai_draft = body
        record(db, "email.sent", f"Customer response sent ({provider}): {source.subject}", entity_type="email", entity_id=source.id)
        return {"email_id": source.id, "sent": True, "recipient": payload.get("to"), "delivery": provider}
    record(db, "email.sent", f"Email sent ({provider}) to {payload.get('to', 'customer')}", details={"to": payload.get("to")})
    return {"sent": True, "recipient": payload.get("to"), "delivery": provider}


def get_emails(db: Session, status: str | None = None) -> list[Email]:
    query = select(Email).order_by(Email.received_at.desc())
    if status:
        query = query.where(Email.status == status)
    return list(db.scalars(query).all())


def get_email(db: Session, email_id: int) -> Email | None:
    return db.get(Email, email_id)
