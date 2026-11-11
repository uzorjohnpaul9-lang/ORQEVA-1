"use client";

import { useState } from "react";
import { Bell, BellOff, ExternalLink, Send, X } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { tierRank } from "@/lib/plans";
import type { Preferences } from "@/lib/types";

const BOTS: Record<string, { name: string; url: string }> = {
  free: { name: "@ORQEVA_free_bot", url: "https://t.me/ORQEVA_free_bot" },
  premium: { name: "@ORQEVA_premium_bot", url: "https://t.me/ORQEVA_premium_bot" },
  vip: { name: "@ORQEVA_VIP_bot", url: "https://t.me/ORQEVA_VIP_bot" },
};

function botForTier(tier?: string | null) {
  const t = (tier || "free").toLowerCase();
  return BOTS[t] ?? BOTS.free;
}

const TOGGLES: { key: keyof Preferences; label: string; hint?: string }[] = [
  { key: "telegram_signals", label: "Signal alerts", hint: "Pause to stop all pair alerts without losing your pairs." },
  { key: "telegram_tp_sl", label: "TP/SL notifications" },
  { key: "telegram_market_analysis", label: "Market analysis" },
  { key: "telegram_risk_alerts", label: "Risk alerts", hint: "Kill switch and limit breaches." },
  { key: "telegram_system_alerts", label: "System alerts", hint: "Payments and account changes." },
];

const PREMIUM_ONLY = new Set(["telegram_tp_sl", "telegram_market_analysis", "telegram_risk_alerts"]);

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={`relative h-5 w-10 shrink-0 rounded-full transition-colors disabled:opacity-40 ${
        checked ? "bg-green" : "bg-bg-tertiary"
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
          checked ? "left-[22px]" : "left-0.5"
        }`}
      />
    </button>
  );
}

interface TelegramAlertsModalProps {
  open: boolean;
  onClose: () => void;
  prefs: Preferences | null;
  token: string | null;
  tier?: string | null;
  focusSymbol?: string | null;
  pairBusy: Set<string>;
  onPrefsChange: (next: Preferences) => void;
  onSetPair: (symbol: string, subscribe: boolean) => Promise<void>;
  onNotice: (message: string) => void;
}

