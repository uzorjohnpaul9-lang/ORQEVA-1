"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ExchangeConn {
  id: string;
  exchange: string;
  display_name?: string;
  markets?: string[];
  is_paper: boolean;
  is_active: boolean;
  key_masked: string;
  connected_at: string;
  last_checked: string | null;
}

interface AdapterMeta {
  name: string;
  display_name: string;
  markets: string[];
  needs_secret: boolean;
}

export default function ExchangesPage() {
  const { token } = useAuth();
  const [conns, setConns] = useState<ExchangeConn[] | null>(null);
  const [adapters, setAdapters] = useState<AdapterMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // connect form
  const [showForm, setShowForm] = useState(false);
  const [exchange, setExchange] = useState("alpaca");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [isPaper, setIsPaper] = useState(true);
  const [busy, setBusy] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      setConns(await api<ExchangeConn[]>("/api/exchanges", { token }));
      setError(null);
    } catch {
      setError("Could not load exchange connections");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    refresh();
    api<AdapterMeta[]>("/api/exchanges/meta", { token })
      .then((list) => {
        setAdapters(list);
        if (list.length && !list.some((a) => a.name === "alpaca")) {
          setExchange(list[0].name);
        }
      })
      .catch(() => {});
  }, [token, refresh]);

  async function connect(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api("/api/exchanges/connect", {
        method: "POST",
        token,
        body: JSON.stringify({ exchange, api_key: apiKey, api_secret: apiSecret, is_paper: isPaper }),
      });
      setNotice("Connected. Run Test to validate credentials.");
      setShowForm(false);
      setApiKey("");
      setApiSecret("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect(id: string) {
    if (!token) return;
    setError(null);
    try {
      await api(`/api/exchanges/${id}`, { method: "DELETE", token });
      setNotice("Disconnected");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    }
  }

  async function testConn(id: string) {
    if (!token) return;
    setTestingId(id);
    setError(null);
    try {
      const res = await api<{ ok: boolean; detail: string }>(`/api/exchanges/${id}/test`, { method: "POST", token });
      setNotice(res.ok ? `Connection OK: ${res.detail}` : `Test failed: ${res.detail}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTestingId(null);
    }
  }

  const connectedExchanges = new Set((conns ?? []).map((c) => c.exchange));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Exchange Connections</h1>
        {!showForm && (
          <Button onClick={() => setShowForm(true)} disabled={connectedExchanges.size >= adapters.length}>
            + Connect Exchange
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-red">{error}</p>}
      {notice && <p className="text-sm text-green">{notice}</p>}

      {showForm && (
        <Card>
          <CardHeader><CardTitle>New Connection</CardTitle></CardHeader>
          <form onSubmit={connect} className="space-y-4 max-w-md">
            <Select
              label="Exchange"
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              options={adapters
                .filter((a) => !connectedExchanges.has(a.name))
                .map((a) => ({ value: a.name, label: `${a.display_name} (${a.markets.join("/")})` }))}
              required
            />
            <Input
              label="API Key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              minLength={10}
              required
            />
            {adapters.find((a) => a.name === exchange)?.needs_secret !== false && (
              <Input
                label="API Secret"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                required
              />
            )}
            <label className="flex items-center gap-2 text-sm text-text-secondary">
              <input type="checkbox" checked={isPaper} onChange={(e) => setIsPaper(e.target.checked)} />
              Paper trading mode
            </label>
            <div className="flex gap-2">
              <Button type="submit" disabled={busy} className="flex-1">
                {busy ? "Connecting..." : "Save Connection"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
            <p className="text-xs text-text-muted">Keys are encrypted at rest (Fernet) and never shown in full.</p>
          </form>
        </Card>
      )}

      {conns === null ? (
        <p className="text-sm text-text-muted">Loading connections...</p>
      ) : conns.length === 0 ? (
        <Card>
          <p className="text-sm text-text-muted py-8 text-center">
            No exchanges connected yet. Connect a broker to trade.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {conns.map((conn) => {
            const adapter = adapters.find((a) => a.name === conn.exchange);
            const label = conn.display_name ?? adapter?.display_name ?? (conn.exchange as string).charAt(0).toUpperCase() + (conn.exchange as string).slice(1);
            const type = (adapter?.markets ?? []).join("/") || "-";
            return (
              <Card key={conn.id}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-lg">{label}</h3>
                    <p className="text-sm text-text-secondary">{type}</p>
                  </div>
                  <Badge variant={conn.is_active ? "green" : conn.last_checked ? "red" : "yellow"} dot>
                    {conn.is_active ? "validated" : conn.last_checked ? "failed" : "untested"}
                  </Badge>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-text-muted">Mode</span>
                    <span>{conn.is_paper ? "Paper Trading" : "Live Trading"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">API Key</span>
                    <span className="font-mono">{conn.key_masked}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-muted">Last checked</span>
                    <span>{conn.last_checked ? new Date(conn.last_checked).toLocaleString() : "never"}</span>
                  </div>
                </div>

                <div className="mt-4 flex gap-2">
                  <Button variant="secondary" size="sm" className="flex-1" onClick={() => testConn(conn.id)} disabled={testingId === conn.id}>
                    {testingId === conn.id ? "Testing..." : "Test"}
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => disconnect(conn.id)}>Disconnect</Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
