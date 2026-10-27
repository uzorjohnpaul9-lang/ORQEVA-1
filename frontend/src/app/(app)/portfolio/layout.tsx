import type { Metadata } from "next";
import type { ReactNode } from "react";
import { WorkspaceTabs } from "@/components/layout/WorkspaceTabs";

export const metadata: Metadata = {
  title: "Portfolio",
  description:
    "Track positions, trade history, equity and performance across connected brokers and exchanges.",
};

const TABS = [
  { href: "/portfolio", label: "Performance" },
  { href: "/portfolio/positions", label: "Positions" },
  { href: "/portfolio/history", label: "History" },
  { href: "/portfolio/analytics", label: "Analytics" },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-6">
      <WorkspaceTabs tabs={TABS} label="Portfolio sections" />
      {children}
    </div>
  );
}
