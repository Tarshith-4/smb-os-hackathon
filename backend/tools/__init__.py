"""Explicit agent tool registry; models never select arbitrary Python functions."""

from .email import get_email, get_emails, send_email
from .invoices import create_invoice, get_invoices
from .calendar import get_calendar, schedule_meeting
from .customers import analyze_customer, get_customer, get_customers
from .tasks import get_tasks
from .analytics import get_business_metrics

WRITE_TOOLS = {"SEND_EMAIL": send_email, "CREATE_INVOICE": create_invoice, "SCHEDULE_MEETING": schedule_meeting}
READ_TOOLS = {"get_customer": get_customer, "get_customers": get_customers,
              "get_tasks": get_tasks, "get_business_metrics": get_business_metrics,
              "analyze_customer": analyze_customer, "get_emails": get_emails,
              "get_email": get_email, "get_invoices": get_invoices,
              "get_calendar": get_calendar}


def tool_catalog() -> list[dict]:
    return [
        {"name": "get_business_context", "risk": "LOW", "description": "Read cross-system customers, inbox, invoices, tasks, and meetings."},
        {"name": "get_emails", "risk": "LOW", "description": "Read customer conversations."},
        {"name": "get_invoices", "risk": "LOW", "description": "Read invoice status and balances."},
        {"name": "get_calendar", "risk": "LOW", "description": "Read upcoming customer meetings."},
        {"name": "analyze_customer_risk", "risk": "LOW", "description": "Analyze support, sentiment, follow-up, and invoice risk signals."},
        {"name": "draft_email", "risk": "LOW", "description": "Prepare an email draft without sending it."},
        {"name": "send_email", "risk": "MEDIUM", "description": "Send a customer email after approval."},
        {"name": "create_invoice", "risk": "HIGH", "description": "Create an official invoice after approval."},
        {"name": "schedule_meeting", "risk": "MEDIUM", "description": "Schedule an external customer meeting after approval."},
    ]
