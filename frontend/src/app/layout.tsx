import type { Metadata } from "next";

import { AuthProvider } from "@/components/AuthProvider";
import { Header } from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Helpdesk",
  description: "Open a support ticket and follow it until it's resolved.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <Header />
          <main className="page">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
