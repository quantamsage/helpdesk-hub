"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormError } from "@/components/FormError";
import { RequireLogin } from "@/components/RequireLogin";
import { ApiError, api } from "@/lib/api";

export default function NewTicketPage() {
  return (
    <RequireLogin>
      {(user) =>
        user.role === "customer" ? (
          <NewTicketForm />
        ) : (
          <p className="empty">
            Staff can&apos;t open tickets. <Link href="/tickets">Back to all tickets</Link>
          </p>
        )
      }
    </RequireLogin>
  );
}

function NewTicketForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await api.createTicket(title, description);
      router.push(`/tickets/${ticket.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", "Something went wrong. Please try again."));
      setBusy(false);
    }
  }

  return (
    <section className="narrow">
      <p className="back">
        <Link href="/tickets">Your tickets</Link>
      </p>
      <h1>Open a ticket</h1>
      <p className="lead">Describe the problem. A member of our team will reply on the ticket.</p>
      <form onSubmit={handleSubmit} className="form" noValidate>
        <label>
          Summary
          <input maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Can't download my invoice" />
          <span className="hint">5 to 120 characters.</span>
          <FormError message={error?.fieldMessage("title")} />
        </label>
        <label>
          What&apos;s happening?
          <textarea
            rows={8}
            maxLength={5000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What were you trying to do, and what happened instead?"
          />
          <span className="hint">
            {description.length} / 5000 characters. At least 10.
          </span>
          <FormError message={error?.fieldMessage("description")} />
        </label>
        <FormError message={error && error.details.length === 0 ? error.message : null} />
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Opening ticket…" : "Open ticket"}
        </button>
      </form>
    </section>
  );
}
