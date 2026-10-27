import type { Metadata } from "next";
import type { ReactNode } from "react";
import { WorkspaceTabs } from "@/components/layout/WorkspaceTabs";

export const metadata: Metadata = {
  title: "Trade",
  description:
    "Place and manage trades with live broker routing, smart order execution and built-in risk controls.",
};

const TABS = [
  { href: "/trading", label: "Order Ticket" },
  { href: "/trading/automation", label: "Automation" },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <WorkspaceTabs tabs={TABS} label="Trade sections" />
      {children}
    </div>
  );
}
