import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Support",
  description: "Open a ticket or view replies from the ORQEVA support team.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}