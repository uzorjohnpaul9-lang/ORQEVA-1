"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Prefs {
  telegram_signals: boolean;
  telegram_tp_sl: boolean;
  telegram_market_analysis: boolean;
  telegram_risk_alerts: boolean;
  telegram_system_alerts: boolean;
  email_notifications: boolean;
  web_notifications: boolean;
  default_market: string;
  risk_tolerance: string;
  theme: string;
  watchlist: string[];
  directions: string[];
  min_confidence: number;
  telegram_weekly_digest: boolean;
  telegram_chat_id?: string | null;
  telegram_linked?: boolean;
}

const TG_ITEMS: { key: keyof Prefs; label: string }[] = [
  { key: "telegram_signals", label: "Signal Alerts" },
  { key: "telegram_tp_sl", label: "TP/SL Notifications" },
  { key: "telegram_market_analysis", label: "Market Analysis" },
  { key: "telegram_risk_alerts", label: "Risk Alerts (kill switch, limit breaches)" },
  { key: "telegram_system_alerts", label: "System Alerts (payments, account)" },
];

export default function SettingsPage() {
  const { user, token } = useAuth();
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [chatId, setChatId] = useState("");
  const [watchInput, setWatchInput] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const p = await api<Prefs>("/api/preferences", { token });
      setPrefs(p);
      setWatchInput((p.watchlist ?? []).join(", "));
    } catch {}
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function toggle(key: keyof Prefs) {
    if (!token || !prefs) return;
    const next = !prefs[key];
    setPrefs({ ...prefs, [key]: next });
    try {
      const updated = await api<Prefs>("/api/preferences", { method: "PUT", token, body: { [key]: next } });
      setPrefs({ ...prefs, ...updated });
    } catch { load(); }
  }

  async function saveGeneral() {
    if (!token || !prefs) return;
    setBusy(true);
    try {
      const updated = await api<Prefs>("/api/preferences", {
        method: "PUT", token,
        body: {
          default_market: prefs.default_market,
          risk_tolerance: prefs.risk_tolerance,
          theme: prefs.theme,
          email_notifications: prefs.email_notifications,
          web_notifications: prefs.web_notifications,
        },
      });
      setPrefs({ ...prefs, ...updated });
      setNotice("Preferences saved");
    } catch { setNotice("Save failed"); }
    setBusy(false);
  }

  function toggleDirection(d: "buy" | "sell") {
    if (!prefs) return;
    const cur = prefs.directions ?? [];
    const next = cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d];
    setPrefs({ ...prefs, directions: next });
  }

  async function saveFilters() {
    if (!token || !prefs) return;
    setBusy(true);
    try {
      const watchlist = watchInput.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
      const body = {
        watchlist,
        directions: prefs.directions ?? [],
        min_confidence: prefs.min_confidence ?? 0,
        telegram_weekly_digest: prefs.telegram_weekly_digest ?? false,
      };
      const updated = await api<Prefs>("/api/preferences", { method: "PUT", token, body });
      setPrefs({ ...prefs, ...updated });
      setWatchInput((updated.watchlist ?? []).join(", "));
      setNotice("Signal filters saved");
    } catch { setNotice("Save failed"); }
    setBusy(false);
  }

  async function linkTelegram() {    if (!token || chatId.trim().length < 4) { setNotice("Enter a valid chat ID"); return; }
    setBusy(true);
    try {
      const res = await api<{ telegram_chat_id: string; test: { ok: boolean; detail: string } }>(
        "/api/preferences/telegram/link", { method: "POST", token, body: { chat_id: chatId.trim() } });
      setNotice(res.test.ok
        ? "Linked - confirmation sent to your Telegram"
        : `Linked, but test send failed (${res.test.detail}). Check the chat ID.`);
      await load();
    } catch { setNotice("Link failed"); }
    setBusy(false);
  }

  async function testTelegram() {
    if (!token) return;
    setBusy(true);
    try {
      const res = await api<{ ok: boolean; detail: string }>("/api/preferences/telegram/test", { method: "POST", token });
      setNotice(res.ok ? "Test message sent" : `Send failed: ${res.detail}`);
    } catch { setNotice("Test failed"); }
    setBusy(false);
  }

  async function unlinkTelegram() {
    if (!token) return;
    setBusy(true);
    try {
      await api("/api/preferences/telegram/link", { method: "DELETE", token });
      setNotice("Telegram unlinked");
      await load();
    } catch { setNotice("Unlink failed"); }
    setBusy(false);
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
        <CardHeader>
          <CardTitle>Telegram Notifications</CardTitle>
          {prefs?.telegram_linked ? (
            <span className="ml-auto rounded-full bg-green/15 px-3 py-1 text-xs font-medium text-green">
              Linked · {prefs.telegram_chat_id}
            </span>
          ) : (
            <span className="ml-auto rounded-full bg-bg-tertiary px-3 py-1 text-xs text-text-secondary">Not linked</span>
          )}
        </CardHeader>

        {!prefs?.telegram_linked && (
          <div className="flex items-end gap-2 pb-2">
            <Input label="Your Telegram Chat ID" value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="e.g. 8451723391" />
            <Button variant="primary" size="sm" onClick={linkTelegram} disabled={busy}>Link</Button>
          </div>
        )}
        {prefs?.telegram_linked && (
          <div className="flex gap-2 pb-3">
            <Button variant="secondary" size="sm" onClick={testTelegram} disabled={busy}>Send Test Message</Button>
            <Button variant="danger" size="sm" onClick={unlinkTelegram} disabled={busy}>Unlink</Button>
          </div>
        )}

        <div className="divide-y divide-border">
          {TG_ITEMS.map((item) => (
            <label key={String(item.key)} className="flex cursor-pointer items-center justify-between py-2.5">
              <span className="text-sm">{item.label}</span>
              <button
                type="button"
                role="switch"
                aria-checked={prefs ? Boolean(prefs[item.key]) : false}
                onClick={() => toggle(item.key)}
                className={`relative h-5 w-10 rounded-full transition-colors ${prefs && prefs[item.key] ? "bg-green" : "bg-bg-tertiary"}`}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${prefs && prefs[item.key] ? "left-[22px]" : "left-0.5"}`} />
              </button>
            </label>
          ))}
        </div>
        <p className="pt-3 text-xs text-text-secondary">Free tier receives signals and system alerts. TP/SL, analysis and risk alerts require Premium or VIP.</p>
      </Card>

      <Card>
        <CardHeader><CardTitle>Signal Filters</CardTitle></CardHeader>
        <p className="text-xs text-text-secondary">Only alerts matching these filters are pushed to Telegram.</p>
        <div className="mt-3 space-y-4">
          <Input
            label="Watchlist (comma-separated, empty = all symbols)"
            value={watchInput}
            onChange={(e) => setWatchInput(e.target.value)}
            placeholder="e.g. BTC, ETH, AAPL, EUR/USD"
          />
          <div>
            <span className="text-sm">Directions</span>
            <div className="mt-1 flex gap-2">
              {(["buy", "sell"] as const).map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDirection(d)}
                  className={`rounded-md border px-4 py-1.5 text-sm uppercase transition-colors ${
                    (prefs?.directions ?? []).includes(d)
                      ? "border-green bg-green/15 text-green"
                      : "border-border bg-bg-tertiary text-text-secondary"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-text-secondary">Unselected = both sides.</p>
          </div>
          <Select
            label="Minimum Confidence"
            value={String(prefs?.min_confidence ?? 0)}
            onChange={(e) => prefs && setPrefs({ ...prefs, min_confidence: parseFloat(e.target.value) })}
            options={[
              { value: "0", label: "Any" },
              { value: "0.5", label: "50%+" },
              { value: "0.6", label: "60%+" },
              { value: "0.7", label: "70%+" },
              { value: "0.8", label: "80%+" },
            ]}
          />
          <label className="flex cursor-pointer items-center justify-between">
            <span className="text-sm">Weekly Performance Digest (Sundays)</span>
            <button
              type="button"
              role="switch"
              aria-checked={prefs ? Boolean(prefs.telegram_weekly_digest) : false}
              onClick={() => toggle("telegram_weekly_digest")}
              className={`relative h-5 w-10 rounded-full transition-colors ${prefs && prefs.telegram_weekly_digest ? "bg-green" : "bg-bg-tertiary"}`}
            >
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${prefs && prefs.telegram_weekly_digest ? "left-[22px]" : "left-0.5"}`} />
            </button>
          </label>
          <Button variant="primary" size="sm" onClick={saveFilters} disabled={busy || !prefs}>Save Filters</Button>
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
            value={prefs?.theme ?? "dark"}
            onChange={(e) => prefs && setPrefs({ ...prefs, theme: e.target.value })}
            options={[{ value: "dark", label: "Dark" }, { value: "light", label: "Light" }]}
          />
          <Button variant="secondary" size="sm" onClick={saveGeneral} disabled={busy || !prefs}>Save Preferences</Button>
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
