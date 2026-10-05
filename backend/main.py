"""SMB OS API entry point. Demo data is seeded at first startup."""

import asyncio
import hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .database import Base, SessionLocal, engine, get_db
from .models import AgentAction, ApprovalRequest, AuditLog, CalendarEvent, Customer, Email, Invoice, Task
from .schemas import ApprovalDecision, ApprovalEdit, CommandRequest, TaskCreate, TaskUpdate
from .seed import ensure_demo_invoice, ensure_demo_threat, seed_database
from .agents import llm
from .agents.orchestrator import morning_brief, run_command
from .services.business_context import security_alerts
from .services.validation import validate_payload
from .risk_engine import evaluate_action
from .services.approvals import decide
from .services.audit import record


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Optional shared-secret gate: set API_KEY to require an X-API-Key header on every route except /api/health.
    Demo-grade only. A real deployment needs per-user login and per-tenant data."""
    expected = os.getenv("API_KEY")
    if not expected or request.url.path == "/api/health" or request.method == "OPTIONS":
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Missing or invalid API key")


def _brief_job() -> None:
    with SessionLocal() as db:
        morning_brief(db)


async def _scheduler(minutes: int) -> None:
    while True:
        try:
            await asyncio.to_thread(_brief_job)
        except Exception:  # a failed background run must never take the API down
            pass
        await asyncio.sleep(minutes * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
        ensure_demo_threat(db)
        ensure_demo_invoice(db)
    task = None
    minutes = int(os.getenv("BRIEF_INTERVAL_MINUTES", "0") or 0)
    if minutes > 0:  # proactive mode: prepare the daily brief without being asked
        task = asyncio.create_task(_scheduler(minutes))
    yield
    if task:
        task.cancel()


app = FastAPI(title="SMB OS", description="AI operations copilot API", version="0.2.0", lifespan=lifespan,
              dependencies=[Depends(require_api_key)])
app.add_middleware(
    CORSMiddleware, allow_origins=list(dict.fromkeys([os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"), "http://localhost:3000", "http://127.0.0.1:3000"])),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "smb-os-api", "ai": "live" if llm.configured() else "offline",
            "email": "smtp" if os.getenv("SMTP_HOST") else "mock", "auth": "api_key" if os.getenv("API_KEY") else "open",
            "proactive_brief_minutes": int(os.getenv("BRIEF_INTERVAL_MINUTES", "0") or 0)}


MINUTES_SAVED = {"SEND_EMAIL": 6, "CREATE_INVOICE": 10, "SCHEDULE_MEETING": 5}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today().isoformat()
    customers = db.scalars(select(Customer).options(joinedload(Customer.emails))).unique().all()
    open_emails = db.scalar(select(func.count()).select_from(Email).where(Email.status == "open")) or 0
    overdue = db.scalars(select(Invoice).where(Invoice.status == "overdue")).all()
    paid = db.scalars(select(Invoice).where(Invoice.status == "paid")).all()
    due_now = db.scalar(select(func.count()).select_from(Task).where(Task.due_date <= today, Task.status == "open")) or 0
    overdue_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.due_date < today, Task.status == "open")) or 0
    at_risk = sorted([c for c in customers if c.risk_score >= 65], key=lambda c: c.risk_score, reverse=True)
    executed = db.scalars(select(AgentAction).where(AgentAction.status == "executed")).all()
    auto_done = db.scalar(select(func.count()).select_from(Task).where(Task.automated.is_(True), Task.status == "completed")) or 0
    minutes = sum(MINUTES_SAVED.get(a.action_type, 5) for a in executed) + 3 * auto_done  # transparent estimate, not a claim
    alerts = security_alerts(db)
    priorities = []
    if alerts:
        priorities.append({"priority": "urgent", "title": f"Review {len(alerts)} suspicious message(s)", "detail": f"{alerts[0]['customer']}: {', '.join(alerts[0]['flags'])}. Blocked from the AI."})
    for c in at_risk[:1]:
        n = sum(e.status == "open" for e in c.emails)
        priorities.append({"priority": "urgent", "title": f"Resolve {c.company}'s open support issues" if n else f"Check in with {c.company}", "detail": f"{n} open conversation(s). {c.risk_reason}"})
    priorities.append({"priority": "high", "title": "Prepare today's customer follow-ups", "detail": f"{due_now} open tasks are due."})
    priorities.append({"priority": "medium", "title": "Review overdue invoices", "detail": f"{len(overdue)} invoices need a payment follow-up."})
    return {
        "business_name": os.getenv("BUSINESS_NAME", "Northstar Studio"),
        "metrics": {"time_saved_hours": round(minutes / 60, 1), "tasks_automated": len(executed) + auto_done,
                    "customer_issues": open_emails, "revenue_inr": sum(i.amount for i in paid),
                    "outstanding_inr": sum(i.amount for i in overdue), "customers_at_risk": len(at_risk),
                    "estimate_note": "Time saved is estimated from approved actions (6 min per email, 10 per invoice, 5 per meeting, 3 per automated task)."},
        "autopilot": {"urgent_issues": sum(1 for c in customers for e in c.emails if e.status == "open" and e.priority == "high"),
                      "overdue_followups": overdue_tasks, "overdue_invoice_count": len(overdue), "outstanding_inr": sum(i.amount for i in overdue),
                      "customers_at_risk": len(at_risk), "tasks_due_today": due_now},
        "security_alerts": alerts,
        "top_risk_customers": [{"id": c.id, "company": c.company, "risk_score": c.risk_score, "reason": c.risk_reason} for c in at_risk[:3]],
        "priorities": priorities[:4],
    }


@app.get("/api/customers")
def customers(q: str | None = None, db: Session = Depends(get_db)):
    query = select(Customer).options(joinedload(Customer.invoices), joinedload(Customer.emails)).order_by(Customer.risk_score.desc())
    rows = db.scalars(query).unique().all()
    if q:
        term = q.casefold()
        rows = [c for c in rows if term in c.company.casefold() or term in c.name.casefold() or term in c.email.casefold()]
    return [{"id": c.id, "name": c.name, "company": c.company, "email": c.email, "phone": c.phone,
             "customer_since": c.customer_since, "revenue": c.revenue, "sentiment": c.sentiment,
             "risk_score": c.risk_score, "risk_reason": c.risk_reason, "preferences": c.preferences,
             "last_interaction": c.last_interaction, "open_issues": sum(e.status == "open" for e in c.emails),
             "outstanding_invoices": sum(i.amount for i in c.invoices if i.status in ("overdue", "outstanding"))} for c in rows]


@app.get("/api/customers/{customer_id}")
def customer_detail(customer_id: int, db: Session = Depends(get_db)):
    customer = db.scalar(select(Customer).options(joinedload(Customer.emails), joinedload(Customer.invoices)).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(404, "Customer not found")
    return {"id": customer.id, "name": customer.name, "company": customer.company, "email": customer.email,
            "phone": customer.phone, "customer_since": customer.customer_since, "revenue": customer.revenue,
            "sentiment": customer.sentiment, "risk_score": customer.risk_score, "risk_reason": customer.risk_reason,
            "preferences": customer.preferences, "open_issues": sum(e.status == "open" for e in customer.emails),
            "emails": [{"id": e.id, "subject": e.subject, "message": e.message, "received_at": e.received_at, "status": e.status} for e in customer.emails],
            "invoices": [{"id": i.id, "number": i.number, "amount": i.amount, "due_date": i.due_date, "status": i.status} for i in customer.invoices]}


@app.get("/api/emails")
def emails(status: str | None = None, db: Session = Depends(get_db)):
    query = select(Email).options(joinedload(Email.customer)).order_by(Email.received_at.desc())
    if status:
        query = query.where(Email.status == status)
    return [{"id": e.id, "customer_id": e.customer_id, "customer": e.customer.company,
             "subject": e.subject, "message": e.message, "received_at": e.received_at,
             "category": e.category, "priority": e.priority, "sentiment": e.sentiment,
             "status": e.status, "ai_draft": e.ai_draft} for e in db.scalars(query).all()]


@app.get("/api/tasks")
def tasks(db: Session = Depends(get_db)):
    rows = db.execute(select(Task, Customer.company).outerjoin(Customer, Task.customer_id == Customer.id).order_by(Task.due_date)).all()
    return [{"id": t.id, "customer_id": t.customer_id, "customer": company, "title": t.title,
             "description": t.description, "due_date": t.due_date, "priority": t.priority,
             "status": t.status, "automated": t.automated} for t, company in rows]


@app.post("/api/tasks")
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    if body.customer_id is not None and db.get(Customer, body.customer_id) is None:
        raise HTTPException(404, "Customer not found")
    task = Task(title=body.title, due_date=body.due_date, customer_id=body.customer_id)
    db.add(task)
    db.flush()
    record(db, "task.created", f"Task created: {task.title}", entity_type="task", entity_id=task.id)
    db.commit()
    return {"id": task.id, "title": task.title, "due_date": task.due_date, "status": task.status}


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    task.status = body.status
    record(db, "task.completed" if body.status == "completed" else "task.reopened",
           f"Task {body.status}: {task.title}", entity_type="task", entity_id=task.id)
    db.commit()
    return {"id": task.id, "status": task.status}


@app.get("/api/invoices")
def invoices(db: Session = Depends(get_db)):
    rows = db.scalars(select(Invoice).options(joinedload(Invoice.customer)).order_by(Invoice.due_date)).all()
    return [{"id": i.id, "number": i.number, "customer_id": i.customer_id, "customer": i.customer.company,
             "description": i.description, "amount": i.amount, "issued_date": i.issued_date,
             "due_date": i.due_date, "status": i.status} for i in rows]


@app.get("/api/calendar")
def calendar(db: Session = Depends(get_db)):
    rows = db.scalars(select(CalendarEvent).options(joinedload(CalendarEvent.customer)).order_by(CalendarEvent.starts_at)).all()
    now = datetime.now(timezone.utc)
    rows = [event for event in rows if (event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at) >= now]
    return [{"id": e.id, "customer_id": e.customer_id, "customer": e.customer.company if e.customer else None,
             "title": e.title, "starts_at": e.starts_at, "duration_minutes": e.duration_minutes,
             "location": e.location, "notes": e.notes} for e in rows]


@app.get("/api/approvals")
def approvals(db: Session = Depends(get_db)):
    rows = db.scalars(select(ApprovalRequest).options(joinedload(ApprovalRequest.action)).order_by(ApprovalRequest.id.desc())).all()
    return [{"id": r.id, "status": r.status, "explanation": r.explanation, "decided_at": r.decided_at,
             "action": {"id": r.action.id, "type": r.action.action_type, "title": r.action.title,
                        "payload": r.action.payload, "risk_level": r.action.risk_level, "status": r.action.status}}
            for r in rows]


@app.post("/api/approvals/{approval_id}/decision")
def approval_decision(approval_id: int, body: ApprovalDecision, db: Session = Depends(get_db)):
    try:
        return decide(db, approval_id, body.decision, body.edited_payload)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "The approved action could not be completed. The action was not recorded as sent.") from exc


@app.put("/api/approvals/{approval_id}")
def edit_approval(approval_id: int, body: ApprovalEdit, db: Session = Depends(get_db)):
    approval = db.scalar(select(ApprovalRequest).options(joinedload(ApprovalRequest.action)).where(ApprovalRequest.id == approval_id))
    if approval is None:
        raise HTTPException(404, "Approval request not found")
    if approval.status != "pending":
        raise HTTPException(409, "This approval has already been decided")
    try:
        approval.action.payload = validate_payload(approval.action.action_type, body.payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    policy = evaluate_action(approval.action.action_type, approval.action.payload, db)
    approval.action.risk_level = policy["risk_level"]  # an edit can change the risk; show it before the owner approves
    record(db, "action.edited", f"Edited prepared action: {approval.action.title}", entity_type="agent_action", entity_id=approval.action.id)
    db.commit()
    return {"approval_id": approval.id, "status": approval.status, "payload": approval.action.payload, "risk_level": approval.action.risk_level, "risk_factors": policy["factors"]}


@app.post("/api/agent/command")
def agent_command(body: CommandRequest, db: Session = Depends(get_db)):
    try:
        return run_command(db, body.message)
    except ValueError as exc:  # payload validation failures are safe to explain
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        # Do not expose internal provider, database, or Python exception details.
        raise HTTPException(503, "The operations agent could not complete this request. Please try again.") from exc


@app.post("/api/agent/brief")
def agent_brief(db: Session = Depends(get_db)):
    try:
        return morning_brief(db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "The morning brief could not be prepared.") from exc


@app.get("/api/security/alerts")
def alerts(db: Session = Depends(get_db)):
    return security_alerts(db)


@app.get("/api/activity")
def activity(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 250))).all()
    return [{"id": r.id, "event_type": r.event_type, "message": r.message, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "details": r.details, "created_at": r.created_at} for r in rows]
