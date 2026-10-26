import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  metadataBase: new URL("https://orqeva.pages.dev"),
  title: {
    default: "ORQEVA — Multi-Market Trading Intelligence",
    template: "%s | ORQEVA",
  },
  description: "Multi-market trading intelligence with structured signals, explicit risk context and paper-first execution across forex, equities, commodities and crypto.",
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    siteName: "ORQEVA",
    title: "ORQEVA — Multi-Market Trading Intelligence",
    description: "Structured signals, explicit risk context and paper-first execution across forex, equities, commodities and crypto.",
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
