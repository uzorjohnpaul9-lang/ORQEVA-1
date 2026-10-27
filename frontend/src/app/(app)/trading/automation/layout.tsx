import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Automation",
  description:
    "Configure AI auto-trading with risk profiles, position sizing and execution rules.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
