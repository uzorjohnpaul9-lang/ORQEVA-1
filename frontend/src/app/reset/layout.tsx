import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Reset Password",
  description: "Choose a new password for your ORQEVA account.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
