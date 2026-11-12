"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { FormError } from "@/components/FormError";
import { ApiError, api } from "@/lib/api";

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.register(email, name, password);
      await login(email, password);
      router.push("/tickets");
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", "Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  // Show the server's message next to the field it's about.
  const fieldMessage = (field: string) => error?.fieldMessage(field);
  const generalMessage = error && error.details.length === 0 ? error.message : null;

  return (
    <section className="narrow">
      <h1>Create an account</h1>
      <p className="lead">You&apos;ll be able to open tickets and follow replies from our team.</p>
      <form onSubmit={handleSubmit} className="form" noValidate>
        <label>
          Your name
          <input autoComplete="name" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
          <FormError message={fieldMessage("name")} />
        </label>
        <label>
          Email
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <FormError message={fieldMessage("email")} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="new-password"
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <span className="hint">At least 8 characters.</span>
          <FormError message={fieldMessage("password")} />
        </label>
        <FormError message={generalMessage} />
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </section>
  );
}
