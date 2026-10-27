import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Trade History",
  description:
    "Full history of executed trades with entry, exit and profit metrics.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
