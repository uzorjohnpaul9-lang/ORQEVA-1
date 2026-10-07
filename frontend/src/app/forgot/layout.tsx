import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Forgot Password",
  description:
    "Reset your ORQEVA account password securely by email.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
