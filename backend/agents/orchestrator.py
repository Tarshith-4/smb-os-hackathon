"""Agent run lifecycle: context → plan → explicit tools → risk/approval → result."""

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgentRun
from ..services.approvals import prepare_action
from ..services.audit import record
from ..services.business_context import load_business_context, security_alerts
from ..tools import tool_catalog
from . import llm
from .agent_loop import run_agent_loop
from .planner import create_plan

OFFLINE_TOOLS = {"autopilot": ["list_open_conversations", "list_invoices", "list_open_tasks", "get_customer"],
                 "prepare_reply": ["list_open_conversations", "get_customer"], "prepare_reminder": ["list_invoices", "get_customer"],
                 "prepare_invoice": ["get_customer"], "schedule_meeting": ["get_customer", "list_upcoming_meetings"],
                 "weekly_report": ["get_overview", "list_invoices"], "overdue_report": ["list_invoices"],
                 "meeting_brief": ["list_upcoming_meetings", "get_customer"], "risk_report": ["get_overview", "get_customer"],
                 "none": ["get_overview", "get_customer"]}


def _focus(plan: dict, context: dict) -> dict:
    return next((c for c in context["customers"] if c["company"] == plan.get("focus_customer")), context["customers"][0])


def _invoice_request(message: str, customer: dict) -> tuple[int | None, str]:
    """Parse '₹25,000', 'Rs 25k', 'INR 1.5 lakh'. Returns amount=None when no amount is stated (never guess)."""
    amount_match = re.search(r"(?:₹|rs\.?\s*|inr\s*)([\d,]+(?:\.\d+)?)\s*(k|lakhs?|lacs?)?", message, re.I)
    amount = None
    if amount_match:
        value = float(amount_match.group(1).replace(",", ""))
        unit = (amount_match.group(2) or "").lower()
        amount = int(value * (1000 if unit == "k" else 100000 if unit else 1))
    rest = message[amount_match.end():] if amount_match else ""
    desc_match = re.search(r"^\s*(?:for\s+)?(.+?)\s*(?:\.|$)", rest, re.I)
    desc = desc_match.group(1).strip() if desc_match and desc_match.group(1).strip() else "Consulting services"
    return amount, desc


def _recommendations(context: dict, overdue: list[dict]) -> list[str]:
    recs = []
    for c in sorted(context["customers"], key=lambda c: c["risk_score"], reverse=True)[:3]:
        if c["risk_score"] >= 40:
            recs.append(f"Contact {c['company']}: {c['risk_reason'].rstrip('.').lower()}" if c["risk_reason"] else f"Contact {c['company']}")
    if overdue:
        top = max(overdue, key=lambda i: i["amount"])
        recs.append(f"Chase {top['number']} ({top['customer']}, ₹{top['amount']:,} overdue)")
    return recs or ["No urgent actions this week."]


def _tools_for(action_type: str) -> list[str]:
    return OFFLINE_TOOLS.get(action_type, OFFLINE_TOOLS["none"])


def _live_result(db: Session, run: AgentRun, live: dict, context: dict, alerts: list[dict]) -> dict:
    focus = next((c for c in context["customers"] if c["company"] == live["focus_customer"]), None)
    report = None
    if focus:
        overdue = sum(i["amount"] for i in focus["invoices"] if i["status"] == "overdue")
        signals = ([f"{len(focus['open_issues'])} open issue(s)"] if focus["open_issues"] else []) + ([f"₹{overdue:,} overdue"] if overdue else [])
        report = {"focus_customer": focus["company"], "priority": "HIGH" if focus["risk_score"] >= 65 else "MEDIUM",
                  "signals": signals or [focus["risk_reason"]], "recommendation": live["recommendation"], "customer_id": focus["id"]}
    run.intent, run.status, run.summary, run.plan = "agent_loop", "completed", live["summary"], live["trace"]
    record(db, "agent.run_completed", "Agent completed (live tool-calling loop)", entity_type="agent_run", entity_id=run.id,
           details={"prepared_actions": len(live["prepared"]), "tools_used": live["tools_used"], "steps": len(live["trace"])})
    db.commit()
    prepared = live["prepared"]
    return {"run_id": run.id, "intent": "agent_loop", "summary": live["summary"], "steps": live["trace"],
            "trace": live["trace"] + ([f"⚠ {len(prepared)} external action(s) require approval"] if prepared else []),
            "focus_customer": focus["company"] if focus else None, "prepared_actions": prepared, "report": report,
            "approval_count": len(prepared), "ai_mode": "live", "tools_used": live["tools_used"], "security_alerts": alerts}


