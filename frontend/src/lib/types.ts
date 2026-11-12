// Shapes returned by the backend. These mirror docs/openapi.yaml.

export type Role = "customer" | "staff";
export type TicketStatus = "open" | "in_progress" | "resolved";

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
  customer: UserSummary;
  assignee: UserSummary | null;
  created_at: string;
  updated_at: string;
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
  created_at: string;
}

export interface FieldError {
  field: string;
  message: string;
}
