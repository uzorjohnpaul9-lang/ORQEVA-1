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
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const p = await api<Prefs>("/api/preferences", { token });
      setPrefs(p);
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

  async function linkTelegram() {
    if (!token || chatId.trim().length < 4) { setNotice("Enter a valid chat ID"); return; }
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
    </div>
  );
}
