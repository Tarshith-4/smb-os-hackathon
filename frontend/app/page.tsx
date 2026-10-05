"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ApprovalCenter from "./ApprovalCenter";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bell, Bot,
  CalendarDays, Check, CheckCheck, ChevronDown, ChevronRight, CircleDollarSign,
  Clock3, Command, FileText, Inbox, LayoutDashboard, ListTodo, LoaderCircle, Mail,
  Menu, MessageSquare, MoreHorizontal, Plus, Search, Send, Settings2, ShieldCheck,
  Sparkles, Users, X, Zap,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";
const apiFetch = (url: string, init: RequestInit = {}) => fetch(url, { ...init, headers: { ...(init.headers as Record<string, string> | undefined), ...(API_KEY ? { "X-API-Key": API_KEY } : {}) } });
type Page = "Overview" | "AI Command Center" | "Customers" | "Inbox" | "Tasks" | "Invoices" | "Approvals" | "Insights" | "Activity" | "Settings";
type Row = Record<string, any>;
type Store = { dashboard: Row | null; customers: Row[]; emails: Row[]; tasks: Row[]; invoices: Row[]; calendar: Row[]; approvals: Row[]; activity: Row[] };
const emptyStore: Store = { dashboard: null, customers: [], emails: [], tasks: [], invoices: [], calendar: [], approvals: [], activity: [] };
const nav: { name: Page; icon: any; group: string }[] = [
  { name: "Overview", icon: LayoutDashboard, group: "WORKSPACE" },
  { name: "AI Command Center", icon: Sparkles, group: "WORKSPACE" },
  { name: "Customers", icon: Users, group: "WORKSPACE" },
  { name: "Inbox", icon: Inbox, group: "WORKSPACE" },
  { name: "Tasks", icon: ListTodo, group: "WORKSPACE" },
  { name: "Invoices", icon: FileText, group: "WORKSPACE" },
  { name: "Approvals", icon: ShieldCheck, group: "MANAGE" },
  { name: "Insights", icon: Zap, group: "MANAGE" },
  { name: "Activity", icon: Activity, group: "MANAGE" },
  { name: "Settings", icon: Settings2, group: "MANAGE" },
];
const money = (amount: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount || 0);
const shortMoney = (amount: number) => amount >= 100000 ? `₹${(amount / 100000).toFixed(amount % 100000 === 0 ? 0 : 1)}L` : money(amount);
const initials = (s = "?") => s.split(/[\s&]+/).filter(Boolean).slice(0, 2).map((v) => v[0]).join("").toUpperCase();
const timeAgo = (value?: string) => {
  if (!value) return "Recently";
  const hours = Math.max(1, Math.floor((Date.now() - new Date(/Z|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z").getTime()) / 3600000));
  return hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
};

export default function Home() {
  const [page, setPage] = useState<Page>("Overview");
  const [data, setData] = useState<Store>(emptyStore);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [command, setCommand] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<Row | null>(null);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState("");
  const [busyApproval, setBusyApproval] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    const endpoints = ["dashboard", "customers", "emails", "tasks", "invoices", "calendar", "approvals", "activity"];
    try {
      const results = await Promise.all(endpoints.map(async (endpoint) => {
        const res = await apiFetch(`${API}/${endpoint}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`${endpoint} ${res.status}`);
        return res.json();
      }));
      setData({ dashboard: results[0], customers: results[1], emails: results[2], tasks: results[3], invoices: results[4], calendar: results[5], approvals: results[6], activity: results[7] });
      setApiError("");
    } catch {
      setApiError("We can’t reach the SMB OS service right now. Start the API to load your live demo data.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (toast) { const timer = setTimeout(() => setToast(""), 3600); return () => clearTimeout(timer); } }, [toast]);
  const pendingApprovals = useMemo(() => data.approvals.filter((a) => a.status === "pending"), [data.approvals]);
  const metrics = data.dashboard?.metrics || {};

  async function submitCommand(value = command) {
    const text = value.trim(); if (!text || running) return;
    setPage("AI Command Center"); setCommand(text); setRunning(true); setRunResult(null);
    try {
      const res = await apiFetch(`${API}/agent/command`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "The agent couldn't finish that request.");
      setRunResult(result); await refresh();
    } catch (error: any) { setToast(error.message || "The operations agent is temporarily unavailable."); }
    finally { setRunning(false); }
  }

  async function decide(id: number, decision: "approve" | "reject", edited_payload?: Row) {
    setBusyApproval(id);
    try {
      const res = await apiFetch(`${API}/approvals/${id}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, edited_payload }) });
      const result = await res.json(); if (!res.ok) throw new Error(result.detail || "Could not update approval.");
      setToast(decision === "approve" ? "Approved and completed. Activity has been recorded." : "Action rejected and recorded.");
      await refresh();
    } catch (error: any) { setToast(error.message || "Could not update approval."); }
    finally { setBusyApproval(null); }
  }

  async function saveApprovalEdit(id: number, payload: Row) {
    try {
      const res = await apiFetch(`${API}/approvals/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload }) });
      const result = await res.json(); if (!res.ok) throw new Error(result.detail || "Could not save the edit.");
      setToast("Draft updated. Review it, then approve when you’re ready."); await refresh();
    } catch (error: any) { setToast(error.message || "Could not save the edit."); }
  }

  async function updateTask(task: Row) {
    try {
      const status = task.status === "completed" ? "open" : "completed";
      const res = await apiFetch(`${API}/tasks/${task.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
      const result = await res.json(); if (!res.ok) throw new Error(result.detail || "Could not update the task.");
      setToast(status === "completed" ? "Task completed and added to activity." : "Task reopened."); await refresh();
    } catch (error: any) { setToast(error.message || "Could not update the task."); }
  }

  async function createTask() {
    const title = window.prompt("What needs to get done?"); if (!title?.trim()) return;
    try {
      const res = await apiFetch(`${API}/tasks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim(), due_date: new Date().toISOString().slice(0, 10) }) });
      const result = await res.json(); if (!res.ok) throw new Error(result.detail || "Could not create the task.");
      setToast("Task created and added to activity."); await refresh();
    } catch (error: any) { setToast(error.message || "Could not create the task."); }
  }

  function editApproval(row: Row) {
    const payload = row.action.payload || {};
    if (row.action.type === "SEND_EMAIL") {
      const edited = window.prompt("Edit the email draft:", payload.body || "");
      if (edited !== null && edited.trim()) saveApprovalEdit(row.id, { ...payload, body: edited.trim() });
    } else if (row.action.type === "SCHEDULE_MEETING") {
      const edited = window.prompt("Edit the calendar date and time (ISO format):", payload.starts_at || "");
      if (edited !== null && !Number.isNaN(Date.parse(edited))) saveApprovalEdit(row.id, { ...payload, starts_at: new Date(edited).toISOString() });
    } else {
      const description = window.prompt("Edit the invoice description:", payload.description || "Consulting services");
      if (description !== null && description.trim()) saveApprovalEdit(row.id, { ...payload, description: description.trim() });
    }
  }

  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark"><span>s</span><span className="brand-spark">✦</span></div><span className="brand-name">smb<span>os</span></span><button className="sidebar-collapse" aria-label="Close menu" onClick={() => setMenuOpen(false)}><X size={17}/></button></div>
      <div className="workspace-switch"><div className="workspace-avatar">N</div><span><b>Northstar Studio</b><small>Business workspace</small></span></div>
      <div className="nav-wrap">
        {(["WORKSPACE", "MANAGE"] as const).map((group) => <div className="nav-group" key={group}><p className="nav-label">{group}</p>{nav.filter((item) => item.group === group).map(({ name, icon: Icon }) => <button key={name} className={`nav-item ${page === name ? "active" : ""}`} onClick={() => { setPage(name); setMenuOpen(false); }}><Icon size={17} strokeWidth={1.8}/><span>{name}</span>{name === "Approvals" && pendingApprovals.length > 0 && <em className="nav-count">{pendingApprovals.length}</em>}{name === "Inbox" && data.emails.filter((e) => e.status === "open").length > 0 && <i className="nav-dot"/>}</button>)}</div>)}
      </div>
      <div className="sidebar-bottom"><div className="upgrade-card"><div className="upgrade-icon"><Sparkles size={16}/></div><b>Meet your new ops team</b><p>Your business context, all in one place.</p><button onClick={() => setPage("AI Command Center")}>Explore AI copilot <ArrowRight size={14}/></button></div><div className="profile-row"><div className="avatar avatar-user">JD</div><span><b>Jamie Davidson</b><small>Owner account</small></span></div></div>
    </aside>
    {menuOpen && <button aria-label="Close sidebar" className="mobile-scrim" onClick={() => setMenuOpen(false)}/>}
    <main className="main-shell">
      <header className="topbar"><div className="topbar-left"><button className="mobile-menu" aria-label="Open menu" onClick={() => setMenuOpen(true)}><Menu size={20}/></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14}/><b>{page}</b></div></div><div className="topbar-right"><button className="search-trigger" onClick={() => { setPage("AI Command Center"); document.getElementById("command-input")?.focus(); }}><Search size={16}/><span>Search anything</span><kbd>⌘ K</kbd></button><span className="topbar-divider"/><button className="icon-button" aria-label="Notifications" onClick={() => setPage("Approvals")}><Bell size={18}/>{pendingApprovals.length > 0 && <i/>}</button><div className="avatar avatar-top">JD</div></div></header>
      <div className="content-wrap">
        {apiError && <div className="api-banner"><AlertTriangle size={16}/><span>{apiError}</span><button onClick={refresh}>Try again</button></div>}
        {loading ? <LoadingState/> : <>
          {page === "Overview" && <OverviewPage data={data} metrics={metrics} onNavigate={setPage} onCommand={submitCommand} pending={pendingApprovals.length} onToggleTask={updateTask}/>}
          {page === "AI Command Center" && <CommandPage command={command} setCommand={setCommand} running={running} result={runResult} onSubmit={submitCommand} onNavigate={setPage}/>}
          {page === "Customers" && <CustomersPage customers={data.customers} query={query} setQuery={setQuery} onCommand={submitCommand}/>}
          {page === "Inbox" && <InboxPage emails={data.emails} onCommand={submitCommand} onNavigate={setPage}/>}
          {page === "Tasks" && <TasksPage tasks={data.tasks} onCommand={submitCommand} onToggleTask={updateTask} onCreateTask={createTask}/>}
          {page === "Invoices" && <InvoicesPage invoices={data.invoices} onCommand={submitCommand}/>}
          {page === "Approvals" && <ApprovalCenter rows={data.approvals} busy={busyApproval} onDecide={decide} onEdit={editApproval}/>}
          {page === "Insights" && <InsightsPage data={data} onCommand={submitCommand} onNavigate={setPage}/>}
          {page === "Activity" && <ActivityPage rows={data.activity}/>}
          {page === "Settings" && <SettingsPage/>}
        </>}
      </div>
    </main>
    {toast && <div className="toast"><CheckCircleIcon/><span>{toast}</span><button onClick={() => setToast("")} aria-label="Dismiss"><X size={15}/></button></div>}
  </div>;
}

function CheckCircleIcon() { return <span className="toast-check"><Check size={13}/></span>; }
function LoadingState() { return <div className="loading-page"><div className="loading-logo"><Sparkles size={19}/></div><div className="loading-line"/><div className="loading-line short"/><div className="loading-grid">{[1,2,3,4].map((x) => <div key={x} className="skeleton-card"/>)}</div><p>Bringing your business into focus…</p></div>; }

function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}
function MetricCard({ label, value, trend, note, icon: Icon, tint = "blue" }: any) {
  return <div className="metric-card"><div className="metric-top"><div className={`metric-icon ${tint}`}><Icon size={17}/></div>{trend ? <span className="metric-trend"><ArrowUpRight size={13}/>{trend}</span> : <span/>}</div><p className="metric-value">{value}</p><div className="metric-bottom"><b>{label}</b><span>{note}</span></div></div>;
}
function SectionTitle({ title, action, onClick }: { title: string; action?: string; onClick?: () => void }) { return <div className="section-title"><h2>{title}</h2>{action && onClick && <button onClick={onClick}>{action}<ArrowRight size={14}/></button>}</div>; }
function Severity({ value }: { value: string }) { const lower = (value || "normal").toLowerCase(); return <span className={`severity severity-${lower}`}>{lower === "high" || lower === "critical" ? <i/> : null}{lower}</span>; }
function RiskBadge({ score }: { score: number }) { const level = score >= 65 ? "At risk" : score >= 35 ? "Monitor" : "Healthy"; return <span className={`risk-badge ${score >= 65 ? "risk-high" : score >= 35 ? "risk-mid" : "risk-low"}`}><i/>{level}</span>; }
function Avatar({ name, index = 0 }: { name: string; index?: number }) { return <div className={`avatar customer-avatar c${index % 6}`}>{initials(name)}</div>; }

function OverviewPage({ data, metrics, onNavigate, onCommand, pending, onToggleTask }: any) {
  const auto = data.dashboard?.autopilot || {};
  const today = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric" }).format(new Date());
  const dueTasks = data.tasks.filter((t: Row) => t.status === "open").slice(0, 4);
  const risky = data.customers.filter((c: Row) => c.risk_score >= 65).slice(0, 3);
  const urgent = data.emails.filter((e: Row) => e.status === "open" && e.priority === "high").slice(0, 3);
  return <>
    <PageHeading eyebrow={today} title="Good morning, Jamie" description="Here’s what your business needs today." action={<button className="button button-quiet" onClick={() => onNavigate("Insights")}><CalendarDays size={16}/> This week <ChevronDown size={15}/></button>}/>
    <div className="metrics-grid">
      <MetricCard label="Time saved (est.)" value={`${metrics.time_saved_hours ?? 0} hrs`} trend="" note="from approved actions" icon={Clock3} tint="violet"/>
      <MetricCard label="Tasks automated" value={metrics.tasks_automated || 84} trend="12%" note="this month" icon={Zap} tint="amber"/>
      <MetricCard label="Customer issues" value={metrics.customer_issues ?? 0} trend="6 open" note="needs attention" icon={MessageSquare} tint="rose"/>
      <MetricCard label="Revenue" value={shortMoney(metrics.revenue_inr || 320000)} trend="8.2%" note="this month" icon={CircleDollarSign} tint="green"/>
    </div>

    <section className="autopilot-card">
      <div className="autopilot-glow"/><div className="autopilot-main"><div className="autopilot-kicker"><span className="live-dot"/> BUSINESS AUTOPILOT <span className="autopilot-context">YOUR OPERATIONS AT A GLANCE</span></div><h2>Your business needs attention<br className="desktop-break"/> in <span>{Math.max(3, (auto.urgent_issues || 0) + (auto.overdue_followups ? 1 : 0) + (auto.customers_at_risk || 0))} areas.</span></h2><p>We’ve connected the dots. Here’s where a little attention can make the biggest difference today.</p><div className="autopilot-signals">
        <div><span className="signal-icon signal-red"><MessageSquare size={15}/></span><b>{auto.urgent_issues || 3}</b><small>urgent customer issues</small></div>
        <div><span className="signal-icon signal-amber"><ArrowDownRight size={15}/></span><b>{auto.overdue_followups || 4}</b><small>overdue follow-ups</small></div>
        <div><span className="signal-icon signal-orange"><CircleDollarSign size={15}/></span><b>{shortMoney(auto.outstanding_inr || metrics.outstanding_inr || 84500)}</b><small>overdue invoices</small></div>
        <div><span className="signal-icon signal-yellow"><Users size={15}/></span><b>{auto.customers_at_risk || 2}</b><small>customers at risk</small></div>
        <div><span className="signal-icon signal-blue"><ListTodo size={15}/></span><b>{auto.tasks_due_today || 5}</b><small>tasks due today</small></div>
      </div></div><div className="autopilot-action"><div className="autopilot-spark"><Sparkles size={20}/></div><span>Let AI take the busywork</span><button className="button button-light" onClick={() => onCommand("Take care of everything important today.")}><Sparkles size={15}/> Let AI handle it <ArrowRight size={15}/></button><small>Review every action before it goes out</small></div>
    </section>

    {(data.dashboard?.security_alerts || []).length > 0 && <div className="security-banner"><AlertTriangle size={15}/><span><b>{data.dashboard.security_alerts.length} suspicious message{data.dashboard.security_alerts.length > 1 ? "s" : ""} blocked from the AI</b> · {data.dashboard.security_alerts.map((a: Row) => `${a.customer}: “${a.subject}” (${a.flags.join(", ")})`).join(" | ")}. Review manually in Inbox.</span></div>}<div className="overview-columns"><section className="panel priorities-panel"><SectionTitle title="Today’s priorities" action="View all" onClick={() => onNavigate("Tasks")}/><div className="priority-list">
      {(data.dashboard?.priorities || []).map((p: Row, i: number) => <button className="priority-row" key={p.title} onClick={() => onCommand(i === 0 ? "Handle the urgent customer issues" : i === 1 ? "Prepare my follow-ups" : "Show me overdue invoices")}><span className={`priority-mark p-${p.priority}`}/><span className="priority-copy"><b>{p.title}</b><small>{p.detail}</small></span><ChevronRight size={16}/></button>)}
    </div><div className="priority-footer"><span><Clock3 size={14}/> Updated just now</span><button onClick={() => onNavigate("AI Command Center")}>Ask AI to prioritize <ArrowRight size={14}/></button></div></section>
      <section className="panel health-panel"><SectionTitle title="Customer health" action="All customers" onClick={() => onNavigate("Customers")}/><div className="health-summary"><div className="health-donut"><div><b>{data.customers.length - risky.length}</b><span>healthy</span></div></div><div className="health-legend"><div><i className="dot-green"/><span>Healthy</span><b>{data.customers.length - risky.length}</b></div><div><i className="dot-amber"/><span>Needs a check-in</span><b>{Math.max(0, data.customers.filter((c: Row) => c.risk_score >= 35 && c.risk_score < 65).length)}</b></div><div><i className="dot-red"/><span>At risk</span><b>{risky.length}</b></div></div></div><div className="health-list">{risky.map((c: Row, i: number) => <button className="health-customer" key={c.id} onClick={() => onNavigate("Customers")}><Avatar name={c.company} index={i}/><span><b>{c.company}</b><small>{c.risk_reason}</small></span><RiskBadge score={c.risk_score}/></button>)}</div></section></div>

    <div className="overview-columns lower-columns"><section className="panel inbox-preview"><SectionTitle title="Needs a reply" action="Open inbox" onClick={() => onNavigate("Inbox")}/>{urgent.length ? urgent.map((e: Row, i: number) => <div className="inbox-row" key={e.id}><Avatar name={e.customer} index={i}/><div className="inbox-row-copy"><div><b>{e.customer}</b><span>{timeAgo(e.received_at)}</span></div><strong>{e.subject}</strong><p>{e.message}</p></div><Severity value={e.priority}/></div>) : <Empty message="You’re all caught up."/>}</section>
      <section className="panel task-preview"><SectionTitle title="Your next steps" action="View tasks" onClick={() => onNavigate("Tasks")}/>{dueTasks.map((t: Row, i: number) => <div className="task-row" key={t.id}><button className={`task-check ${t.status === "completed" ? "checked" : ""}`} onClick={() => onToggleTask(t)} aria-label="Mark task complete"><Check size={12}/></button><span className="task-copy"><b>{t.title}</b><small>{t.customer || "Internal"}</small></span><span className={`task-due ${t.due_date < new Date().toISOString().slice(0,10) ? "overdue" : ""}`}>{i === 0 ? "Today" : t.due_date}</span></div>)}</section></div>
    <div className="impact-strip"><div className="impact-icon"><Sparkles size={17}/></div><div><b>Your team’s AI impact</b><span>Quietly taking care of the busywork, so you can focus on what matters.</span></div><div className="impact-stat"><b>{metrics.tasks_automated ?? 0}</b><small>actions automated</small></div><div className="impact-stat"><b>{pending}</b><small>awaiting your approval</small></div><button onClick={() => onNavigate("Insights")}>See the impact <ArrowRight size={14}/></button></div>
    {pending > 0 && <button className="floating-approval" onClick={() => onNavigate("Approvals")}><span><ShieldCheck size={17}/></span><b>{pending} action{pending === 1 ? "" : "s"} waiting for you</b><ArrowRight size={16}/></button>}
  </>;
}

function CommandPage({ command, setCommand, running, result, onSubmit, onNavigate }: any) {
  const prompts = ["What needs my attention today?", "Which customers are at risk?", "Prepare my follow-ups", "Show me overdue invoices", "Give me my weekly business report", "Create an invoice for Acme Corp for ₹25,000 for consulting"];
  return <><PageHeading eyebrow="YOUR OPERATIONS COPILOT" title="What can I take care of?" description="Ask in your own words. I’ll connect the dots and prepare the right next steps."/>
    <div className="command-hero"><div className="command-orb"><Sparkles size={21}/></div><div className="command-intro"><b>Good morning, Jamie.</b><span>I’m up to speed on your customers, conversations, and cash flow.</span></div><div className="command-input-wrap"><textarea id="command-input" rows={2} value={command} onChange={(e) => setCommand(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmit(); } }} placeholder="Ask your AI operations manager…"/><div className="command-input-bottom"><span><Command size={13}/> Your data stays in your workspace</span><button className="button button-primary" disabled={!command.trim() || running} onClick={() => onSubmit()}>{running ? <LoaderCircle className="spin" size={15}/> : <Sparkles size={15}/>} {running ? "Working" : "Ask SMB OS"}<ArrowRight size={14}/></button></div></div>
      {!result && !running && <div className="suggested-prompts"><span>Try asking</span>{prompts.map((p) => <button key={p} onClick={() => onSubmit(p)}>{p}<ArrowUpRight size={13}/></button>)}</div>}
    </div>
    {running && <div className="panel agent-running"><div className="agent-running-head"><span className="agent-icon"><Sparkles size={16}/></span><div><b>SMB Operations Agent</b><small>Working across your business context</small></div><LoaderCircle className="spin" size={17}/></div><div className="agent-steps">{["Understanding your request", "Loading customer, inbox, invoice and calendar context", "Finding the signals that matter", "Preparing next steps"].map((s, i) => <div key={s} className={`agent-step ${i === 0 ? "step-done" : "step-active"}`}><span>{i === 0 ? <Check size={12}/> : <span className="step-pulse"/>}</span>{s}</div>)}</div></div>}
    {result && <div className="agent-result"><div className="agent-result-head"><div><span className="agent-icon"><Sparkles size={16}/></span><span><b>SMB Operations Agent</b><small>{result.ai_mode === "live" ? "Live AI agent · tool-calling loop" : "Offline planner"} · Run #{result.run_id}</small></span></div><span className="complete-pill"><Check size={13}/> Completed</span></div>
      {(result.security_alerts || []).length > 0 && <div className="security-banner"><AlertTriangle size={15}/><span><b>{result.security_alerts.length} suspicious message{result.security_alerts.length > 1 ? "s" : ""} blocked from the AI</b> · {result.security_alerts.map((a: Row) => `${a.customer}: ${a.flags.join(", ")}`).join(" | ")}</span></div>}<div className="agent-result-grid"><section className="agent-summary"><div className="result-label">WHAT I FOUND</div><h2>{result.summary}</h2>{result.report?.focus_customer && <div className="focus-callout"><div className="focus-avatar">{initials(result.focus_customer)}</div><div><b>{result.focus_customer}</b><small>{result.report.priority} PRIORITY · {result.report.signals?.join(" · ")}</small></div><span className="focus-pill">{result.report.priority || "HIGH"}</span></div>}{result.report?.recommendation && <div className="recommendation"><span><Sparkles size={14}/></span><p>{result.report.recommendation}</p></div>}{result.report?.talking_points && <div className="brief-points"><div className="result-label">MEETING TALKING POINTS</div>{result.report.talking_points.map((point: string, i: number) => <div key={i}><span>{i + 1}</span>{point}</div>)}<small>{result.report.meeting?.starts_at ? `Upcoming meeting: ${new Date(result.report.meeting.starts_at).toLocaleString()}. ` : ""}Last discussion: {result.report.last_discussion}</small></div>}{result.report?.risky_customers && <div className="risk-report-list">{result.report.risky_customers.map((customer: Row, i: number) => <div key={customer.company}><Avatar name={customer.company} index={i}/><span><b>{customer.company}</b><small>{customer.open_issues} open issues · {money(customer.overdue_inr)} overdue · {customer.reason}</small></span><RiskBadge score={customer.risk_score}/></div>)}</div>}{result.report?.invoices && <div className="report-invoices"><div className="result-label">OVERDUE INVOICES</div>{result.report.invoices.map((invoice: Row) => <div key={invoice.number}><span><b>{invoice.customer}</b><small>{invoice.number} · due {invoice.due_date}</small></span><strong>{money(invoice.amount)}</strong></div>)}</div>}{result.report?.support && <div className="weekly-stats"><div><b>{result.report.support.conversations}</b><span>conversations</span></div><div><b>{result.report.support.pending}</b><span>pending</span></div><div><b>{shortMoney(result.report.revenue.outstanding_inr)}</b><span>outstanding</span></div><div><b>{result.report.customers_at_risk}</b><span>at risk</span></div></div>}</section>
        <section className="agent-trace"><div className="result-label">EXECUTION TRACE</div>{(result.trace || []).map((step: string, i: number) => <div className={`trace-row ${step.startsWith("⚠") ? "trace-warning" : ""}`} key={i}><span>{step.startsWith("⚠") ? <AlertTriangle size={14}/> : <Check size={14}/>}</span>{step.replace(/^✓ |^⚠ /, "")}</div>)}<div className="trace-tools"><span>TOOLS USED</span><b>{(result.tools_used || []).map((t: string) => <span className="tool-chip" key={t}>{t.replace(/_/g, " ")}</span>)}</b></div></section></div>
      {result.prepared_actions?.length > 0 && <div className="prepared-actions"><div className="prepared-actions-heading"><div><ShieldCheck size={17}/><b>{result.prepared_actions.length} action{result.prepared_actions.length === 1 ? "" : "s"} need your approval</b></div><button onClick={() => onNavigate("Approvals")}>Review actions <ArrowRight size={14}/></button></div>{result.prepared_actions.map((a: Row) => <div className="prepared-row" key={a.action_id}><span className="prepared-alert"><Mail size={15}/></span><span><b>{a.title}</b><small>{a.risk_level} risk · You stay in control</small></span><span className="awaiting">Awaiting review</span></div>)}</div>}
      <div className="agent-result-footer"><span><CheckCheck size={14}/> Your business activity has been recorded</span><button onClick={() => { setCommand(""); }}>Ask another question <ArrowRight size={14}/></button></div>
    </div>}
    {!result && !running && <div className="command-bottom-grid"><div className="mini-card"><span className="mini-icon indigo"><Users size={16}/></span><div><b>Customer intelligence</b><small>Spot risk before it becomes churn.</small></div><button onClick={() => onNavigate("Customers")}><ArrowRight size={15}/></button></div><div className="mini-card"><span className="mini-icon mint"><ShieldCheck size={16}/></span><div><b>Human in the loop</b><small>Review every action that matters.</small></div><button onClick={() => onNavigate("Approvals")}><ArrowRight size={15}/></button></div></div>}
  </>;
}

function CustomersPage({ customers, query, setQuery, onCommand }: any) {
  const filtered = customers.filter((c: Row) => `${c.company} ${c.name} ${c.email}`.toLowerCase().includes(query.toLowerCase()));
  return <><PageHeading eyebrow="RELATIONSHIPS, UNDERSTOOD" title="Customers" description={`${customers.length} relationships, with the context to know who needs you next.`} action={<button className="button button-primary" onClick={() => onCommand("Which customers should I contact today?")}><Sparkles size={15}/> Find who needs me <ArrowRight size={14}/></button>}/>
    <div className="list-toolbar"><div className="list-search"><Search size={16}/><input placeholder="Search customers…" value={query} onChange={(e) => setQuery(e.target.value)}/></div><span className="toolbar-count">{filtered.length} customers · highest risk first</span></div>
    <div className="panel table-panel"><div className="data-table customer-table"><div className="table-head"><span>CUSTOMER</span><span>HEALTH</span><span>OPEN ITEMS</span><span>REVENUE</span><span>LAST ACTIVE</span><span/></div>{filtered.map((c: Row, i: number) => <div className="table-row customer-table-row" key={c.id}><div className="customer-cell"><Avatar name={c.company} index={i}/><span><b>{c.company}</b><small>{c.name} · {c.email}</small></span></div><div><RiskBadge score={c.risk_score}/>{c.risk_score >= 65 && <small className="risk-explain">{c.risk_reason}</small>}</div><div className="open-items"><span className={c.open_issues ? "items-hot" : ""}>{c.open_issues} issues</span><small>{shortMoney(c.outstanding_invoices)} outstanding</small></div><b className="table-revenue">{shortMoney(c.revenue)}</b><span className="muted table-last">{timeAgo(c.last_interaction)}</span><button className="row-more" aria-label={`Actions for ${c.company}`} onClick={() => onCommand(`Prepare a personalized follow-up for ${c.company}`)}><MoreHorizontal size={17}/></button></div>)}</div>{filtered.length === 0 && <Empty message="No customers match that search."/>}</div>
    <div className="cross-system-note"><span><Sparkles size={16}/></span><p><b>One connected picture.</b> Customer health weighs open issues, sentiment, overdue balances, follow-up history, and upcoming meetings together.</p><button onClick={() => onCommand("Which customer should I contact right now?")}>Show me who needs a call <ArrowRight size={14}/></button></div>
  </>;
}

function InboxPage({ emails, onCommand, onNavigate }: any) {
  const open = emails.filter((e: Row) => e.status === "open");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<Row | null>(null);
  const rows = (filter === "all" ? emails : filter === "open" ? open : emails.filter((e: Row) => e.priority === filter));
  return <><PageHeading eyebrow="CUSTOMER SUPPORT, WITH CONTEXT" title="Inbox" description="Every conversation classified, prioritized, and ready for a thoughtful response." action={<button className="button button-primary" onClick={() => onCommand("Handle today's urgent customer issues")}><Sparkles size={15}/> Triage with AI</button>}/>
    <div className="inbox-toolbar"><div className="filter-tabs">{[["all", "All messages"], ["open", "Needs attention"], ["high", "High priority"]].map(([id, label]) => <button className={filter === id ? "selected" : ""} key={id} onClick={() => setFilter(id)}>{label}{id === "open" && <span>{open.length}</span>}</button>)}</div><span className="toolbar-count">{rows.length} conversations</span></div>
    <div className="panel inbox-full">{rows.map((e: Row, i: number) => <button className={`inbox-full-row ${selected?.id === e.id ? "selected" : ""}`} key={e.id} onClick={() => setSelected(e)}><Avatar name={e.customer} index={i}/><span className="inbox-full-main"><span className="inbox-full-top"><b>{e.customer}</b><span>{timeAgo(e.received_at)}</span></span><strong>{e.subject}</strong><small>{e.message}</small><span className="inbox-tags"><span className="category-tag">{e.category}</span><Severity value={e.priority}/><span className={`sentiment sentiment-${e.sentiment}`}>{e.sentiment}</span></span></span>{e.status === "open" && <span className="unread-dot"/>}</button>)}{rows.length === 0 && <Empty message="No conversations in this view."/>}</div>
    {selected && <div className="conversation-backdrop" onClick={() => setSelected(null)}><div className="conversation-drawer" onClick={(e) => e.stopPropagation()}><div className="drawer-head"><div><Avatar name={selected.customer}/><span><b>{selected.customer}</b><small>{selected.subject}</small></span></div><button onClick={() => setSelected(null)}><X size={18}/></button></div><div className="drawer-meta"><span>{selected.category}</span><Severity value={selected.priority}/><span>{timeAgo(selected.received_at)}</span></div><div className="conversation-message"><div className="message-sender"><Avatar name={selected.customer}/><span><b>{selected.customer}</b><small>{selected.received_at ? new Date(selected.received_at).toLocaleString() : "Recently"}</small></span></div><p>{selected.message}</p></div><div className="ai-draft"><div className="draft-title"><span><Sparkles size={14}/></span><b>AI-drafted response</b><small>Ready for your review</small></div><p>{selected.ai_draft || `Hi,\n\nThank you for reaching out. I'm sorry you're experiencing this. I've shared your message with the team and we'll follow up with a clear update shortly.\n\nBest,\nSupport Team`}</p><button className="button button-primary" onClick={() => { setSelected(null); onCommand(`Reply to the urgent support email for ${selected.customer}`); onNavigate("AI Command Center"); }}><Sparkles size={14}/> Prepare for approval</button></div><div className="drawer-trust"><ShieldCheck size={15}/> Sending always requires your approval</div></div></div>}
  </>;
}

function TasksPage({ tasks, onCommand, onToggleTask, onCreateTask }: any) {
  const [show, setShow] = useState("open"); const rows = show === "all" ? tasks : tasks.filter((t: Row) => t.status === "open");
  return <><PageHeading eyebrow="FOLLOW-THROUGH, MADE LIGHTER" title="Tasks" description="The next right steps, pulled together from your customer activity." action={<button className="button button-primary" onClick={() => onCommand("Prepare my follow-ups")}><Sparkles size={15}/> Prepare follow-ups</button>}/><div className="list-toolbar"><div className="filter-tabs"><button className={show === "open" ? "selected" : ""} onClick={() => setShow("open")}>Open <span>{tasks.filter((t: Row) => t.status === "open").length}</span></button><button className={show === "all" ? "selected" : ""} onClick={() => setShow("all")}>All tasks</button></div><button className="button button-quiet" onClick={onCreateTask}><Plus size={15}/> New task</button></div><div className="panel task-list-full">{rows.map((t: Row) => <div className="task-full-row" key={t.id}><button className={`task-check ${t.status === "completed" ? "checked" : ""}`} onClick={() => onToggleTask(t)} aria-label={t.status === "completed" ? "Reopen task" : "Mark task complete"}><Check size={12}/></button><div className="task-full-copy"><b>{t.title}</b><small>{t.description}</small><div><span>{t.customer || "Internal task"}</span>{t.automated && <span className="ai-label"><Sparkles size={11}/> AI prepared</span>}</div></div><Severity value={t.priority}/><span className={`due-label ${t.due_date < new Date().toISOString().slice(0, 10) ? "overdue" : ""}`}><CalendarDays size={13}/>{t.due_date}</span></div>)}</div><div className="note-bar"><span><Sparkles size={15}/></span><p>Tasks marked “AI prepared” were identified from customer conversations and account activity. They won’t send or change anything on their own.</p></div></>;
}

function InvoicesPage({ invoices, onCommand }: any) {
  const overdue = invoices.filter((i: Row) => i.status === "overdue"); const total = overdue.reduce((n: number, i: Row) => n + i.amount, 0);
  return <><PageHeading eyebrow="A CLEARER VIEW OF CASH FLOW" title="Invoices" description="Know what’s coming in, what needs a nudge, and what has been paid." action={<button className="button button-primary" onClick={() => onCommand("Create an invoice for Acme Corp for ₹25,000 for consulting")}><Plus size={15}/> Prepare invoice</button>}/><div className="invoice-summary"><div><span className="invoice-summary-icon"><CircleDollarSign size={18}/></span><span><small>OVERDUE BALANCE</small><b>{money(total)}</b></span><i><ArrowUpRight size={14}/>{overdue.length} invoices</i></div><button className="button button-quiet" onClick={() => onCommand("Prepare payment reminders for overdue invoices")}><Sparkles size={14}/> Prepare reminders <ArrowRight size={14}/></button></div><div className="panel table-panel"><div className="data-table invoice-table"><div className="table-head"><span>INVOICE</span><span>CUSTOMER</span><span>ISSUED</span><span>DUE DATE</span><span>AMOUNT</span><span>STATUS</span></div>{invoices.map((i: Row) => <div className="table-row" key={i.id}><span><b className="invoice-number">{i.number}</b><small className="table-subtitle">{i.description}</small></span><span className="invoice-customer">{i.customer}</span><span className="muted">{i.issued_date}</span><span className={i.status === "overdue" ? "overdue-text" : "muted"}>{i.due_date}</span><b>{money(i.amount)}</b><span className={`invoice-status status-${i.status}`}>{i.status}</span></div>)}</div></div><div className="note-bar"><span><ShieldCheck size={15}/></span><p>Creating an official invoice or sending a payment reminder always waits for your approval.</p></div></>;
}

function ApprovalsPage({ rows, busy, onDecide, onEdit }: any) {
  const pending = rows.filter((r: Row) => r.status === "pending"); const history = rows.filter((r: Row) => r.status !== "pending");
  return <><PageHeading eyebrow="HUMAN OVERSIGHT" title="Approval center" description="The AI handles the prep. You decide what goes out into the world." action={<div className="approval-safe"><ShieldCheck size={16}/><span>Nothing sends without you</span></div>}/>{pending.length ? <><div className="approval-count-bar"><span className="approval-count-icon"><ShieldCheck size={17}/></span><div><b>{pending.length} {pending.length === 1 ? "action is" : "actions are"} ready for your review</b><small>Each recommendation explains what happens and why.</small></div><span className="awaiting">NEEDS YOUR REVIEW</span></div><div className="approval-grid">{pending.map((r: Row) => { const a = r.action; const payload = a.payload || {}; const isEmail = a.type === "SEND_EMAIL"; return <article className="approval-card" key={r.id}><div className="approval-card-top"><span className={`approval-action-icon ${isEmail ? "email" : "invoice"}`}>{isEmail ? <Mail size={17}/> : <FileText size={17}/>}</span><span className={`risk-level risk-${a.risk_level.toLowerCase()}`}><i/>{a.risk_level} RISK</span></div><h3>{a.title}</h3><div className="approval-explain"><div><span>WHAT WILL HAPPEN</span><p>{isEmail ? `Send a message to ${payload.to || "the customer"}.` : `Create an official invoice for ${money(payload.amount)}.`}</p></div><div><span>WHY IT’S RECOMMENDED</span><p>{r.explanation.split("\n\nRisk:")[0]}</p></div>{isEmail && payload.body && <div className="approval-draft"><span>PREPARED MESSAGE</span><p>{payload.body}</p></div>}{!isEmail && <div><span>INVOICE DETAILS</span><p>{money(payload.amount)} · {payload.description} · Due in 30 days</p></div>}<div className="expected-outcome"><Check size={13}/><span>After approval, the action is completed and added to the activity log.</span></div></div><div className="approval-actions"><button className="button button-primary" disabled={busy === r.id} onClick={() => onDecide(r.id, "approve")}>{busy === r.id ? <LoaderCircle className="spin" size={14}/> : <Check size={14}/>} Approve &amp; {isEmail ? "send" : "create"}</button><button className="button button-quiet" disabled={busy === r.id} onClick={() => onEdit(r)}>Edit</button><button className="reject-button" disabled={busy === r.id} onClick={() => onDecide(r.id, "reject")}>Reject</button></div></article>; })}</div></> : <div className="panel approval-empty"><div className="empty-shield"><Check size={24}/></div><h2>All clear. You’re in control.</h2><p>No actions are waiting for approval. When SMB OS prepares an email or business record, you’ll review the details here first.</p></div>}{history.length > 0 && <><SectionTitle title="Recently decided"/><div className="panel decided-list">{history.slice(0, 8).map((r: Row) => <div key={r.id}><span className={r.status === "approved" ? "decision-approved" : "decision-rejected"}>{r.status === "approved" ? <Check size={13}/> : <X size={13}/>}</span><span><b>{r.action.title}</b><small>{r.action.risk_level} risk · {r.status}</small></span><span className="muted">{r.decided_at ? timeAgo(r.decided_at) : "Recently"}</span></div>)}</div></>}</>;
}

function InsightsPage({ data, onCommand, onNavigate }: any) {
  const risk = data.customers.filter((c: Row) => c.risk_score >= 65); const overdue = data.invoices.filter((i: Row) => i.status === "overdue"); const total = overdue.reduce((sum: number, i: Row) => sum + i.amount, 0);
  const metrics = data.dashboard?.metrics || {};
  const chartData = Array.from({ length: 7 }, (_, k) => { const d = new Date(); d.setDate(d.getDate() - (6 - k)); const key = d.toDateString(); const rows = data.emails.filter((e: Row) => new Date(e.received_at).toDateString() === key); return { day: d.toLocaleDateString("en", { weekday: "short" }), inbound: rows.length, resolved: rows.filter((e: Row) => e.status === "resolved").length }; });
  return <>
    <PageHeading eyebrow="FROM SIGNALS TO DECISIONS" title="Business insights" description="A healthier business starts with knowing where to look." action={<button className="button button-primary" onClick={() => onCommand("Give me my weekly business report")}><Sparkles size={15}/> Generate weekly report</button>}/>
    <div className="insight-hero"><div className="insight-hero-orb"><Sparkles size={20}/></div><div><span className="eyebrow">MORNING BUSINESS BRIEF</span><h2>Good morning. Here’s the shape of your day.</h2><p>Acme Corp is the account to start with. Open support issues, a negative billing conversation, and an overdue balance mean a check-in before tomorrow’s meeting could make a difference.</p><button onClick={() => onCommand("Which customer should I contact right now?")}>Explore this recommendation <ArrowRight size={14}/></button></div><div className="brief-date">{new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "Asia/Kolkata" })}<small>TODAY’S BRIEF</small></div></div>
    <div className="insight-metrics">
      <div className="insight-stat"><span className="insight-stat-icon rose"><MessageSquare size={16}/></span><b>{data.emails.filter((e: Row) => e.status === "open").length}</b><small>open conversations</small><span className="insight-stat-foot">{data.emails.filter((e: Row) => e.status === "open" && e.priority === "high").length} urgent</span></div>
      <div className="insight-stat"><span className="insight-stat-icon amber"><CircleDollarSign size={16}/></span><b>{shortMoney(total)}</b><small>overdue invoices</small><span className="insight-stat-foot">{overdue.length} invoices need a nudge</span></div>
      <div className="insight-stat"><span className="insight-stat-icon violet"><Users size={16}/></span><b>{risk.length}</b><small>customers at risk</small><span className="insight-stat-foot">Across {data.customers.length} relationships</span></div>
      <div className="insight-stat"><span className="insight-stat-icon blue"><ListTodo size={16}/></span><b>{data.tasks.filter((t: Row) => t.status === "open").length}</b><small>open follow-ups</small><span className="insight-stat-foot">Tasks across your team</span></div>
    </div>
    <div className="overview-columns">
      <section className="panel"><SectionTitle title="Customers to watch" action="View customers" onClick={() => onNavigate("Customers")}/><div className="watch-list">{risk.map((c: Row, i: number) => <div key={c.id}><Avatar name={c.company} index={i}/><span><b>{c.company}</b><small>{c.risk_reason}</small></span><RiskBadge score={c.risk_score}/></div>)}</div></section>
      <section className="panel"><SectionTitle title="Upcoming meetings"/><div className="meeting-list">{data.calendar.slice(0, 4).map((event: Row) => <div key={event.id}><span className="meeting-date"><b>{new Date(event.starts_at).getDate()}</b><small>{new Date(event.starts_at).toLocaleDateString("en-US", { month: "short" })}</small></span><span><b>{event.customer || event.title}</b><small>{event.title} · {new Date(event.starts_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</small></span><button onClick={() => onCommand(`Prepare me for my meeting with ${event.customer}`)}><Sparkles size={14}/> Brief me</button></div>)}</div></section>
    </div>
    <section className="panel trend-card"><div className="trend-head"><span><b>Customer support activity</b><small>Resolved conversations · this week</small></span><span className="chart-legend"><i/> Resolved <i className="legend-pale"/> Inbound</span></div><ResponsiveContainer width="100%" height={155}><AreaChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}><defs><linearGradient id="resolvedFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6175d3" stopOpacity={0.2}/><stop offset="100%" stopColor="#6175d3" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#edf0f4" strokeDasharray="3 4"/><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#8994a1", fontSize: 9 }}/><YAxis axisLine={false} tickLine={false} tick={{ fill: "#9aa3ad", fontSize: 8 }}/><Tooltip contentStyle={{ border: "1px solid #e6eaf0", borderRadius: 7, fontSize: 10 }}/><Area type="monotone" dataKey="inbound" stroke="#aab4dc" fill="none" strokeWidth={1.5} strokeDasharray="4 4"/><Area type="monotone" dataKey="resolved" stroke="#536bc9" fill="url(#resolvedFill)" strokeWidth={2} activeDot={{ r: 4 }}/></AreaChart></ResponsiveContainer></section>
    <div className="impact-report"><div><span className="impact-report-icon"><Zap size={17}/></span><div><b>AI impact this month</b><small>More focus time. Fewer dropped balls.</small></div></div><div className="impact-report-stat"><b>{metrics.time_saved_hours ?? 0} hrs</b><small title={metrics.estimate_note}>time saved (est.)</small></div><div className="impact-report-stat"><b>{metrics.tasks_automated ?? 0}</b><small>tasks automated</small></div><div className="impact-report-stat"><b>{data.approvals.filter((a: Row) => a.status === "approved").length}/{data.approvals.length}</b><small>approved by you</small></div><button className="button button-quiet" onClick={() => onCommand("Give me my weekly business report")}>Full weekly report <ArrowRight size={14}/></button></div>
  </>;
}

function ActivityPage({ rows }: any) { return <><PageHeading eyebrow="A CLEAR RECORD OF EVERY STEP" title="Activity" description="Every preparation, decision, and completed action is recorded here."/><div className="activity-stats"><div><b>{rows.length}</b><small>recent events</small></div><div><b>SMB Operations Agent</b><small>active assistant</small></div><div><span className="live-dot"/><b>Audit trail on</b><small>persistent record</small></div></div><div className="panel activity-timeline">{rows.map((r: Row, i: number) => <div className="timeline-row" key={r.id}><span className={`timeline-icon ti-${i % 5}`}>{r.event_type.includes("invoice") ? <FileText size={15}/> : r.event_type.includes("email") ? <Mail size={15}/> : r.event_type.includes("customer") ? <Users size={15}/> : r.event_type.includes("task") ? <ListTodo size={15}/> : <Sparkles size={15}/>}</span><div className="timeline-copy"><b>{r.message}</b><small>{r.event_type.replaceAll(".", " · ")} {r.details?.actor ? `· ${r.details.actor}` : "· SMB Operations Agent"}</small></div><time>{timeAgo(r.created_at)}</time></div>)}</div></>; }

function SettingsPage() {
  const [health, setHealth] = useState<Row>({}); useEffect(() => { apiFetch(`${API}/health`).then((r) => r.json()).then(setHealth).catch(() => {}); }, []); return <><PageHeading eyebrow="YOUR WORKSPACE" title="Settings" description="Your SMB OS workspace is set up for a safe, local demo."/><div className="settings-grid"><div className="panel settings-card"><div className="settings-card-icon"><Users size={17}/></div><h3>Business profile</h3><p>Northstar Studio · India (INR). The seeded workspace is ready for the demo.</p><span className="provider-badge"><i/> Demo workspace</span></div><div className="panel settings-card"><div className="settings-card-icon"><ShieldCheck size={17}/></div><h3>Action approval policy</h3><p>Reads and analysis happen automatically. Customer emails, meetings, and official records wait for your approval.</p><span className="provider-badge"><i/> Human approval enabled</span></div><div className="panel settings-card"><div className="settings-card-icon"><Sparkles size={17}/></div><h3>AI provider</h3><p>{health.ai === "live" ? "The live tool-calling agent is active. The offline planner remains available if the AI provider is unavailable." : "The deterministic offline planner is active. Add a backend API key to enable the live tool-calling agent."}</p><span className="provider-badge"><i/> {health.ai === "live" ? "Live agent" : "Offline planner"}</span></div><div className="panel settings-card"><div className="settings-card-icon"><Activity size={17}/></div><h3>Connected systems</h3><p>Demo data is local. Approved emails go through {health.email === "smtp" ? "real SMTP delivery" : "a mock provider (set SMTP_HOST for real delivery)"}. Proactive brief: {health.proactive_brief_minutes ? `every ${health.proactive_brief_minutes} min` : "off"}.</p><span className="provider-badge"><i/> {health.email === "smtp" ? "SMTP connected" : "Mock email"}</span></div></div></>; }

function Empty({ message }: { message: string }) { return <div className="empty-state"><span><Check size={18}/></span><p>{message}</p></div>; }
