import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Market Overview",
  description:
    "Live prices, movers and AI market analysis across forex, cryptocurrencies and stock indices.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
