"use client";

import { CalendarDays, Check, FileText, LoaderCircle, Mail, ShieldCheck, Sparkles, X } from "lucide-react";
type Row = Record<string, any>;

const money = (amount: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount || 0);
const ago = (value?: string) => value ? `${Math.max(1, Math.floor((Date.now() - new Date(/Z|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z").getTime()) / 3600000))}h ago` : "Recently";

export default function ApprovalCenter({ rows, busy, onDecide, onEdit }: any) {
  const pending = rows.filter((r: Row) => r.status === "pending");
  const history = rows.filter((r: Row) => r.status !== "pending");
  return <>
    <div className="page-heading"><div><div className="eyebrow">HUMAN OVERSIGHT</div><h1>Approval center</h1><p>The AI handles the prep. You decide what goes out into the world.</p></div><div className="approval-safe"><ShieldCheck size={16}/><span>Nothing sends without you</span></div></div>
    {pending.length > 0 ? <>
      <div className="approval-count-bar"><span className="approval-count-icon"><ShieldCheck size={17}/></span><div><b>{pending.length} {pending.length === 1 ? "action is" : "actions are"} ready for your review</b><small>Each recommendation explains what happens and why.</small></div><span className="awaiting">NEEDS YOUR REVIEW</span></div>
      <div className="approval-grid">{pending.map((row: Row) => {
        const action = row.action; const payload = action.payload || {};
        const isEmail = action.type === "SEND_EMAIL"; const isMeeting = action.type === "SCHEDULE_MEETING";
        const Icon = isEmail ? Mail : isMeeting ? CalendarDays : FileText;
        const kind = isEmail ? "email" : isMeeting ? "meeting" : "invoice";
        return <article className="approval-card" key={row.id}>
          <div className="approval-card-top"><span className={`approval-action-icon ${kind}`}><Icon size={17}/></span><span className={`risk-level risk-${action.risk_level.toLowerCase()}`}><i/>{action.risk_level} RISK</span></div>
          <h3>{action.title}</h3>
          <div className="approval-explain">
            <div><span>WHAT WILL HAPPEN</span><p>{isEmail ? `Send a message to ${payload.to || "the customer"}.` : isMeeting ? `Send a calendar invitation to ${payload.customer || "the customer"} for ${new Date(payload.starts_at).toLocaleString()}.` : `Create an official invoice for ${money(payload.amount)}.`}</p></div>
            <div><span>WHY IT’S RECOMMENDED</span><p>{row.explanation.replace("\n\nRisk:", " Risk:")}</p></div>
            {isEmail && payload.body && <div className="approval-draft"><span>PREPARED MESSAGE</span><p>{payload.body}</p></div>}
            {isMeeting && <div><span>MEETING DETAILS</span><p>{payload.duration_minutes || 30} minutes · {payload.location || "Video call"} · {payload.notes}</p></div>}
            {!isEmail && !isMeeting && <div><span>INVOICE DETAILS</span><p>{money(payload.amount)} · {payload.description} · Due in 30 days</p></div>}
            <div className="expected-outcome"><Check size={13}/><span>After approval, the action is completed and added to the activity log.</span></div>
          </div>
          <div className="approval-actions"><button className="button button-primary" disabled={busy === row.id} onClick={() => onDecide(row.id, "approve")}>{busy === row.id ? <LoaderCircle className="spin" size={14}/> : <Check size={14}/>} Approve &amp; {isEmail ? "send" : isMeeting ? "schedule" : "create"}</button><button className="button button-quiet" disabled={busy === row.id} onClick={() => onEdit(row)}>Edit</button><button className="reject-button" disabled={busy === row.id} onClick={() => onDecide(row.id, "reject")}>Reject</button></div>
        </article>;
      })}</div>
    </> : <div className="panel approval-empty"><div className="empty-shield"><Check size={24}/></div><h2>All clear. You’re in control.</h2><p>No actions are waiting for approval. When SMB OS prepares an email or business record, you’ll review the details here first.</p></div>}
    {history.length > 0 && <><div className="section-title"><h2>Recently decided</h2></div><div className="panel decided-list">{history.slice(0, 8).map((row: Row) => <div key={row.id}><span className={row.status === "approved" ? "decision-approved" : "decision-rejected"}>{row.status === "approved" ? <Check size={13}/> : <X size={13}/>}</span><span><b>{row.action.title}</b><small>{row.action.risk_level} risk · {row.status}</small></span><span className="muted">{ago(row.decided_at)}</span></div>)}</div></>}
  </>;
}
