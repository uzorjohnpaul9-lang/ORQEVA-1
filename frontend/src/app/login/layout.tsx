import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Sign In",
  description:
    "Sign in to your ORQEVA account to access AI trading signals and your dashboard.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