export function TelegramAlertsModal({
  open,
  onClose,
  prefs,
  token,
  tier,
  focusSymbol,
  pairBusy,
  onPrefsChange,
  onSetPair,
  onNotice,
}: TelegramAlertsModalProps) {
  const [chatId, setChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const bot = botForTier(tier);
  const linked = Boolean(prefs?.telegram_linked);
  const canUsePremium = tierRank(tier) >= 1;
  const pairs = prefs?.watchlist ?? [];
  const focus = focusSymbol?.toUpperCase() ?? null;
  const focusSubscribed = focus
    ? pairs.some((p) => p.toUpperCase() === focus)
    : false;

  async function savePrefs(body: Record<string, unknown>) {
    if (!token || !prefs) return;
    try {
      const updated = await api<Preferences>("/api/preferences", {
        method: "PUT",
        token,
        body,
      });
      onPrefsChange({
        ...prefs,
        ...updated,
        telegram_linked: prefs.telegram_linked,
        telegram_chat_id: prefs.telegram_chat_id,
      });
    } catch {
      setError("Could not save that setting. Please try again.");
    }
  }

  async function linkTelegram() {
    if (!token) return;
    if (chatId.trim().length < 4) {
      setError("Enter a valid Telegram chat ID.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await api<{
        telegram_chat_id: string;
        test: { ok: boolean; detail: string };
      }>("/api/preferences/telegram/link", {
        method: "POST",
        token,
        body: { chat_id: chatId.trim() },
      });
      const fresh = await api<Preferences>("/api/preferences", {
        token,
        noCache: true,
      });
      onPrefsChange(fresh);
      setChatId("");
      if (res.test.ok) {
        onNotice("Telegram linked - confirmation sent to your chat.");
      } else {
        onNotice(
          `Linked, but the test message failed (${res.test.detail}). Check the chat ID.`
        );
      }
      if (focus && !(fresh.watchlist ?? []).some((p) => p.toUpperCase() === focus)) {
        await onSetPair(focus, true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not link Telegram.");
    } finally {
      setBusy(false);
    }
  }

  async function testTelegram() {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const res = await api<{ ok: boolean; detail: string }>(
        "/api/preferences/telegram/test",
        { method: "POST", token }
      );
      onNotice(res.ok ? "Test message sent." : `Send failed: ${res.detail}`);
    } catch {
      setError("Could not send the test message.");
    } finally {
      setBusy(false);
    }
  }

  async function unlinkTelegram() {
    if (!token || !prefs) return;
    setBusy(true);
    setError("");
    try {
      await api("/api/preferences/telegram/link", { method: "DELETE", token });
      onPrefsChange({ ...prefs, telegram_linked: false, telegram_chat_id: null });
      onNotice("Telegram unlinked.");
    } catch {
      setError("Could not unlink Telegram.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleDirection(direction: "buy" | "sell") {
    if (!prefs) return;
    const current = prefs.directions ?? [];
    const next = current.includes(direction)
      ? current.filter((d) => d !== direction)
      : [...current, direction];
    await savePrefs({ directions: next });
  }

  return (
    <Modal open={open} onClose={onClose} title="Telegram alerts">
      {!prefs ? (
        <p className="text-sm text-text-muted">Loading your alert settings…</p>
      ) : (
        <div className="space-y-5">
          {error && (
            <p className="rounded-md border border-red/40 bg-red-dim px-3 py-2 text-xs text-red">
              {error}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {linked ? (
              <span className="rounded-full bg-green/15 px-3 py-1 text-xs font-medium text-green">
                Linked · {prefs.telegram_chat_id}
              </span>
            ) : (
              <span className="rounded-full bg-bg-tertiary px-3 py-1 text-xs text-text-secondary">
                Not linked
              </span>
            )}
            {linked && (
              <div className="ml-auto flex gap-2">
                <Button variant="secondary" size="sm" onClick={testTelegram} disabled={busy}>
                  <Send className="h-3.5 w-3.5" /> Send test
                </Button>
                <Button variant="danger" size="sm" onClick={unlinkTelegram} disabled={busy}>
                  Unlink
                </Button>
              </div>
            )}
          </div>

          {!linked && (
            <div className="rounded-lg border border-border bg-bg-tertiary p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">
                Set up in 4 steps
              </p>
              <ol className="mt-2 space-y-2 text-xs text-text-secondary">
                <li>
                  1. Open{" "}
                  <a
                    href={bot.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-green hover:underline"
                  >
                    {bot.name} <ExternalLink className="h-3 w-3" />
                  </a>{" "}
                  for your plan and tap <span className="text-text-primary">Start</span>.
                </li>
                <li>
                  2. Message{" "}
                  <a
                    href="https://t.me/userinfobot"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-green hover:underline"
                  >
                    @userinfobot <ExternalLink className="h-3 w-3" />
                  </a>{" "}
                  to get your numeric chat ID.
                </li>
                <li>3. Paste the chat ID below and link it.</li>
                <li>4. Flip the bells on the signal cards you want alerts for.</li>
              </ol>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <div className="min-w-[180px] flex-1">
                  <Input
                    label="Your Telegram chat ID"
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="e.g. 8451723391"
                  />
                </div>
                <Button variant="primary" size="sm" onClick={linkTelegram} disabled={busy}>
                  {busy ? "Linking…" : "Link Telegram"}
                </Button>
              </div>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold">Pairs you follow</p>
              <span className="text-xs text-text-muted">
                {pairs.length} pair{pairs.length === 1 ? "" : "s"}
              </span>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              Alerts are opt-in per pair. Turn bells on from any signal card.
            </p>

            {focus && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border bg-bg-tertiary p-3">
                <div className="flex min-w-0 items-center gap-2">
                  {focusSubscribed ? (
                    <Bell className="h-4 w-4 shrink-0 text-green" fill="currentColor" />
                  ) : (
                    <BellOff className="h-4 w-4 shrink-0 text-text-muted" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{focus}</p>
                    <p className="text-xs text-text-muted">
                      {focusSubscribed ? "Telegram alerts are on." : "Telegram alerts are off."}
                    </p>
                  </div>
                </div>
                <Button
                  variant={focusSubscribed ? "danger" : "primary"}
                  size="sm"
                  disabled={pairBusy.size > 0}
                  onClick={() => onSetPair(focus, !focusSubscribed)}
                >
                  {focusSubscribed ? "Turn off" : "Turn on"}
                </Button>
              </div>
            )}

            {pairs.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {pairs.map((symbol) => {
                  const sym = symbol.toUpperCase();
                  return (
                    <span
                      key={sym}
                      className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-tertiary py-1 pl-3 pr-1.5"
                    >
                      <Bell className="h-3 w-3 text-green" fill="currentColor" />
                      <span className="text-xs font-medium text-text-primary">{sym}</span>
                      <button
                        type="button"
                        disabled={pairBusy.size > 0}
                        onClick={() => onSetPair(sym, false)}
                        aria-label={`Turn off Telegram alerts for ${sym}`}
                        className="rounded-full p-0.5 text-text-muted transition-colors hover:bg-red/10 hover:text-red disabled:opacity-40"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 rounded-lg border border-dashed border-border px-3 py-4 text-center text-xs text-text-muted">
                No pairs yet. Flip a bell on a signal card to start.
              </p>
            )}
          </div>

          <div className="border-t border-border pt-4">
            <p className="text-sm font-semibold">Alert types</p>
            <div className="mt-2 divide-y divide-border">
              {TOGGLES.map((item) => {
                const locked = PREMIUM_ONLY.has(String(item.key)) && !canUsePremium;
                return (
                  <div key={String(item.key)} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="text-sm">{item.label}</p>
                      {item.hint && <p className="text-xs text-text-muted">{item.hint}</p>}
                      {locked && (
                        <p className="text-xs text-yellow">Requires Premium or VIP.</p>
                      )}
                    </div>
                    <Toggle
                      checked={Boolean(prefs[item.key])}
                      disabled={locked || busy}
                      onChange={() => savePrefs({ [item.key]: !prefs[item.key] })}
                    />
                  </div>
                );
              })}
              <div className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-sm">Weekly performance digest</p>
                  <p className="text-xs text-text-muted">Sundays, when your plan includes Telegram alerts.</p>
                </div>
                <Toggle
                  checked={Boolean(prefs.telegram_weekly_digest)}
                  disabled={busy}
                  onChange={() =>
                    savePrefs({ telegram_weekly_digest: !prefs.telegram_weekly_digest })
                  }
                />
              </div>
            </div>
          </div>

          <div className="border-t border-border pt-4">
            <p className="text-sm font-semibold">Signal alert filters</p>
            <p className="mt-1 text-xs text-text-secondary">
              Pairs always filter alerts. These narrow them further.
            </p>
            <div className="mt-3 space-y-3">
              <div>
                <span className="text-sm">Directions</span>
                <div className="mt-1 flex gap-2">
                  {(["buy", "sell"] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => toggleDirection(d)}
                      className={`rounded-md border px-4 py-1.5 text-sm uppercase transition-colors ${
                        (prefs.directions ?? []).includes(d)
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
                label="Minimum confidence"
                value={String(prefs.min_confidence ?? 0)}
                onChange={(e) => savePrefs({ min_confidence: parseFloat(e.target.value) })}
                options={[
                  { value: "0", label: "Any" },
                  { value: "0.5", label: "50%+" },
                  { value: "0.6", label: "60%+" },
                  { value: "0.7", label: "70%+" },
                  { value: "0.8", label: "80%+" },
                ]}
              />
            </div>
          </div>

          <p className="text-xs text-text-muted">
            Free tier receives signal and system alerts. TP/SL, analysis and risk alerts require
            Premium or VIP.
          </p>
        </div>
      )}
    </Modal>
  );
}