def morning_brief(db: Session) -> dict:
    """Proactive run: prepares today's priority actions once per day without anyone asking."""
    today = date.today().isoformat()
    existing = db.scalar(select(AgentRun).where(AgentRun.request.like(f"[morning brief {today}]%")))
    if existing:
        return {"skipped": True, "reason": "Today's brief was already prepared.", "run_id": existing.id}
    result = run_command(db, f"[morning brief {today}] Take care of everything important today")
    record(db, "agent.morning_brief", "Morning brief prepared proactively", entity_type="agent_run", entity_id=result["run_id"],
           details={"prepared_actions": result["approval_count"]})
    db.commit()
    return result


def run_command(db: Session, message: str) -> dict:
    context = load_business_context(db)
    alerts = security_alerts(db)
    run = AgentRun(request=message, intent="agent", status="running", plan=[])
    db.add(run)
    db.flush()
    if llm.configured():
        live = run_agent_loop(db, message, context, run)
        if live:
            return _live_result(db, run, live, context, alerts)
    plan = create_plan(message, context)
    run.intent, run.plan = plan["intent"], plan["steps"]
    focus = _focus(plan, context)
    prepared, report = [], None
    action_type = plan["action"]
    if action_type in ("prepare_invoice", "schedule_meeting") and not plan.get("customer_named"):
        action_type = "needs_customer"  # never guess which customer gets an invoice or meeting

    if action_type == "autopilot":
        # Prepare selected high-priority customer replies; sending stays behind approval.
        open_urgent = [e for e in context["recent_conversations"] if e["status"] == "open" and not e["security_flags"] and (e["priority"] == "high" or e["sentiment"] == "negative")]
        seen, picks = set(), []
        for e in open_urgent:  # one reply per customer, not one per email
            if e["customer_id"] not in seen:
                seen.add(e["customer_id"]); picks.append(e)
        for conversation in picks[:4]:
            cust = next((c for c in context["customers"] if c["id"] == conversation["customer_id"]), focus)
            body = conversation["ai_draft"] or f"Hi {cust['contact'].split()[0]},\n\nI'm sorry this is still unresolved. I've flagged your message for priority attention and will share an update shortly.\n\nBest,\nSupport Team"
            action, approval = prepare_action(db, action_type="SEND_EMAIL", title=f"Reply to {cust['company']}: {conversation['subject']}",
                                              payload={"email_id": conversation["id"], "to": cust["email"], "subject": f"Re: {conversation['subject']}", "body": body},
                                              explanation=f"Open {conversation['priority']} priority conversation with {conversation['sentiment']} sentiment. This reply acknowledges the issue and gives the customer a next step.", run_id=run.id)
            prepared.append({"action_id": action.id, "approval_id": approval.id if approval else None, "title": action.title, "risk_level": action.risk_level, "payload": action.payload})
        run.summary = f"Reviewed {len(context['recent_conversations'])} recent conversations, {len(context['open_tasks'])} open tasks, {len(context['invoices'])} invoices, and {len(context['upcoming_meetings'])} meetings. Prepared {len(prepared)} customer replies for approval." + (f" Blocked {len(alerts)} suspicious message(s) from the AI: review them manually." if alerts else "")
    elif action_type in ("prepare_reply", "prepare_reminder"):
        conversation = next((e for e in context["recent_conversations"] if e["status"] == "open" and e["customer_id"] == focus["id"] and not e["security_flags"]), None)
        invoice = next((i for i in context["invoices"] if i["customer_id"] == focus["id"] and i["status"] in ("overdue", "outstanding")), None)
        if not invoice and action_type == "prepare_reminder":
            invoice = next((i for i in context["invoices"] if i["status"] == "overdue"), None)
            if invoice:
                focus = next(c for c in context["customers"] if c["id"] == invoice["customer_id"])
        if action_type == "prepare_reminder" and invoice:
            from datetime import date
            days = max((date.today() - date.fromisoformat(invoice["due_date"])).days, 0)
            body = f"Hi {focus['contact'].split()[0]},\n\nA friendly reminder that invoice {invoice['number']} for ₹{invoice['amount']:,} is {days} days past its due date. Please let us know if you need a copy or have any questions.\n\nBest,\nAccounts Team"
            action, approval = prepare_action(db, action_type="SEND_EMAIL", title=f"Payment reminder to {focus['company']}",
                                              payload={"to": focus["email"], "subject": f"Payment reminder: {invoice['number']}", "body": body},
                                              explanation=f"Invoice {invoice['number']} for ₹{invoice['amount']:,} is {days} days overdue. A polite reminder supports collection while preserving the customer relationship.", run_id=run.id)
        elif conversation:
            body = conversation["ai_draft"] or f"Hi {focus['contact'].split()[0]},\n\nI'm sorry for the delay. I've shared your message with our team and we'll provide an update shortly.\n\nBest,\nSupport Team"
            action, approval = prepare_action(db, action_type="SEND_EMAIL", title=f"Respond to {focus['company']}",
                                              payload={"email_id": conversation["id"], "to": focus["email"], "subject": f"Re: {conversation['subject']}", "body": body},
                                              explanation=f"Prepared from the open conversation ‘{conversation['subject']}’ and the customer's recent support history.", run_id=run.id)
        else:
            action = approval = None
        if action:
            prepared.append({"action_id": action.id, "approval_id": approval.id if approval else None, "title": action.title, "risk_level": action.risk_level, "payload": action.payload})
        run.summary = f"Prepared an approval-ready customer follow-up for {focus['company']}." if action else f"No open follow-up matched {focus['company']}."
    elif action_type == "prepare_invoice":
        amount, description = _invoice_request(message, focus)
        if amount is None:
            run.summary = f"I need an amount to prepare the invoice for {focus['company']}. Try: “Create an invoice for {focus['company']} for ₹25,000 for consulting”."
            report = {"needs_input": "amount"}
        else:
            action, approval = prepare_action(db, action_type="CREATE_INVOICE", title=f"Create ₹{amount:,} invoice for {focus['company']}",
                                              payload={"customer_id": focus["id"], "amount": amount, "description": description},
                                              explanation=f"The requested official invoice for {focus['company']} is a business record and will be created only after approval.", run_id=run.id)
            prepared.append({"action_id": action.id, "approval_id": approval.id if approval else None, "title": action.title,
                             "risk_level": action.risk_level, "payload": action.payload})
            run.summary = f"Prepared a ₹{amount:,} invoice for {focus['company']}; it will be recorded after approval."
    elif action_type == "needs_customer":
        run.summary = "Which customer is this for? Name the company (for example “Acme Corp”) so I don't act on the wrong account."
        report = {"needs_input": "customer"}
    elif action_type == "schedule_meeting":
        from datetime import datetime, time, timedelta, timezone
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        starts_at = datetime.combine(tomorrow, time(hour=10), tzinfo=timezone.utc)
        action, approval = prepare_action(db, action_type="SCHEDULE_MEETING", title=f"Schedule a check-in with {focus['company']}",
                                          payload={"customer_id": focus["id"], "customer": focus["company"],
                                                   "title": f"{focus['company']} account check-in", "starts_at": starts_at.isoformat(),
                                                   "duration_minutes": 30, "location": "Video call",
                                                   "notes": "Review open items, recent outcomes, and upcoming priorities."},
                                          explanation=f"The customer meeting is prepared for {starts_at.strftime('%Y-%m-%d %H:%M UTC')}. The calendar invitation will be created only after approval.", run_id=run.id)
        prepared.append({"action_id": action.id, "approval_id": approval.id if approval else None, "title": action.title,
                         "risk_level": action.risk_level, "payload": action.payload})
        run.summary = f"Prepared a customer meeting with {focus['company']} for your approval."
    elif action_type == "weekly_report":
        resolved = sum(e["status"] == "resolved" for e in context["recent_conversations"])
        open_count = sum(e["status"] == "open" for e in context["recent_conversations"])
        overdue = [i for i in context["invoices"] if i["status"] == "overdue"]
        report = {"support": {"conversations": len(context["recent_conversations"]), "resolved": resolved, "pending": open_count},
                  "revenue": {"outstanding_inr": sum(i["amount"] for i in overdue), "overdue_invoices": len(overdue)},
                  "customers_at_risk": sum(c["risk_score"] >= 65 for c in context["customers"]),
                  "recommendations": _recommendations(context, overdue)}
        run.summary = "Your weekly business snapshot is ready, with support, collections, and customer health priorities."
    elif action_type == "overdue_report":
        overdue = [i for i in context["invoices"] if i["status"] == "overdue"]
        report = {"overdue_invoice_count": len(overdue), "outstanding_inr": sum(i["amount"] for i in overdue),
                  "invoices": [{"number": i["number"], "customer": i["customer"], "amount": i["amount"], "due_date": i["due_date"]} for i in overdue]}
        run.summary = f"{len(overdue)} invoices are overdue, totaling ₹{sum(i['amount'] for i in overdue):,}. The highest-priority balance is {overdue[0]['customer']} at ₹{overdue[0]['amount']:,}." if overdue else "There are no overdue invoices."
    elif action_type == "meeting_brief":
        meetings = [m for m in context["upcoming_meetings"] if m["customer_id"] == focus["id"]]
        recent = [e for e in context["recent_conversations"] if e["customer_id"] == focus["id"]]
        issues = [e for e in recent if e["status"] == "open"]
        overdue = [i for i in context["invoices"] if i["customer_id"] == focus["id"] and i["status"] == "overdue"]
        report = {"customer": focus["company"], "meeting": meetings[0] if meetings else None,
                  "last_discussion": recent[0]["subject"] if recent else "Account progress and next steps",
                  "open_issues": len(issues), "outstanding_inr": sum(i["amount"] for i in overdue),
                  "talking_points": (["Resolve the open customer support issue"] if issues else []) + (["Review overdue invoice and confirm next steps"] if overdue else []) + ["Discuss upcoming goals and account progress"]}
        run.summary = f"Meeting brief prepared for {focus['company']} using recent conversations, {len(issues)} open issues, and ₹{sum(i['amount'] for i in overdue):,} in overdue invoices."
    elif action_type == "risk_report":
        at_risk = sorted([customer for customer in context["customers"] if customer["risk_score"] >= 65],
                         key=lambda customer: customer["risk_score"], reverse=True)
        report = {"risky_customers": [{"company": customer["company"], "risk_score": customer["risk_score"],
                                       "reason": customer["risk_reason"], "open_issues": len(customer["open_issues"]),
                                       "overdue_inr": sum(invoice["amount"] for invoice in customer["invoices"] if invoice["status"] == "overdue")}
                                      for customer in at_risk]}
        run.summary = f"{len(at_risk)} customers currently show high churn risk. {at_risk[0]['company']} has the strongest combined signals." if at_risk else "No customers currently meet the high-risk threshold."
    else:
        highest = focus
        open_issues = focus["open_issues"]
        overdue_invoices = [i for i in focus["invoices"] if i["status"] == "overdue"]
        signals = []
        if open_issues:
            signals.append(f"{len(open_issues)} unresolved support issue{'s' if len(open_issues) != 1 else ''}")
        if focus["sentiment"] == "negative":
            signals.append("recent negative sentiment")
        if overdue_invoices:
            signals.append(f"₹{sum(i['amount'] for i in overdue_invoices):,} overdue")
        summary = f"{highest['company']} is the strongest account to contact now: " + (", ".join(signals) if signals else highest["risk_reason"])
        run.summary = summary
        report = {"focus_customer": highest["company"], "priority": "HIGH" if highest["risk_score"] >= 65 else "MEDIUM",
                  "signals": signals or [highest["risk_reason"]], "recommendation": f"Send a personalized check-in to {highest['company']} and review the open account items.",
                  "customer_id": highest["id"]}

    run.status = "completed"
    record(db, "agent.run_completed", f"Agent completed: {plan['intent']}", entity_type="agent_run", entity_id=run.id,
           details={"prepared_actions": len(prepared), "tool_catalog": [t["name"] for t in tool_catalog()]})
    db.commit()
    return {"run_id": run.id, "intent": plan["intent"], "summary": run.summary, "steps": plan["steps"],
            "trace": [f"✓ {step}" for step in plan["steps"]] + ([f"⚠ {len(prepared)} external action(s) require approval"] if prepared else []),
            "focus_customer": focus["company"], "prepared_actions": prepared, "report": report,
            "approval_count": len(prepared), "ai_mode": "offline", "tools_used": _tools_for(action_type), "security_alerts": alerts}
