"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/components/theme/ThemeProvider";
import type { Preferences } from "@/lib/types";

export default function SettingsPage() {
  const { user, token } = useAuth();
  const { theme, setTheme } = useTheme();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const p = await api<Preferences>("/api/preferences", { token });
      setPrefs(p);
    } catch {}
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function saveGeneral() {
    if (!token || !prefs) return;
    setBusy(true);
    try {
      const updated = await api<Preferences>("/api/preferences", {
        method: "PUT", token,
        body: {
          default_market: prefs.default_market,
          risk_tolerance: prefs.risk_tolerance,
        },
      });
      setPrefs({ ...prefs, ...updated });
      setNotice("Preferences saved");
    } catch { setNotice("Save failed"); }
    setBusy(false);
  }

  function saveTheme(next: "dark" | "light" | "system") {
    setTheme(next);
    setNotice("Theme updated");
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>
      {notice && <div className="rounded-md border border-border bg-bg-secondary px-4 py-2 text-sm">{notice}</div>}

      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-text-secondary">Username</span><p className="font-medium">{user?.username ?? "-"}</p></div>
          <div><span className="text-text-secondary">Email</span><p className="font-medium">{user?.email ?? "-"}</p></div>
          <div><span className="text-text-secondary">Plan</span><p className="font-medium uppercase">{user?.tier ?? "free"}</p></div>
        </div>
      </Card>

      <Card>
        <CardHeader><CardTitle>Other Preferences</CardTitle></CardHeader>
        <div className="space-y-4">
          <Select
            label="Default Market"
            value={prefs?.default_market ?? "all"}
            onChange={(e) => prefs && setPrefs({ ...prefs, default_market: e.target.value })}
            options={[
              { value: "all", label: "All Markets" },
              { value: "stock", label: "Stocks Only" },
              { value: "forex", label: "Forex Only" },
              { value: "crypto", label: "Crypto Only" },
              { value: "commodity", label: "Commodities Only" },
            ]}
          />
          <Select
            label="Risk Tolerance"
            value={prefs?.risk_tolerance ?? "moderate"}
            onChange={(e) => prefs && setPrefs({ ...prefs, risk_tolerance: e.target.value })}
            options={[
              { value: "conservative", label: "Conservative" },
              { value: "moderate", label: "Moderate" },
              { value: "aggressive", label: "Aggressive" },
            ]}
          />
          <Select
            label="Theme"
            value={theme}
            onChange={(e) => saveTheme(e.target.value as "dark" | "light" | "system")}
            options={[
              { value: "system", label: "System" },
              { value: "dark", label: "Dark" },
              { value: "light", label: "Light" },
            ]}
          />
          <Button variant="primary" size="sm" onClick={saveGeneral} disabled={busy || !prefs}>
            Save Preferences
          </Button>
        </div>
      </Card>

      <ApiKeysCard token={token} />
    </div>
  );
}

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at?: string | null;
  revoked: boolean;
  requests_today: number;
  requests_total: number;
}

function ApiKeysCard({ token }: { token: string | null }) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [quota, setQuota] = useState(0);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const r = await api<{ keys: ApiKey[]; daily_quota: number }>("/api/api-keys", { token });
      setKeys(r.keys);
      setQuota(r.daily_quota);
    } catch {
      setNotice("Could not load API keys");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    if (!token) return;
    setBusy(true); setNotice(""); setCreated(null);
    try {
      const r = await api<{ key: string }>("/api/api-keys", {
        method: "POST", token,
        body: JSON.stringify({ name: name.trim() || "default" }),
      });
      setCreated(r.key);
      setName("");
      await load();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Could not create key");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (!token) return;
    setBusy(true);
    try {
      await api(`/api/api-keys/${id}`, { method: "DELETE", token });
      await load();
    } catch {
      setNotice("Could not revoke key");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>API Keys</CardTitle></CardHeader>
      <div className="space-y-4">
        <p className="text-sm text-text-secondary">
          Use these keys with the metered signal API (<code className="text-green">/v1/signals</code>).
          Daily quota: <span className="text-text-primary font-medium">{quota.toLocaleString()}</span> requests.
          Keys are shown once at creation - store them safely.
        </p>

        {created && (
          <div className="bg-bg-tertiary rounded-lg p-3">
            <p className="text-xs text-text-muted mb-1">Your new key (copy it now - it will not be shown again):</p>
            <div className="flex items-center gap-2">
              <code className="text-xs text-green flex-1 break-all">{created}</code>
              <Button
                variant="secondary" size="sm"
                onClick={() => navigator.clipboard.writeText(created).catch(() => {})}
              >
                Copy
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <Input
              label="Key Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Trading bot"
            />
          </div>
          <Button variant="primary" size="sm" onClick={create} disabled={busy}>
            {busy ? "Working..." : "Create Key"}
          </Button>
        </div>

        {notice && <p className="text-sm text-red">{notice}</p>}

        <div className="space-y-2">
          {keys.length === 0 && <p className="text-sm text-text-muted">No API keys yet.</p>}
          {keys.map((k) => (
            <div key={k.id} className="flex flex-wrap items-center justify-between gap-2 p-3 bg-bg-tertiary rounded-lg">
              <div>
                <span className="text-sm font-medium">{k.name}</span>
                <span className="text-xs text-text-muted ml-2 font-mono">{k.prefix}…</span>
                {k.revoked && <span className="text-xs text-red ml-2">revoked</span>}
                <p className="text-xs text-text-muted mt-0.5">
                  {k.requests_today.toLocaleString()} today · {k.requests_total.toLocaleString()} total
                  {k.last_used_at ? ` · last used ${k.last_used_at.slice(0, 10)}` : " · never used"}
                </p>
              </div>
              {!k.revoked && (
                <Button variant="danger" size="sm" onClick={() => revoke(k.id)} disabled={busy}>
                  Revoke
                </Button>
              )}
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
