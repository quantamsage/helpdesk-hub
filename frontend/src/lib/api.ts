// The only place the frontend talks to the backend.
// Every request goes over HTTP(S) to the API; the frontend never sees the database.

import { clearToken, getToken } from "./session";
import type { Comment, FieldError, Ticket, TicketList, TicketStatus, User, UserSummary } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: FieldError[] = [],
  ) {
    super(message);
  }

  /** The server's message for one form field, if there is one. */
  fieldMessage(field: string): string | undefined {
    return this.details.find((d) => d.field === field)?.message;
  }
}

type Options = { method?: string; body?: unknown };

async function request<T>(path: string, { method = "GET", body }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Check your connection and try again.");
  }

  if (response.ok) return (await response.json()) as T;

  // Every backend error looks like {"error": {"code", "message", "details"?}}
  const data = await response.json().catch(() => null);
  const error = data?.error;
  if (response.status === 401 && token) {
    clearToken();
    window.location.assign("/login?expired=1"); // session expired: back to login
  }
  throw new ApiError(
    response.status,
    error?.code ?? "unknown_error",
    error?.message ?? "Something went wrong. Please try again.",
    error?.details ?? [],
  );
}

export const api = {
  register: (email: string, name: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: { email, name, password } }),

  login: (email: string, password: string) =>
    request<{ access_token: string; expires_in: number }>("/auth/login", { method: "POST", body: { email, password } }),

  me: () => request<User>("/auth/me"),

  listStaff: () => request<{ items: UserSummary[] }>("/staff"),

  listTickets: (filters: { status?: string; assignee?: string; limit: number; offset: number }) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.assignee) params.set("assignee", filters.assignee);
    params.set("limit", String(filters.limit));
    params.set("offset", String(filters.offset));
    return request<TicketList>(`/tickets?${params}`);
  },

  createTicket: (title: string, description: string) =>
    request<Ticket>("/tickets", { method: "POST", body: { title, description } }),

  getTicket: (id: string) => request<Ticket>(`/tickets/${encodeURIComponent(id)}`),

  updateTicket: (id: string, changes: { status?: TicketStatus; assignee_id?: string | null }) =>
    request<Ticket>(`/tickets/${encodeURIComponent(id)}`, { method: "PATCH", body: changes }),

  listComments: (id: string) => request<{ items: Comment[] }>(`/tickets/${encodeURIComponent(id)}/comments`),

  addComment: (id: string, body: string) =>
    request<Comment>(`/tickets/${encodeURIComponent(id)}/comments`, { method: "POST", body: { body } }),
};
