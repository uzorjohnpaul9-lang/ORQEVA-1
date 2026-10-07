import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Trading Terminal",
  description:
    "Place and manage trades with live broker routing, smart order execution and built-in risk controls.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
