import Link from "next/link";

import { formatDate } from "@/lib/format";
import type { Ticket } from "@/lib/types";
import { StatusStamp } from "./StatusStamp";

export function TicketRow({ ticket, showCustomer }: { ticket: Ticket; showCustomer: boolean }) {
  return (
    <li className="ticket-row">
      <Link href={`/tickets/${ticket.id}`} className="ticket-link">
        <span className="ticket-main">
          <span className="ticket-title">{ticket.title}</span>
          <span className="ticket-meta">
            {showCustomer && <>From {ticket.customer.name}. </>}
            Updated {formatDate(ticket.updated_at)}.{" "}
            {ticket.assignee ? `Assigned to ${ticket.assignee.name}.` : "Not assigned yet."}
          </span>
        </span>
        <StatusStamp status={ticket.status} />
      </Link>
    </li>
  );
}
