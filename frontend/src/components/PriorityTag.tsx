import { PRIORITY_LABELS, formatRelative } from "@/lib/format";
import type { Ticket, TicketPriority } from "@/lib/types";

export function PriorityTag({ priority }: { priority: TicketPriority }) {
  return <span className={`priority priority-${priority}`}>{PRIORITY_LABELS[priority]}</span>;
}

/** First-response deadline, for staff. Says nothing once staff have replied or the ticket is resolved. */
export function DueNote({ ticket }: { ticket: Ticket }) {
  if (ticket.first_response_at || ticket.status === "resolved") return null;
  if (ticket.overdue) return <span className="overdue">Reply overdue ({formatRelative(ticket.due_at)})</span>;
  return <span className="due">First reply due {formatRelative(ticket.due_at)}</span>;
}
