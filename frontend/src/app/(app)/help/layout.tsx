import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Help Center",
  description:
    "Guides, FAQs and troubleshooting for the ORQEVA trading platform.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
