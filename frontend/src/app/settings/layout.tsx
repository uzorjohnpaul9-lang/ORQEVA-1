import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Settings",
  description:
    "Manage your account preferences, theme and notification settings.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
