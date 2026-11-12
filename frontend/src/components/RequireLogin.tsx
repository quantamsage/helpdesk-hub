"use client";

// Wraps pages that need a logged-in user. This is only for a smooth UI:
// the backend checks every request itself, whatever the frontend shows.
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import type { User } from "@/lib/types";
import { useAuth } from "./AuthProvider";

export function RequireLogin({ children }: { children: (user: User) => React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <p className="muted">Loading…</p>;
  return <>{children(user)}</>;
}
