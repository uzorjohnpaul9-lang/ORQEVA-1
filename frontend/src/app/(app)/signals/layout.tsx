import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Live Trading Signals",
  description:
    "Real-time AI-generated trading signals for forex, crypto and stocks with entry, stop and take-profit levels.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
