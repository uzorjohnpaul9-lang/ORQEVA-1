import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  metadataBase: new URL("https://orqeva.pages.dev"),
  title: {
    default: "ORQEVA — AI Market Signals",
    template: "%s | ORQEVA",
  },
  description: "ORQEVA: AI trading signals for forex, crypto and stocks, with live broker routing and risk controls.",
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    siteName: "ORQEVA",
    title: "ORQEVA — AI Market Signals",
    description: "AI trading signals for forex, crypto and stocks, with live broker routing and risk controls.",
    url: "https://orqeva.pages.dev",
  },
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
