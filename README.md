# SMB OS

**Your AI operations team, with you in control.**

SMB OS is an AI operations manager that brings customer conversations, follow-ups, invoices, tasks, and meetings into one business-aware command center. It analyzes and prepares work automatically, while actions with external consequences go through human approval.

## What it is

An agentic operations manager for small businesses. It reads customer conversations, invoices, tasks and meetings, reasons over them with tools, prepares the work, and asks before anything leaves the building. Every decision is audited.

## Problem and solution

Small business owners lose time switching between conversations, customer records, follow-ups, invoices, and calendars to decide what deserves attention next. SMB OS adds an operations layer over that business context: it connects the signals, recommends a next step, prepares the work, and asks before it makes a consequential change.

### Tech stack

Next.js, TypeScript, Tailwind CSS, and a responsive component system on the frontend; FastAPI and Pydantic on the backend; SQLite and SQLAlchemy for persistence; Recharts-ready analytics surfaces; and structured LLM function calling with an offline fallback.

## Product and architecture

The MVP uses a modular monolith: Next.js/TypeScript/Tailwind for the product UI, FastAPI/Pydantic for the API, and SQLite/SQLAlchemy for persistence. The agent calls explicit tools; it does not write directly to the database. A business-context service collects customer, message, invoice, task, and calendar signals. A planner forms a concise action plan. A risk engine and approval service gate external writes, and an audit service retains a durable record.

```text
Owner → Command Center → SMB Operations Agent
                         ├─ Planner + business context
                         ├─ Explicit read / analysis / prepare tools
                         └─ Risk engine → Approval queue → Write tools
                                                    └─ Persistent audit log
```

### Why it is agentic

With an AI key (`OPENAI_API_KEY`, any OpenAI-compatible provider via `OPENAI_BASE_URL`) the model runs a **tool-calling loop** (max 6 steps): it calls read tools (overview, conversations, customer, invoices, meetings, tasks), reasons over the results, then calls `propose_email` / `propose_invoice` / `propose_meeting` and `finish`. `propose_*` only queues an item for approval; the model cannot send, create or schedule anything. Without a key, or if the provider fails, a deterministic offline planner keeps the demo working (the UI shows which mode ran). A proactive **morning brief** (`POST /api/agent/brief`, or `BRIEF_INTERVAL_MINUTES`) prepares the day's priority actions once per day without being asked.

### Safety layers (defence in depth)

1. **Prompt-injection guard**: inbound messages with instruction-like content are flagged, withheld from the model, can never be replied to by the agent, and surface as a security alert. A hostile demo email is seeded (Cloudline Travel).
2. **Server-side resolution**: the model passes a company name; recipients and customer IDs come from records, so it can't redirect mail or invoices.
3. **Strict payload schemas** on prepare, edit and approve (valid recipient, amount 1 to 1e7, meeting window).
4. **Context-aware risk engine** that only escalates: unknown recipient, key account, large invoice (≥ ₹1L), or an amount over 2× the customer's largest prior invoice. Edits at approval time are re-assessed.
5. **Never guess**: missing invoice amount or customer name triggers a question, not a default.
6. **Human approval + audit log** for every MEDIUM+ action; duplicate pending actions are suppressed.

### Risk and human oversight

The product risk model is LOW for reads, analysis, and preparation, MEDIUM for external communications and meetings, HIGH for official business records such as invoices, and CRITICAL for destructive or financial actions. MEDIUM and above must pass the approval service before execution. The Approval Center explains what will happen, why, and the information used. Every preparation, edit, decision, and execution is written to the persistent Activity log.

## Setup

Requirements: Python 3.10 or newer and Node.js 20 or newer.

In a terminal, start the API:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
cd ..
uvicorn backend.main:app --reload
```

In a second terminal, start the web app:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

The web app is at `http://localhost:3000`; the API is at `http://localhost:8000`. First launch creates `smb_os.db` (delete an old one to pick up the new demo data) and seeds 20 customers, 50 conversations, 25 tasks, 20 invoices, 15 meetings, and 105 activity records. API documentation is at `http://localhost:8000/docs`.

Frontend checks (from `frontend`): `npm run typecheck`, `npm run build`.

### Tests and evals

```bash
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q          # 10 tests: guard, validation, risk, agent loop (scripted model), approvals, auth
python -m backend.evals.run_evals          # 17 scenario evals incl. prompt-injection and "never guess" cases
```

### Docker

`docker compose up --build` starts the API on :8000 and the web app on :3000 (set `backend/.env` first). Not tested in the authoring environment.

## Environment

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`. Everything is optional: `OPENAI_API_KEY` (live agent), `API_KEY` + `NEXT_PUBLIC_API_KEY` (shared-secret gate, demo-grade only), `BRIEF_INTERVAL_MINUTES` (proactive mode), and `SMTP_*` for real email delivery after approval (`SMTP_REDIRECT_TO` sends everything to your own inbox for safe demos).

## Demo

1. Open Business Autopilot to see urgent issues, overdue invoices, customer risk, and tasks.
2. Choose **Let AI handle it** and review the multi-step plan and approval-ready customer replies.
3. Ask **Which customer should I contact right now?** to show the combined Acme support, payment, and meeting signals.
4. Ask **Create an invoice for Acme Corp for ₹25,000 for consulting** and review its HIGH risk approval.
5. Run "Take care of everything important today": note the red banner. The seeded hostile email was blocked from the AI and no reply was drafted to it.
6. Create an invoice for Vertex Solutions for ₹2 lakh: the risk engine escalates it to CRITICAL. Try an invoice with no amount: it asks instead of guessing.
7. Edit, approve, or reject a prepared action; then show the decision and outcome in Activity.

## API overview

`/api/health`, `/api/dashboard`, `/api/customers`, `/api/customers/{id}`, `/api/emails`, `/api/tasks`, `/api/invoices`, `/api/calendar`, `/api/approvals`, `/api/activity`, `/api/agent/command`, `/api/agent/brief`, `/api/security/alerts`. Task completion, task creation, approval decisions, and approval edits persist to SQLite.

## Known limits (honest)

- Customers, inbox, invoices and calendar are seeded local data. Only email delivery has a real provider (SMTP). Gmail/Calendar OAuth is the next integration.
- The injection guard is heuristic; it is one layer among several, not a guarantee.
- Auth is a single shared key. No per-user login or multi-tenancy.
- The live agent loop is tested against a scripted model, not against a real provider in CI.
- "Time saved" is an estimate from approved actions (6 / 10 / 5 minutes per email / invoice / meeting).

## Future roadmap

Replace the seeded sources through the same explicit tool interfaces with Gmail/Outlook, Google Calendar, CRM, accounting and WhatsApp. Add per-user auth and tenants, owner-configurable approval policies, and undo for executed actions. Keep the approval boundary and audit history consistent as integrations are added.
