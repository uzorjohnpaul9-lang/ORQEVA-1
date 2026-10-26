import type { Metadata } from "next";
import "./globals.css";

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
    images: [
      {
        url: "/og-orqeva.jpg",
        width: 1200,
        height: 630,
        type: "image/jpeg",
        alt: "ORQEVA social preview with a sample EUR/USD signal brief, risk context and guardrails.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ORQEVA — Multi-Market Trading Intelligence",
    description: "Structured signals, explicit risk context and paper-first execution across forex, equities, commodities and crypto.",
    images: ["/og-orqeva.jpg"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-bg-primary text-text-primary antialiased">
        {children}
      </body>
    </html>
  );
}
