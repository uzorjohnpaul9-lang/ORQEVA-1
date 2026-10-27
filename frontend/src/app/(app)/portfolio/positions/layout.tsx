import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Positions",
  description: "Open positions with live prices, unrealized P/L and execution status.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
