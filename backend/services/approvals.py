from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import AgentAction, ApprovalRequest
from ..risk_engine import evaluate_action
from .audit import record
from .validation import validate_payload

_DEDUPE_KEYS = {"SEND_EMAIL": ("email_id", "to", "subject"), "CREATE_INVOICE": ("customer_id", "amount", "description"),
                "SCHEDULE_MEETING": ("customer_id", "starts_at")}


def _pending_duplicate(db: Session, action_type: str, payload: dict) -> tuple[AgentAction, ApprovalRequest] | None:
    keys = _DEDUPE_KEYS.get(action_type, ())
    rows = db.scalars(select(ApprovalRequest).options(joinedload(ApprovalRequest.action)).where(ApprovalRequest.status == "pending")).all()
    for row in rows:
        if row.action.action_type == action_type and all(row.action.payload.get(k) == payload.get(k) for k in keys):
            return row.action, row
    return None


def prepare_action(db: Session, *, action_type: str, title: str, payload: dict, explanation: str, run_id: int | None = None) -> tuple[AgentAction, ApprovalRequest | None]:
    payload = validate_payload(action_type, payload)  # raises ValueError on bad data
    duplicate = _pending_duplicate(db, action_type, payload)
    if duplicate:
        return duplicate
    policy = evaluate_action(action_type, payload, db)
    action = AgentAction(run_id=run_id, action_type=action_type, title=title, payload=payload,
                         risk_level=policy["risk_level"], status="awaiting_approval" if policy["approval_required"] else "prepared")
    db.add(action)
    db.flush()
    approval = None
    if policy["approval_required"]:
        approval = ApprovalRequest(action_id=action.id, explanation=f"{explanation}\n\nRisk: {policy['risk_level']}. {policy['reason']}")
        db.add(approval)
    record(db, "action.prepared", title, entity_type="agent_action", entity_id=action.id,
           details={"action_type": action_type, "risk_level": policy["risk_level"], "approval_required": policy["approval_required"], "risk_factors": policy["factors"]})
    return action, approval


def decide(db: Session, approval_id: int, decision: str, edited_payload: dict | None = None) -> dict:
    approval = db.scalar(select(ApprovalRequest).options(joinedload(ApprovalRequest.action)).where(ApprovalRequest.id == approval_id))
    if approval is None:
        raise LookupError("Approval request not found")
    if approval.status != "pending":
        raise ValueError("This approval has already been decided")
    action = approval.action
    if decision == "approve":
        if edited_payload is not None:
            action.payload = validate_payload(action.action_type, edited_payload)
            # An edit can change the risk (e.g. a new recipient or a bigger amount): re-evaluate and never lower it.
            policy = evaluate_action(action.action_type, action.payload, db)
            record(db, "action.reassessed", f"Re-assessed after edit: {action.title}", entity_type="agent_action", entity_id=action.id,
                   details={"risk_level": policy["risk_level"], "factors": policy["factors"]})
            action.risk_level = policy["risk_level"]
        approval.status = "approved"
        approval.decided_at = datetime.now(timezone.utc)
        execute_action(db, action)
        record(db, "approval.approved", f"Approved: {action.title}", entity_type="agent_action", entity_id=action.id)
    else:
        approval.status = "rejected"
        approval.decided_at = datetime.now(timezone.utc)
        action.status = "rejected"
        record(db, "approval.rejected", f"Rejected: {action.title}", entity_type="agent_action", entity_id=action.id)
    db.commit()
    return {"approval_id": approval.id, "approval_status": approval.status, "action_status": action.status,
            "message": "Action completed." if decision == "approve" else "Action rejected."}


def execute_action(db: Session, action: AgentAction) -> None:
    """Execute only registered, explicitly gated write tools."""
    from ..tools.calendar import schedule_meeting
    from ..tools.email import send_email
    from ..tools.invoices import create_invoice

    handlers = {"SEND_EMAIL": send_email, "CREATE_INVOICE": create_invoice, "SCHEDULE_MEETING": schedule_meeting}
    handler = handlers.get(action.action_type)
    if handler is None:
        raise ValueError("No execution tool is registered for this action")
    handler(db, validate_payload(action.action_type, action.payload))
    action.status = "executed"
    record(db, "action.executed", f"Executed: {action.title}", entity_type="agent_action", entity_id=action.id,
           details={"action_type": action.action_type})
