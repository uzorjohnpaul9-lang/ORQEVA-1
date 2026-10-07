import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AI Analysis",
  description:
    "Deep AI analysis of market conditions, trends and trade opportunities across asset classes.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
