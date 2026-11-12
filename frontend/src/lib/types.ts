// Shapes returned by the backend. These mirror docs/openapi.yaml.

export type Role = "customer" | "staff";
export type TicketStatus = "open" | "in_progress" | "resolved";
export type TicketPriority = "low" | "normal" | "high" | "urgent";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface UserSummary {
  id: string;
  name: string;
}

export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  customer: UserSummary;
  assignee: UserSummary | null;
  created_at: string;
  updated_at: string;
  first_response_at: string | null;
  due_at: string;
  overdue: boolean;
}

export interface TicketList {
  items: Ticket[];
  total: number;
  limit: number;
  offset: number;
}

export interface Comment {
  id: string;
  ticket_id: string;
  author: UserSummary & { role: Role };
  body: string;
  internal: boolean;
  created_at: string;
}

export interface FieldError {
  field: string;
  message: string;
}
