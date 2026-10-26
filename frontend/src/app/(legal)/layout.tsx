import { DisclaimerFooter } from "@/components/layout/DisclaimerFooter";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh flex flex-col">
      <div className="flex-1">{children}</div>
      <DisclaimerFooter />
    </div>
  );
}
