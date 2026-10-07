import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Notifications",
  description:
    "View trading alerts, signal updates and system notifications in one place.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
