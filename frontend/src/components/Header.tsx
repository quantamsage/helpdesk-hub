"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "./AuthProvider";

export function Header() {
  const { user, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href={user ? "/tickets" : "/login"} className="brand">
          Helpdesk
        </Link>
        {user && (
          <nav className="header-nav">
            <span className="who">
              {user.name}
              {user.role === "staff" && <span className="role-tag">Staff</span>}
            </span>
            <button type="button" className="link-button" onClick={handleLogout}>
              Log out
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}
