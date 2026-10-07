import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Analytics",
  description:
    "Performance analytics: win rate, drawdown, streaks and strategy statistics over time.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
