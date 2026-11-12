"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { RequireLogin } from "@/components/RequireLogin";
import { TicketRow } from "@/components/TicketRow";
import { ApiError, api } from "@/lib/api";
import { PRIORITY_LABELS, STATUS_LABELS } from "@/lib/format";
import type { TicketList, TicketPriority, TicketStatus, User, UserSummary } from "@/lib/types";

const PAGE_SIZE = 20;

export default function TicketsPage() {
  return <RequireLogin>{(user) => <Tickets user={user} />}</RequireLogin>;
}

function Tickets({ user }: { user: User }) {
  const isStaff = user.role === "staff";
  const [status, setStatus] = useState("");
  const [assignee, setAssignee] = useState("");
  const [priority, setPriority] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<TicketList | null>(null);
  const [staff, setStaff] = useState<UserSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load the staff list once, for the "Assigned to" filter.
  useEffect(() => {
    if (isStaff) api.listStaff().then((r) => setStaff(r.items)).catch(() => setStaff([]));
  }, [isStaff]);

  // Reload whenever a filter or the page changes. The server decides which
  // tickets this user may see; we just show what comes back.
  useEffect(() => {
    setError(null);
    api
      .listTickets({ status, assignee, priority, overdue: overdueOnly, limit: PAGE_SIZE, offset })
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load tickets."));
  }, [status, assignee, priority, overdueOnly, offset]);

  function changeFilter(update: () => void) {
    update();
    setOffset(0);
  }

  return (
    <section>
      <div className="page-head">
        <h1>{isStaff ? "All tickets" : "Your tickets"}</h1>
        {!isStaff && (
          <Link href="/tickets/new" className="button">
            Open a ticket
          </Link>
        )}
      </div>

      <div className="filters">
        <label>
          Status
          <select value={status} onChange={(e) => changeFilter(() => setStatus(e.target.value))}>
            <option value="">Any status</option>
            {(Object.keys(STATUS_LABELS) as TicketStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        {isStaff && (
          <label>
            Assigned to
            <select value={assignee} onChange={(e) => changeFilter(() => setAssignee(e.target.value))}>
              <option value="">Anyone</option>
              <option value="me">Me</option>
              <option value="none">Nobody yet</option>
              {staff
                .filter((s) => s.id !== user.id)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
        )}
        {isStaff && (
          <label>
            Priority
            <select value={priority} onChange={(e) => changeFilter(() => setPriority(e.target.value))}>
              <option value="">Any priority</option>
              {(Object.keys(PRIORITY_LABELS) as TicketPriority[]).map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABELS[p]}
                </option>
              ))}
            </select>
          </label>
        )}
        {isStaff && (
          <label className="check">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => changeFilter(() => setOverdueOnly(e.target.checked))}
            />
            Overdue only
          </label>
        )}
      </div>

      <FormError message={error} />
      {!data && !error && <p className="muted">Loading tickets…</p>}
      {data && data.items.length === 0 && <EmptyState isStaff={isStaff} filtered={Boolean(status || assignee || priority || overdueOnly)} />}
      {data && data.items.length > 0 && (
        <>
          <ul className="ticket-list">
            {data.items.map((t) => (
              <TicketRow key={t.id} ticket={t} showCustomer={isStaff} />
            ))}
          </ul>
          <Pager total={data.total} offset={offset} onChange={setOffset} />
        </>
      )}
    </section>
  );
}

function EmptyState({ isStaff, filtered }: { isStaff: boolean; filtered: boolean }) {
  if (filtered) return <p className="empty">No tickets match these filters. Try a different status or assignee.</p>;
  if (isStaff) return <p className="empty">The queue is empty. New tickets from customers will appear here.</p>;
  return (
    <p className="empty">
      You haven&apos;t opened any tickets. <Link href="/tickets/new">Open a ticket</Link> and we&apos;ll reply here.
    </p>
  );
}

function Pager({ total, offset, onChange }: { total: number; offset: number; onChange: (o: number) => void }) {
  if (total <= PAGE_SIZE) return null;
  const last = Math.min(offset + PAGE_SIZE, total);
  return (
    <div className="pager">
      <button type="button" className="button secondary" disabled={offset === 0} onClick={() => onChange(offset - PAGE_SIZE)}>
        Newer
      </button>
      <span className="muted">
        {offset + 1}–{last} of {total}
      </span>
      <button type="button" className="button secondary" disabled={last >= total} onClick={() => onChange(offset + PAGE_SIZE)}>
        Older
      </button>
    </div>
  );
}
