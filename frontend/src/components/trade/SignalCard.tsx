import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { Signal } from "@/lib/types";

interface SignalCardProps {
  signal: Signal;
}

export function SignalCard({ signal }: SignalCardProps) {
  const marketColors: Record<string, "blue" | "green" | "purple"> = { stock: "blue", forex: "green", crypto: "purple" };
  const dirColor = signal.direction === "buy" ? "green" : "red";

  return (
    <Card className="hover:border-border-light transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-base">{signal.symbol}</h3>
            <Badge variant={marketColors[signal.market] || "gray"}>{signal.market}</Badge>
          </div>
          <p className="text-xs text-text-muted mt-1">{signal.strategy}</p>
        </div>
        <Badge variant={dirColor} dot>{signal.direction.toUpperCase()}</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-[10px] text-text-muted uppercase">Entry</p>
          <p className="text-sm font-mono font-medium mt-0.5">{signal.entry_price?.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-[10px] text-text-muted uppercase">Stop Loss</p>
          <p className="text-sm font-mono font-medium text-red mt-0.5">{signal.stop_loss?.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-[10px] text-text-muted uppercase">Take Profit</p>
          <p className="text-sm font-mono font-medium text-green mt-0.5">{signal.take_profit?.toLocaleString()}</p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Confidence</span>
          <div className="w-24 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${signal.confidence * 100}%`,
                backgroundColor: signal.confidence >= 0.8 ? "#00D68F" : signal.confidence >= 0.6 ? "#FFBE0B" : "#FF4757",
              }}
            />
          </div>
          <span className="text-xs font-mono">{(signal.confidence * 100).toFixed(0)}%</span>
        </div>
        <Badge variant={signal.tier_required === "free" ? "gray" : signal.tier_required === "premium" ? "yellow" : "purple"}>
          {signal.tier_required}
        </Badge>
      </div>
    </Card>
  );
}
