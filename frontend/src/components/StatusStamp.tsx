import { STATUS_LABELS } from "@/lib/format";
import type { TicketStatus } from "@/lib/types";

export function StatusStamp({ status }: { status: TicketStatus }) {
  return <span className={`stamp stamp-${status}`}>{STATUS_LABELS[status]}</span>;
}
