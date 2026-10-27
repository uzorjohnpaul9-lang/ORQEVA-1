import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Economic Calendar",
  description:
    "High-impact economic events and market-moving releases with affected-market context.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
