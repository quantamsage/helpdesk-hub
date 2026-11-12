// Where the login token is kept: sessionStorage.
// It survives a page refresh but is cleared when the tab closes.
// The README explains why this was chosen over localStorage or cookies.

const KEY = "support_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(KEY);
}

export function saveToken(token: string): void {
  window.sessionStorage.setItem(KEY, token);
}

export function clearToken(): void {
  window.sessionStorage.removeItem(KEY);
}
