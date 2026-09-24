import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "ORQEVA — AI Market Signals",
  description: "ORQEVA: AI trading signals for forex, crypto and stocks, with live broker routing and risk controls.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-bg-primary text-text-primary antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
