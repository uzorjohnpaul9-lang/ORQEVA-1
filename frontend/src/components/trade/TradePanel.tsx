import Link from "next/link";
import { clsx } from "clsx";
import type { Trade } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface TradePanelProps {
  trade: Trade & { current_price?: number | null; unrealized_pnl?: number | null };
  onClose?: () => void;
  closing?: boolean;
}

export function TradePanel({ trade, onClose, closing }: TradePanelProps) {
  const isOpen = trade.status === "open";

  return (
    <Card className="hover:border-border-light transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">{trade.symbol}</h3>
            <Badge variant={trade.side === "buy" ? "green" : "red"}>{trade.side.toUpperCase()}</Badge>
            {trade.is_demo && <Badge variant="purple">DEMO</Badge>}
          </div>
          <p className="text-xs text-text-muted mt-1">{trade.strategy} · {trade.market}</p>
        </div>
        <Badge variant={isOpen ? "yellow" : "gray"} dot={isOpen}>{isOpen ? "OPEN" : "CLOSED"}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-text-muted">Entry</p>
          <p className="font-mono font-medium">{trade.entry_price.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-text-muted">Quantity</p>
          <p className="font-mono font-medium">{trade.quantity}</p>
        </div>
        {isOpen && trade.current_price != null && (
          <div>
            <p className="text-xs text-text-muted">Live Price</p>
            <p className="font-mono font-medium">{trade.current_price.toLocaleString()}</p>
          </div>
        )}
        {isOpen && trade.unrealized_pnl != null && (
          <div>
            <p className="text-xs text-text-muted">Unrealized P&L</p>
            <p className={clsx("font-mono font-bold", trade.unrealized_pnl >= 0 ? "text-green" : "text-red")}>
              {trade.unrealized_pnl >= 0 ? "+" : ""}{trade.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </div>
        )}
        {trade.exit_price && (
          <div>
            <p className="text-xs text-text-muted">Exit</p>
            <p className="font-mono font-medium">{trade.exit_price.toLocaleString()}</p>
          </div>
        )}
        {trade.pnl !== null && (
          <div>
            <p className="text-xs text-text-muted">P&L</p>
            <p className={clsx("font-mono font-bold", trade.pnl >= 0 ? "text-green" : "text-red")}>
              {trade.pnl >= 0 ? "+" : ""}{trade.pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </div>
        )}
      </div>

      <div className={clsx("mt-4 grid gap-2", onClose ? "grid-cols-2" : "grid-cols-1")}>
        <Link
          href={`/market/charts?symbol=${encodeURIComponent(trade.symbol)}&market=${trade.market}&entry=${trade.entry_price}&side=${trade.side}`}
          className="inline-flex w-full items-center justify-center rounded-lg border border-border bg-bg-tertiary px-4 py-2 text-sm font-medium text-text-primary hover:bg-hover transition-colors"
        >
          View chart
        </Link>
        {onClose && (
          <Button variant="danger" size="sm" onClick={onClose} disabled={closing}>
            {closing ? "Closing..." : "Close position"}
          </Button>
        )}
      </div>
    </Card>
  );
}
