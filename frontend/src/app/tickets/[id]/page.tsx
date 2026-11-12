"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { RequireLogin } from "@/components/RequireLogin";
import { StatusStamp } from "@/components/StatusStamp";
import { ApiError, api } from "@/lib/api";
import { STATUS_LABELS, formatDate } from "@/lib/format";
import type { Comment, Ticket, TicketStatus, User, UserSummary } from "@/lib/types";

export default function TicketPage() {
  const { id } = useParams<{ id: string }>();
  return <RequireLogin>{(user) => <TicketDetail id={id} user={user} />}</RequireLogin>;
}

function TicketDetail({ id, user }: { id: string; user: User }) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, c] = await Promise.all([api.getTicket(id), api.listComments(id)]);
      setTicket(t);
      setComments(c.items);
    } catch (err) {
      // 404 covers both "doesn't exist" and "not yours": the server doesn't say which.
      if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
        setLoadError("We couldn't find that ticket.");
      } else {
        setLoadError(err instanceof ApiError ? err.message : "Couldn't load this ticket.");
      }
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const backLink = (
    <p className="back">
      <Link href="/tickets">{user.role === "staff" ? "All tickets" : "Your tickets"}</Link>
    </p>
  );

  if (loadError)
    return (
      <section>
        {backLink}
        <p className="empty">{loadError}</p>
      </section>
    );
  if (!ticket) return <p className="muted">Loading ticket…</p>;

  return (
    <section>
      {backLink}
      <div className="ticket-head">
        <h1>{ticket.title}</h1>
        <StatusStamp status={ticket.status} />
      </div>
      <p className="ticket-meta">
        Opened by {ticket.customer.name} on {formatDate(ticket.created_at)}.{" "}
        {ticket.assignee ? `Assigned to ${ticket.assignee.name}.` : "Not assigned yet."}
      </p>
      <div className="description">{ticket.description}</div>

      {user.role === "staff" && <StaffControls ticket={ticket} onSaved={setTicket} />}

      <h2>Conversation</h2>
      <Thread comments={comments} />
      <ReplyForm ticketId={ticket.id} onSent={load} />
    </section>
  );
}

function StaffControls({ ticket, onSaved }: { ticket: Ticket; onSaved: (t: Ticket) => void }) {
  const [staff, setStaff] = useState<UserSummary[]>([]);
  const [status, setStatus] = useState<TicketStatus>(ticket.status);
  const [assigneeId, setAssigneeId] = useState(ticket.assignee?.id ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listStaff().then((r) => setStaff(r.items)).catch(() => setStaff([]));
  }, []);

  const unchanged = status === ticket.status && assigneeId === (ticket.assignee?.id ?? "");

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updateTicket(ticket.id, { status, assignee_id: assigneeId || null });
      onSaved(updated);
      setMessage("Changes saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.details[0]?.message ?? err.message : "Couldn't save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="staff-panel">
      <label>
        Status
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as TicketStatus);
            setMessage(null);
          }}
        >
          {(Object.keys(STATUS_LABELS) as TicketStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Assigned to
        <select
          value={assigneeId}
          onChange={(e) => {
            setAssigneeId(e.target.value);
            setMessage(null);
          }}
        >
          <option value="">Nobody</option>
          {staff.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="button" onClick={save} disabled={busy || unchanged}>
        {busy ? "Saving…" : "Save changes"}
      </button>
      {message && (
        <p className="saved" role="status">
          {message}
        </p>
      )}
      <FormError message={error} />
    </div>
  );
}

function Thread({ comments }: { comments: Comment[] }) {
  if (comments.length === 0) return <p className="muted">No replies yet.</p>;
  return (
    <ol className="thread">
      {comments.map((c) => (
        <li key={c.id} className={c.author.role === "staff" ? "reply reply-staff" : "reply"}>
          <p className="reply-meta">
            <strong>{c.author.name}</strong>
            {c.author.role === "staff" && <span className="role-tag">Staff</span>}
            <span className="muted"> {formatDate(c.created_at)}</span>
          </p>
          <p className="reply-body">{c.body}</p>
        </li>
      ))}
    </ol>
  );
}

function ReplyForm({ ticketId, onSent }: { ticketId: string; onSent: () => Promise<void> }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addComment(ticketId, body);
      setBody("");
      await onSent();
    } catch (err) {
      setError(err instanceof ApiError ? err.details[0]?.message ?? err.message : "Couldn't send your reply.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="form reply-form" noValidate>
      <label>
        Your reply
        <textarea rows={4} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
      </label>
      <FormError message={error} />
      <button type="submit" className="button" disabled={busy || body.trim() === ""}>
        {busy ? "Sending…" : "Send reply"}
      </button>
    </form>
  );
}
