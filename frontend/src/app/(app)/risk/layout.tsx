import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Risk Management",
  description:
    "Set drawdown limits, trade caps and use the kill switch to protect your capital.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
