"""Request interpretation and concise, user-safe action plans."""

def _fallback_plan(request: str, context: dict) -> dict:
    """Deterministic offline interpretation for the seeded hackathon demo."""
    text = request.casefold()
    customers = context["customers"]
    selected = next((c for c in customers if c["company"].casefold() in text or c["contact"].casefold() in text), None)
    if any(word in text for word in ("everything important", "take care", "autopilot", "handle today's", "handle today")):
        intent, action = "business_autopilot", "autopilot"
        summary = "I reviewed your open conversations, customer health, invoices, follow-ups, and meetings."
        steps = ["Reviewing open customer conversations", "Checking customer health and follow-up gaps", "Reviewing overdue invoices and today's tasks", "Preparing priority actions for your approval"]
    elif "weekly" in text or "business report" in text or "report" in text:
        intent, action = "weekly_business_report", "weekly_report"
        summary = "Your week combines customer support activity, revenue collection, and follow-up work."
        steps = ["Summarizing customer support and resolution status", "Reviewing invoice and revenue signals", "Checking customer risk and team follow-through"]
    elif "invoice" in text and any(word in text for word in ("create", "prepare", "make")):
        intent, action = "prepare_invoice", "prepare_invoice"
        summary = "I found the invoice request and will prepare it as a business record for approval."
        steps = ["Matching the requested customer", "Preparing invoice details and due date", "Classifying the record change for approval"]
    elif any(word in text for word in ("follow up", "follow-up", "followup", "reconnect", "check-in")):
        intent, action = "customer_followup", "prepare_reply"
        summary = "I checked the account's recent conversation and follow-up context, then prepared a personal check-in."
        steps = ["Finding the customer's latest conversation", "Checking their open issues and account history", "Preparing a follow-up for approval"]
    elif "meeting" in text and "schedule" in text:
        intent, action = "schedule_meeting", "schedule_meeting"
        summary = "I matched the customer and prepared an external calendar invitation for your approval."
        steps = ["Matching the customer account", "Preparing a time and meeting details", "Checking the external calendar action risk"]
    elif "meeting" in text and any(word in text for word in ("brief", "prepare", "tomorrow", "upcoming")):
        intent, action = "meeting_intelligence", "meeting_brief"
        summary = "I connected the upcoming meeting with recent customer conversations, account issues, and balances."
        steps = ["Finding the upcoming customer meeting", "Reviewing recent conversations and outstanding work", "Preparing concise talking points"]
    elif any(word in text for word in ("prepare reminder", "payment reminder", "send reminder", "remind acme", "remind the customer")):
        intent, action = "payment_followup", "prepare_reminder"
        summary = "I checked outstanding balances and customer history to prepare the most relevant payment follow-up."
        steps = ["Reviewing outstanding invoices", "Checking the customer's conversation history", "Drafting a polite reminder for approval"]
    elif "overdue" in text or "outstanding invoice" in text:
        intent, action = "overdue_invoice_report", "overdue_report"
        summary = "I reviewed invoice due dates and grouped the overdue balances by customer."
        steps = ["Reading invoice records", "Calculating overdue amounts and aging", "Summarizing the highest-priority balances"]
    elif "reply" in text or "respond" in text or "urgent" in text or "support" in text or "inbox" in text:
        intent, action = "customer_support", "prepare_reply"
        summary = "I reviewed the open customer conversations and prioritized issues by urgency and sentiment."
        steps = ["Reviewing open customer conversations", "Prioritizing urgency and sentiment", "Preparing a response for approval"]
    elif "which customers" in text and any(word in text for word in ("risk", "churn", "at risk")):
        intent, action = "customer_risk_report", "risk_report"
        summary = "I compared support load, sentiment, outstanding invoices, and follow-up signals across customer accounts."
        steps = ["Reviewing customer sentiment and support signals", "Comparing outstanding balances and follow-up gaps", "Ranking customer health and churn risk"]
    elif any(word in text for word in ("risk", "churn", "contact", "attention", "who should")):
        intent, action = "customer_priority", "none"
        summary = "I combined support issues, sentiment, overdue balances, and recent follow-up signals."
        steps = ["Comparing customer support and sentiment signals", "Checking overdue invoices and follow-up history", "Ranking the strongest reasons to make contact"]
    else:
        intent, action = "business_assistance", "none"
        summary = "I checked the business context for the signals most relevant to your request."
        steps = ["Loading customer, conversation, invoice, task, and calendar context", "Identifying the most relevant business signals", "Preparing a concise recommendation"]
    focus = selected
    if not focus:
        focus = max(customers, key=lambda c: c["risk_score"] + len(c["open_issues"]) * 13 + sum(i["amount"] for i in c["invoices"] if i["status"] == "overdue") / 2000)
    return {"intent": intent, "action": action, "summary": summary, "steps": steps, "focus_customer": focus["company"], "customer_named": selected is not None}


def create_plan(request: str, context: dict) -> dict:
    """Offline planner (fallback when no AI provider is reachable). Live reasoning lives in agent_loop.py."""
    plan = _fallback_plan(request, context)
    plan["source"] = "offline"
    return plan
