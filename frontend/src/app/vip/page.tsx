"use client";

import { Card, CardHeader, CardTitle, StatCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DonutChart } from "@/components/charts/DonutChart";

export default function VIPPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">VIP Features</h1>
        <Badge variant="purple">VIP</Badge>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="VIP Subscribers" value="12" change="+3 this week" />
        <StatCard label="Monthly Revenue" value="$1,200" change="+$300" />
        <StatCard label="Auto-Trade Enabled" value="5" />
        <StatCard label="Avg. VIP P&L" value="+8.2%" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Revenue by Tier</CardTitle></CardHeader>
          <DonutChart
            labels={["Free", "Premium", "VIP"]}
            data={[0, 800, 1200]}
            colors={["#5A5E72", "#FFBE0B", "#9B59B6"]}
            height={250}
          />
        </Card>

        <Card>
          <CardHeader><CardTitle>VIP Features</CardTitle></CardHeader>
          <div className="space-y-3">
            {[
              { name: "Unlimited Signals", status: true },
              { name: "Crypto Signals", status: true },
              { name: "Forex Signals", status: true },
              { name: "Auto-Trade Bot", status: true },
              { name: "Priority Support", status: true },
              { name: "Custom Risk Profiles", status: true },
              { name: "API Access", status: false },
            ].map((f) => (
              <div key={f.name} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <span className="text-sm">{f.name}</span>
                <Badge variant={f.status ? "green" : "gray"}>{f.status ? "Active" : "Coming Soon"}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Binance Referral</CardTitle></CardHeader>
        <div className="space-y-3">
          <p className="text-sm text-text-secondary">Earn commission by referring users to Binance.</p>
          <div className="flex items-center gap-2 bg-bg-tertiary rounded-lg p-3">
            <code className="text-sm text-green flex-1">https://www.binance.com/activity/referral-entry/CPA?ref=CPA_00N4AMKT4D</code>
            <Button variant="secondary" size="sm">Copy</Button>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="text-center">
              <p className="text-2xl font-bold">45</p>
              <p className="text-xs text-text-muted">Referrals</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green">$2,250</p>
              <p className="text-xs text-text-muted">Total Earned</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold">$50</p>
              <p className="text-xs text-text-muted">This Month</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
