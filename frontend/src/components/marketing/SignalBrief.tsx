import { Check, ShieldCheck } from "lucide-react";
import { SignalPulse } from "@/components/ui/SignalPulse";

const context = [
  "Higher-timeframe trend aligned",
  "Volatility compressed into the session open",
  "No high-impact event inside the horizon",
];

export function SignalBrief() {
  return (
    <div className="relative mx-auto w-full max-w-[540px]">
      <div
        className="pointer-events-none absolute -inset-10 -z-10 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(0,214,143,0.14), transparent 68%)",
        }}
      />

      <div className="overflow-hidden rounded-[22px] border border-white/[0.09] bg-[#0E1117]/95 shadow-[0_32px_100px_rgba(0,0,0,0.55)] backdrop-blur">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div className="flex items-center gap-3">
            <SignalPulse size={24} rings={2} />
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-muted">
                Signal brief
              </p>
              <p className="text-sm font-semibold text-text-primary">
                EUR/USD <span className="font-normal text-text-muted">/ 4h</span>
              </p>
            </div>
          </div>
          <span className="rounded-full border border-green/20 bg-green/[0.07] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-green">
            Illustrative
          </span>
        </div>

        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-muted">
                Direction
              </p>
              <div className="mt-2 flex items-center gap-2.5">
                <span className="inline-flex items-center gap-1.5 rounded-md bg-green-dim px-2.5 py-1 text-xs font-semibold text-green">
                  <span className="h-1.5 w-1.5 rounded-full bg-green" />
                  Long
                </span>
                <span className="font-mono text-xs text-text-muted">R:R 2.0</span>
              </div>
            </div>

            <div
              className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full"
              style={{
                background:
                  "conic-gradient(var(--color-green) 82%, rgba(255,255,255,0.07) 0)",
              }}
              aria-label="Illustrative confidence score: 82 out of 100"
            >
              <div className="flex h-11 w-11 flex-col items-center justify-center rounded-full bg-[#0E1117]">
                <span className="text-sm font-semibold leading-none text-text-primary">82</span>
                <span className="mt-0.5 text-[8px] uppercase tracking-[0.12em] text-text-muted">
                  conf.
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07]">
            <PriceCell label="Entry" value="1.0842" />
            <PriceCell label="Invalidation" value="1.0798" tone="red" />
            <PriceCell label="Target" value="1.0930" tone="green" />
          </div>

          <div className="mt-4 grid grid-cols-3 divide-x divide-white/[0.06] rounded-xl border border-white/[0.06] bg-white/[0.02] py-3">
            <Metric label="Risk" value="1.0%" />
            <Metric label="Horizon" value="4–12h" />
            <Metric label="Expiry" value="Session" />
          </div>

          <div className="mt-6">
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-muted">
              Why this setup
            </p>
            <ul className="mt-3 space-y-2.5">
              {context.map((item) => (
                <li key={item} className="flex gap-2.5 text-[13px] leading-5 text-text-secondary">
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-5 border-t border-white/[0.06] pt-4">
            <p className="text-[11px] leading-5 text-text-muted">
              Illustrative structure only. Confidence ranks setups; it does not
              predict outcomes or remove risk.
            </p>
          </div>
        </div>
      </div>

      <div className="relative z-10 mx-4 mt-3 rounded-xl border border-white/[0.07] bg-[#11151C]/95 p-4 shadow-xl backdrop-blur sm:mx-8">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-green-dim">
            <ShieldCheck className="h-3.5 w-3.5 text-green" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-text-primary">Risk engine</p>
              <span className="text-[9px] uppercase tracking-[0.14em] text-text-muted">
                Example guardrails
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-text-muted">
              <span>Exposure 18% / 100%</span>
              <span>Open trades 3 / 10</span>
              <span className="text-green">Daily loss guard armed</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PriceCell({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "red" | "green";
}) {
  const toneClass =
    tone === "red" ? "text-red" : tone === "green" ? "text-green" : "text-text-primary";

  return (
    <div className="bg-[#0E1117] px-3 py-3.5">
      <p className="text-[9px] uppercase tracking-[0.14em] text-text-muted">{label}</p>
      <p className={`mt-1.5 font-mono text-sm font-medium ${toneClass}`}>{value}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-3 text-center">
      <p className="text-[9px] uppercase tracking-[0.14em] text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-xs text-text-secondary">{value}</p>
    </div>
  );
}
