"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/AuthProvider";

// The home page just sends you to the right place.
export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) router.replace(user ? "/tickets" : "/login");
  }, [loading, user, router]);

  return <p className="muted">Loading…</p>;
}
