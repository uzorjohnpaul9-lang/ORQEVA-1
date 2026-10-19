"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { BINANCE_REFERRAL_URL, REFERRAL_STEPS } from "@/lib/links";

interface Partner {
  id: string;
  name: string;
  url: string;
  category: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  broker: "Broker",
  prop_firm: "Prop Firm",
  partner: "Partner",
};

const CATEGORY_BADGE: Record<string, "green" | "blue" | "purple" | "gray"> = {
  broker: "green",
  prop_firm: "purple",
  partner: "blue",
};

export default function PartnersPage() {
  const { token } = useAuth();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const r = await api<{ partners: Partner[] }>("/api/affiliates", { token });
      setPartners(r.partners);
      setError(null);
    } catch {
      setError("Could not load partner links");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function openPartner(p: Partner) {
    if (token) {
      try {
        await api(`/api/affiliates/${p.id}/click`, { method: "POST", token });
      } catch {
        // click tracking is best-effort - never block the redirect
      }
    }
    window.open(p.url, "_blank", "noopener,noreferrer");
  }

  async function copyReferral() {
    try {
      await navigator.clipboard.writeText(BINANCE_REFERRAL_URL);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Partner Desks</h1>
        {partners.length > 0 && <Badge variant="gray">{partners.length}</Badge>}
      </div>
      <p className="text-sm text-text-secondary max-w-2xl">
        Sign up with our partner brokers and prop firms to fund your account and trade ORQEVA signals
        with real capital. Clicking a partner records a referral so we can keep improving the platform.
      </p>

      {error && (
        <Card>
          <p className="text-sm text-red">{error}</p>
        </Card>
      )}

      {loading ? (
        <p className="text-sm text-text-muted">Loading partners...</p>
      ) : partners.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {partners.map((p) => (
            <Card key={p.id}>
              <div className="flex items-center justify-between mb-2">
                <CardTitle>{p.name}</CardTitle>
                <Badge variant={CATEGORY_BADGE[p.category] ?? "gray"}>
                  {CATEGORY_LABELS[p.category] ?? p.category}
                </Badge>
              </div>
              <p className="text-xs text-text-muted break-all mb-4">{p.url}</p>
              <Button size="sm" onClick={() => openPartner(p)}>
                Open account →
              </Button>
            </Card>
          ))}
        </div>
      ) : null}

      {/* Refer & Earn on Binance */}
      <Card>
        <CardHeader><CardTitle>Refer & Earn on Binance</CardTitle></CardHeader>
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Create your Binance account through ORQEVA&apos;s referral link to support the platform.
          </p>
          <div className="flex items-center gap-2 bg-bg-tertiary rounded-lg p-3">
            <code className="text-xs text-green flex-1 break-all">{BINANCE_REFERRAL_URL}</code>
            <Button variant="secondary" size="sm" onClick={copyReferral}>
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <ol className="space-y-2">
            {REFERRAL_STEPS.map((step, i) => (
              <li key={i} className="flex gap-3 text-sm text-text-secondary">
                <span className="w-5 h-5 shrink-0 rounded-full bg-green/15 text-green text-xs flex items-center justify-center font-medium">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
          <a href={BINANCE_REFERRAL_URL} target="_blank" rel="noopener noreferrer">
            <Button variant="ghost" size="sm">Open Binance →</Button>
          </a>
        </div>
      </Card>
    </div>
  );
}
