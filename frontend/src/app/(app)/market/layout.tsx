import type { Metadata } from "next";
import type { ReactNode } from "react";
import { WorkspaceTabs } from "@/components/layout/WorkspaceTabs";

export const metadata: Metadata = {
  title: "Markets",
  description:
    "Live prices, movers, charts and AI market analysis across forex, cryptocurrencies and stock indices.",
};

const TABS = [
  { href: "/market", label: "Overview" },
  { href: "/market/charts", label: "Charts" },
  { href: "/market/calendar", label: "Calendar" },
  { href: "/market/analysis", label: "Analysis" },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <WorkspaceTabs tabs={TABS} label="Markets sections" />
      {children}
    </div>
  );
}
