"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clsx } from "clsx";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import type { Position } from "@/lib/types";

export interface Notif {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

const typeColors: Record<string, "green" | "red" | "blue" | "yellow" | "purple" | "gray"> = {
  signal: "green", tp: "green", sl: "red", risk: "yellow",
  system: "gray", trade: "blue", trade_warning: "yellow", auto_trade: "blue",
};

const TRADE_TYPES = new Set(["trade", "auto_trade", "trade_warning"]);

interface NotificationSheetProps {
  notif: Notif | null;
  onClose: () => void;
  token: string | null;
}

export function NotificationSheet({ notif, onClose, token }: NotificationSheetProps) {
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  const isTrade = notif != null && TRADE_TYPES.has(notif.type);

  useEffect(() => {
    if (!isTrade || !token) { setPositions([]); return; }
    let active = true;
    api<Position[]>("/api/portfolio/positions", { token })
      .then((data) => { if (active) setPositions(data); })
      .catch(() => { if (active) setPositions([]); });
    return () => { active = false; };
  }, [isTrade, token, notif?.id]);

  if (!notif) return null;

  // Extract a symbol like EUR/USD, BTC, AAPL from title or message.
  const match = (notif.title + " " + notif.message).match(/\b[A-Z]{1,5}(?:[\/\-][A-Z]{1,5})?\b/g) || [];
  const symbol = match.find((m) => m !== "USD" && m !== "USDT") || null;

  const related = symbol
    ? positions.filter((p) => p.symbol.toUpperCase().includes(symbol.toUpperCase()))
    : [];

  function manage(e: React.MouseEvent) {
    e.preventDefault();
    onClose();
    router.push("/trading");
  }

  return (
    <Modal open onClose={onClose} title="Notification" align="bottom">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <Badge variant={typeColors[notif.type] || "gray"}>{notif.type}</Badge>
          <span className="text-xs text-text-muted">{new Date(notif.created_at).toLocaleString()}</span>
        </div>

        <div>
          <p className="font-semibold">{notif.title}</p>
          <p className="text-sm text-text-secondary mt-1 whitespace-pre-wrap break-words">{notif.message}</p>
        </div>

        {isTrade && (
          <div>
            <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
              Related position {symbol ? `· ${symbol}` : ""}
            </p>
            {related.length === 0 ? (
              <div className="bg-bg-tertiary rounded-lg p-3 text-sm text-text-muted">
                No open position{symbol ? ` for ${symbol}` : ""}. It may already be closed.
                <Link href="/history" onClick={onClose} className="block mt-2 text-blue hover:underline">
                  View History →
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {related.map((p) => (
                  <div key={p.id} className="flex items-center justify-between gap-3 bg-bg-tertiary rounded-lg p-3 text-sm">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{p.symbol}</span>
                        <Badge variant={p.side === "buy" ? "green" : "red"}>{p.side.toUpperCase()}</Badge>
                      </div>
                      <p className="text-xs text-text-muted mt-0.5">Entry {p.entry_price.toLocaleString()} · {p.quantity}</p>
                    </div>
                    {p.unrealized_pnl != null && (
                      <span className={clsx("font-mono font-bold shrink-0", p.unrealized_pnl >= 0 ? "text-green" : "text-red")}>
                        {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    )}
                  </div>
                ))}
                <Button className="w-full" onClick={manage}>Manage in Trading</Button>
              </div>
            )}
          </div>
        )}

        {!isTrade && notif.type === "billing" && (
          <Button className="w-full" variant="secondary" onClick={() => { onClose(); router.push("/billing"); }}>
            Go to Billing
          </Button>
        )}
        {!isTrade && notif.type === "signal" && (
          <Button className="w-full" variant="secondary" onClick={() => { onClose(); router.push("/signals"); }}>
            View Signals
          </Button>
        )}
        {!isTrade && notif.type === "risk" && (
          <Button className="w-full" variant="secondary" onClick={() => { onClose(); router.push("/risk"); }}>
            Go to Risk Management
          </Button>
        )}
      </div>
    </Modal>
  );
}