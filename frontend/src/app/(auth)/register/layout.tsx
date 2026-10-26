import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Create Account",
  description:
    "Create a free ORQEVA account and start receiving AI-powered trading signals.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
