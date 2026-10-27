import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Charts",
  description:
    "Interactive charts with EMA overlays, entry, stop and target levels across markets.",
};

export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
