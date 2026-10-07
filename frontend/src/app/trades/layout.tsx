import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Trades",
  description: "Open and closed positions with live P/L and execution status.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
