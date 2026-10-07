import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Broker Connections",
  description:
    "Connect and manage broker and exchange API keys for live data and order routing.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
