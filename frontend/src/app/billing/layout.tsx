import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Plans and Billing",
  description:
    "View subscription tiers, payment details and invoice status for ORQEVA.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
