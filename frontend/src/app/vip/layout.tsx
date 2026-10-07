import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "VIP Membership",
  description:
    "Unlock VIP signals, priority analysis and premium features with ORQEVA VIP.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
