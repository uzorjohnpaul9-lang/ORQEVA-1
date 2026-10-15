"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import {
  FEATURE_MATRIX,
  PLAN_PRICES,
  TIERS,
  tierBadgeVariant,
  tierLabel,
  tierRank,
  type FeatureValue,
} from "@/lib/plans";
import { BINANCE_REFERRAL_URL, REFERRAL_STEPS } from "@/lib/links";

function FeatureCell({ value }: { value: FeatureValue }) {
  if (value === true) return <span className="text-green font-medium">✓</span>;
  if (value === false) return <span className="text-text-muted">—</span>;
  return <span className="text-text-secondary">{value}</span>;
}

export default function VIPPage() {
  const { user } = useAuth();
  const current = (user?.tier || "free").toLowerCase();
  const currentRank = tierRank(current);
  const [copied, setCopied] = useState(false);

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
        <h1 className="text-2xl font-bold">Plans & Membership</h1>
        <Badge variant={tierBadgeVariant(current)}>Current: {tierLabel(current)}</Badge>
      </div>

      <p className="text-sm text-text-secondary max-w-2xl">
        Upgrade to unlock more markets, faster signals and auto-trade. Payments are handled on the
        Billing page via crypto (USDT) or manual transfer.
      </p>

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TIERS.map((t) => {
          const isCurrent = t.tier === current;
          const isUpgrade = tierRank(t.tier) > currentRank;
          return (
            <Card
              key={t.tier}
              className={isCurrent ? "border-green/50 ring-1 ring-green/30" : ""}
            >
              <div className="flex items-center justify-between mb-3">
                <CardTitle>{t.name}</CardTitle>
                {isCurrent ? (
                  <Badge variant="green">Current</Badge>
                ) : (
                  <Badge variant={tierBadgeVariant(t.tier)}>{t.tier.toUpperCase()}</Badge>
                )}
              </div>
              <p className="text-3xl font-bold mb-1">
                ${PLAN_PRICES[t.tier]}
                {t.tier !== "free" && <span className="text-sm text-text-muted font-normal">/30d</span>}
              </p>
              <p className="text-xs text-text-muted mb-4">{t.tagline}</p>
              <ul className="space-y-2 mb-5">
                {t.perks.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-green mt-0.5">✓</span>
                    {p}
                  </li>
                ))}
              </ul>
              {isUpgrade ? (
                <Link href="/billing" className="block">
                  <Button className="w-full">Upgrade to {t.name}</Button>
                </Link>
              ) : isCurrent ? (
                <Button className="w-full" variant="secondary" disabled>
                  Your current plan
                </Button>
              ) : (
                <div className="h-9" />
              )}
            </Card>
          );
        })}
      </div>

      {/* Comparison table */}
      <Card padding={false}>
        <div className="px-4 pt-4"><CardTitle>Compare Plans</CardTitle></div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs text-text-muted px-4 py-2 font-medium">Feature</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">Free</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">Premium</th>
                <th className="text-center text-xs text-text-muted px-4 py-2 font-medium">VIP</th>
              </tr>
            </thead>
            <tbody>
              {FEATURE_MATRIX.map((f) => (
                <tr key={f.label} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2.5">{f.label}</td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.free} /></td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.premium} /></td>
                  <td className="px-4 py-2.5 text-center"><FeatureCell value={f.vip} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Referral */}
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
